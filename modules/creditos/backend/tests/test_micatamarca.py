"""SSO Mi Catamarca (proveedor REAL): authorization code + PKCE y validación del ID Token.

El proveedor real no se toca en los tests: se le cambia el cliente HTTP por uno falso que devuelve
lo que devolvería Mi Catamarca (/token y /userinfo, y el /jwks cuando hay que verificar la firma).
Así se ejercita nuestro lado del contrato: qué mandamos y qué aceptamos.
"""
import base64
import json
import time

import httpx
import jwt
import pytest

from app.core.config import Settings
from app.services import mi_catamarca as mc

ISSUER = "https://api-mi.catamarca.gob.ar/openid"
CLIENT_ID = "967361"
SECRET = "un-secreto-de-prueba"
REDIRECT = "https://portal.example.gob.ar/api/creditos/portal/auth/callback"

USERINFO = {"sub": "ciudadano-1", "email": "juana@example.gob.ar", "given_name": "JUANA",
            "family_name": "PEREZ", "documento": "30123456"}


def _settings(**extra) -> Settings:
    return Settings(micatamarca_issuer=ISSUER, micatamarca_client_id=CLIENT_ID,
                    micatamarca_client_secret=SECRET, micatamarca_redirect_uri=REDIRECT,
                    micatamarca_scopes="openid profile email", **extra)


def _id_token(claims=None, secret=SECRET, alg="HS256", **extra):
    base = {"iss": ISSUER, "aud": CLIENT_ID, "sub": USERINFO["sub"],
            "exp": int(time.time()) + 300, "iat": int(time.time())}
    base.update(extra)
    if claims:
        base.update(claims)
    return jwt.encode(base, secret, algorithm=alg)


class _Respuesta(httpx.Response):
    def __init__(self, url, datos, status=200):
        super().__init__(status, json=datos, request=httpx.Request("GET", url))


class _ClienteFalso:
    """Reemplaza httpx.Client: responde según la URL y guarda lo que se le mandó."""
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviado = {}

    def __call__(self, *a, **kw):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _responder(self, url):
        r = self.respuestas.get(url)
        if r is None:
            raise httpx.ConnectError(f"sin ruta falsa para {url}")
        if isinstance(r, Exception):
            raise r
        return _Respuesta(url, r() if callable(r) else r)

    def post(self, url, data=None, headers=None):
        self.enviado[url] = data
        return self._responder(url)

    def get(self, url, headers=None):
        self.enviado[url] = headers
        return self._responder(url)


@pytest.fixture()
def sin_cache_jwks():
    mc.MiCatamarcaProvider._jwks = None
    yield
    mc.MiCatamarcaProvider._jwks = None


def _correr(monkeypatch, s, respuestas, desafio=None):
    cliente = _ClienteFalso(respuestas)
    monkeypatch.setattr(mc.httpx, "Client", cliente)
    prov = mc.MiCatamarcaProvider(s)
    d = desafio or mc.Desafio()
    return prov, cliente, d


# --------------------------------------------------------------------------- authorize
def test_authorize_url_lleva_pkce_y_nonce():
    s = _settings()
    d = mc.Desafio()
    url = mc.MiCatamarcaProvider(s).authorize_url("el-state", d)
    assert url.startswith(f"{ISSUER}/authorize?")
    q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    assert q["client_id"] == CLIENT_ID and q["response_type"] == "code"
    assert q["scope"] == "openid+profile+email"     # el scope concedido; `phone` no está otorgado
    assert q["state"] == "el-state" and q["nonce"] == d.nonce
    assert q["code_challenge_method"] == "S256" and q["code_challenge"] == d.code_challenge
    # PKCE: viaja el hash, nunca el verifier.
    assert d.code_verifier not in url


def test_code_challenge_es_el_sha256_del_verifier():
    d = mc.Desafio()
    import hashlib
    esperado = base64.urlsafe_b64encode(hashlib.sha256(d.code_verifier.encode()).digest()).decode().rstrip("=")
    assert d.code_challenge == esperado and "=" not in d.code_challenge


def test_pkce_se_puede_apagar():
    url = mc.MiCatamarcaProvider(_settings(micatamarca_pkce=False)).authorize_url("s", mc.Desafio())
    assert "code_challenge" not in url


# --------------------------------------------------------------------------- token + userinfo
def test_intercambio_manda_secreto_y_verifier_y_normaliza_la_identidad(monkeypatch):
    s = _settings()
    d = mc.Desafio()
    prov, cli, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": lambda: {"access_token": "at-1", "id_token": _id_token(nonce=d.nonce)},
        f"{ISSUER}/userinfo": USERINFO,
    }, d)
    ident = prov.identidad_desde_code("el-code", d)

    enviado = cli.enviado[f"{ISSUER}/token"]
    assert enviado["grant_type"] == "authorization_code" and enviado["code"] == "el-code"
    assert enviado["client_id"] == CLIENT_ID and enviado["client_secret"] == SECRET
    assert enviado["redirect_uri"] == REDIRECT and enviado["code_verifier"] == d.code_verifier
    assert cli.enviado[f"{ISSUER}/userinfo"]["Authorization"] == "Bearer at-1"

    assert ident.sub == "ciudadano-1" and ident.email == "juana@example.gob.ar"
    assert ident.nombre == "JUANA PEREZ" and ident.documento == "30123456"


def test_userinfo_de_otro_sub_se_rechaza(monkeypatch):
    """Si el userinfo no es del mismo sujeto que el ID Token, la respuesta no es de esta
    autenticación y no se puede confiar en ella (OIDC Core 5.3.2)."""
    s, d = _settings(), mc.Desafio()
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": lambda: {"access_token": "at", "id_token": _id_token(nonce=d.nonce)},
        f"{ISSUER}/userinfo": {**USERINFO, "sub": "otro-ciudadano"},
    }, d)
    with pytest.raises(ValueError, match="sub distinto"):
        prov.identidad_desde_code("code", d)


# --------------------------------------------------------------------------- ID Token
def test_id_token_hs256_se_verifica_con_el_secreto(monkeypatch):
    s, d = _settings(), mc.Desafio()
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": lambda: {"access_token": "at",
                                    "id_token": _id_token(secret="otro-secreto", nonce=d.nonce)},
        f"{ISSUER}/userinfo": USERINFO,
    }, d)
    with pytest.raises(jwt.InvalidSignatureError):
        prov.identidad_desde_code("code", d)


@pytest.mark.parametrize("malo, error", [
    ({"aud": "otro-cliente"}, jwt.InvalidAudienceError),
    ({"iss": "https://falso.example"}, jwt.InvalidIssuerError),
    ({"exp": int(time.time()) - 10}, jwt.ExpiredSignatureError),
])
def test_id_token_con_claims_que_no_son_nuestros_se_rechaza(monkeypatch, malo, error):
    s, d = _settings(), mc.Desafio()
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": lambda: {"access_token": "at", "id_token": _id_token(malo, nonce=d.nonce)},
        f"{ISSUER}/userinfo": USERINFO,
    }, d)
    with pytest.raises(error):
        prov.identidad_desde_code("code", d)


def test_id_token_de_otro_inicio_de_sesion_se_rechaza(monkeypatch):
    """El nonce ata el ID Token a ESTE login: uno de otra sesión (robado y reinyectado) no entra."""
    s, d = _settings(), mc.Desafio()
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": lambda: {"access_token": "at", "id_token": _id_token(nonce="otro-nonce")},
        f"{ISSUER}/userinfo": USERINFO,
    }, d)
    with pytest.raises(ValueError, match="nonce distinto"):
        prov.identidad_desde_code("code", d)


# --------------------------------------------------------------------------- firma RS256 (JWKS)
def _par_rsa():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_de(privada, kid="k1"):
    from jwt.algorithms import RSAAlgorithm
    pub = json.loads(RSAAlgorithm.to_jwk(privada.public_key()))
    return {"keys": [{**pub, "alg": "RS256", "use": "sig", "kid": kid}]}


def test_firma_rs256_valida_contra_el_jwks_del_proveedor(monkeypatch, sin_cache_jwks):
    privada = _par_rsa()
    s, d = _settings(), mc.Desafio()
    tok = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": USERINFO["sub"], "nonce": d.nonce,
                      "exp": int(time.time()) + 300, "iat": int(time.time())},
                     privada, algorithm="RS256", headers={"kid": "k1"})
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": {"access_token": "at", "id_token": tok},
        f"{ISSUER}/userinfo": USERINFO,
        f"{ISSUER}/jwks": _jwks_de(privada),
    }, d)
    assert prov.identidad_desde_code("code", d).sub == "ciudadano-1"


def test_firma_rs256_de_otra_clave_se_rechaza(monkeypatch, sin_cache_jwks):
    s, d = _settings(), mc.Desafio()
    intrusa, buena = _par_rsa(), _par_rsa()
    tok = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": USERINFO["sub"], "nonce": d.nonce,
                      "exp": int(time.time()) + 300, "iat": int(time.time())},
                     intrusa, algorithm="RS256", headers={"kid": "k1"})
    prov, _, _ = _correr(monkeypatch, s, {
        f"{ISSUER}/token": {"access_token": "at", "id_token": tok},
        f"{ISSUER}/userinfo": USERINFO,
        f"{ISSUER}/jwks": _jwks_de(buena),
    }, d)
    with pytest.raises(jwt.InvalidSignatureError):
        prov.identidad_desde_code("code", d)


def test_sin_jwks_el_login_sigue_pero_los_claims_se_validan_igual(monkeypatch, sin_cache_jwks):
    """El proveedor está detrás de un WAF que desafía a los clientes que no son navegador: si el JWKS
    no se puede traer, el ID Token llegó igual por el canal trasero TLS de /token, así que se aceptan
    los claims válidos… pero uno de otro emisor o vencido se sigue rechazando."""
    privada = _par_rsa()
    s, d = _settings(), mc.Desafio()
    firmar = lambda **extra: jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": USERINFO["sub"],
                                         "nonce": d.nonce, "exp": int(time.time()) + 300,
                                         "iat": int(time.time()), **extra},
                                        privada, algorithm="RS256", headers={"kid": "k1"})
    rutas = {f"{ISSUER}/token": {"access_token": "at", "id_token": firmar()},
             f"{ISSUER}/userinfo": USERINFO,
             f"{ISSUER}/jwks": httpx.ConnectError("bloqueado por el WAF")}
    prov, _, _ = _correr(monkeypatch, s, rutas, d)
    assert prov.identidad_desde_code("code", d).sub == "ciudadano-1"

    for malo in ({"iss": "https://falso.example"}, {"aud": "otro"}, {"exp": int(time.time()) - 5}):
        rutas[f"{ISSUER}/token"] = {"access_token": "at", "id_token": firmar(**malo)}
        prov, _, _ = _correr(monkeypatch, s, rutas, d)
        with pytest.raises(ValueError):
            prov.identidad_desde_code("code", d)


def test_el_jwks_se_cachea(monkeypatch, sin_cache_jwks):
    privada = _par_rsa()
    s, d = _settings(), mc.Desafio()
    veces = {"n": 0}

    def jwks():
        veces["n"] += 1
        return _jwks_de(privada)

    tok = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": USERINFO["sub"], "nonce": d.nonce,
                      "exp": int(time.time()) + 300, "iat": int(time.time())},
                     privada, algorithm="RS256", headers={"kid": "k1"})
    rutas = {f"{ISSUER}/token": {"access_token": "at", "id_token": tok},
             f"{ISSUER}/userinfo": USERINFO, f"{ISSUER}/jwks": jwks}
    for _ in range(3):
        prov, _, _ = _correr(monkeypatch, s, rutas, d)
        prov.identidad_desde_code("code", d)
    assert veces["n"] == 1


# --------------------------------------------------------------------------- endpoints / configuración
def test_los_endpoints_salen_del_issuer_y_se_pueden_pisar():
    s = _settings()
    assert (s.mc_authorize_url, s.mc_token_url) == (f"{ISSUER}/authorize", f"{ISSUER}/token")
    assert (s.mc_userinfo_url, s.mc_jwks_url) == (f"{ISSUER}/userinfo", f"{ISSUER}/jwks")
    dev = Settings(micatamarca_issuer="https://develop-api-mi.catamarca.gob.ar/openid")
    assert dev.mc_token_url == "https://develop-api-mi.catamarca.gob.ar/openid/token"
    pisado = _settings(micatamarca_token_endpoint="https://otro.example/tk")
    assert pisado.mc_token_url == "https://otro.example/tk"


def test_con_credenciales_se_usa_el_proveedor_real(monkeypatch):
    monkeypatch.setattr(mc, "get_settings", lambda: _settings())
    assert isinstance(mc.get_provider(), mc.MiCatamarcaProvider)
    monkeypatch.setattr(mc, "get_settings", lambda: Settings(environment="production",
                                                             portal_mock_sso=False))
    from fastapi import HTTPException
    with pytest.raises(HTTPException):     # sin credenciales y en producción: no se entra con el mock
        mc.get_provider()
