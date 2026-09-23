"""Proveedor de identidad OIDC de Mi Catamarca (SSO del portal ciudadano).

Flujo Authorization Code + PKCE (cliente confidencial, client_secret_post), como pide el documento
de integración de la Dirección Provincial de Sistema:

  authorize_url(...)  → el ciudadano se autentica en Mi Catamarca
  → callback con `code` → identidad_desde_code(...) → /token (code + code_verifier)
  → se valida el ID Token → /userinfo → identidad normalizada.

Está desacoplado detrás de una interfaz para poder:
  - usar el proveedor REAL cuando hay credenciales por entorno (producción/staging), y
  - usar un proveedor MOCK determinista en dev/demo/tests (sin API real ni el WAF de Cloudflare).

Endpoints (discovery verificado en https://api-mi.catamarca.gob.ar/openid/.well-known/openid-configuration):
  authorize /openid/authorize · token /openid/token · userinfo /openid/userinfo · jwks /openid/jwks
  id_token firmado con RS256 o HS256; autenticación del cliente por client_secret_post.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import get_settings

log = logging.getLogger("creditos.micatamarca")

TIMEOUT = 15
JWKS_TTL = 3600          # segundos que se cachean las claves públicas del proveedor


@dataclass
class Identidad:
    """Identidad normalizada que devuelve cualquier proveedor (real o mock)."""
    sub: str
    email: str = ""
    nombre: str = ""
    telefono: str = ""
    documento: str = ""
    crudo: dict | None = None   # claims originales, para depurar / decidir el vínculo con el maestro


@dataclass
class Desafio:
    """Lo que se genera al iniciar el login y hay que recordar hasta el callback."""
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    code_verifier: str = field(default_factory=lambda: secrets.token_urlsafe(64))

    @property
    def code_challenge(self) -> str:
        """S256: el proveedor guarda el hash y recién en /token se le muestra el verifier."""
        d = hashlib.sha256(self.code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(d).decode().rstrip("=")


class MiCatamarcaProvider:
    """Proveedor real: habla con los endpoints OIDC de Mi Catamarca."""
    mock = False
    _jwks: tuple[float, dict] | None = None   # (vencimiento, documento JWKS) — a nivel de clase

    def __init__(self, s):
        self.s = s

    def authorize_url(self, state: str, desafio: Desafio) -> str:
        q = {"client_id": self.s.micatamarca_client_id, "response_type": "code",
             "scope": self.s.micatamarca_scopes, "redirect_uri": self.s.micatamarca_redirect_uri,
             "state": state, "nonce": desafio.nonce}
        if self.s.micatamarca_pkce:
            q["code_challenge"] = desafio.code_challenge
            q["code_challenge_method"] = "S256"
        return f"{self.s.mc_authorize_url}?{urlencode(q)}"

    def identidad_desde_code(self, code: str, desafio: Desafio) -> Identidad:
        datos = {"grant_type": "authorization_code", "code": code,
                 "redirect_uri": self.s.micatamarca_redirect_uri,
                 "client_id": self.s.micatamarca_client_id,
                 "client_secret": self.s.micatamarca_client_secret}
        # Un login empezado con la versión anterior (o sin PKCE) no tiene verifier: no se manda uno vacío.
        if self.s.micatamarca_pkce and desafio.code_verifier:
            datos["code_verifier"] = desafio.code_verifier
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
            tok = c.post(self.s.mc_token_url, data=datos, headers={"Accept": "application/json"})
            tok.raise_for_status()
            cuerpo = tok.json()
            access = cuerpo.get("access_token", "")
            claims_id = self._validar_id_token(cuerpo.get("id_token", ""), desafio.nonce)
            ui = c.get(self.s.mc_userinfo_url, headers={"Authorization": f"Bearer {access}"})
            ui.raise_for_status()
            claims = ui.json()
        # El sub del userinfo tiene que ser el mismo del ID Token: si no, la respuesta no corresponde
        # a esta autenticación (OIDC Core 5.3.2) y no se puede confiar en ella.
        if claims_id and claims.get("sub") and claims_id.get("sub") != claims.get("sub"):
            raise ValueError("El userinfo no corresponde al ID Token (sub distinto)")
        return _normalizar({**claims_id, **claims})

    def _validar_id_token(self, id_token: str, nonce: str) -> dict:
        """Verifica firma y claims del ID Token (paso 6 del documento de integración).

        La firma se verifica con la clave pública del proveedor (RS256, JWKS cacheado) o con el
        client_secret (HS256). Si el JWKS no se puede traer —el proveedor está detrás de un WAF que
        desafía a los clientes que no son navegador—, se validan igual los claims y se deja aviso en
        el log: el token vino por el canal trasero TLS que abrimos nosotros contra /token
        autenticándonos como cliente, que es la excepción que contempla OIDC Core 3.1.3.7.
        """
        if not id_token:
            return {}
        exigidos = ["exp", "iat", "iss", "aud"]
        cabecera = jwt.get_unverified_header(id_token)
        alg = cabecera.get("alg", "RS256")
        try:
            if alg.startswith("HS"):
                claims = jwt.decode(id_token, self.s.micatamarca_client_secret, algorithms=[alg],
                                    audience=self.s.micatamarca_client_id, issuer=self.s.micatamarca_issuer,
                                    options={"require": exigidos})
            else:
                clave = self._clave_publica(cabecera.get("kid", ""))
                claims = jwt.decode(id_token, clave, algorithms=[alg],
                                    audience=self.s.micatamarca_client_id, issuer=self.s.micatamarca_issuer,
                                    options={"require": exigidos})
        except _SinJwks:
            log.warning("Mi Catamarca: no se pudo traer el JWKS; el ID Token se valida sin firma "
                        "(llegó por el canal trasero TLS de /token).")
            claims = jwt.decode(id_token, options={"verify_signature": False})
            if claims.get("iss") != self.s.micatamarca_issuer:
                raise ValueError("El ID Token no es de Mi Catamarca (iss distinto)")
            aud = claims.get("aud")
            if self.s.micatamarca_client_id not in (aud if isinstance(aud, list) else [aud]):
                raise ValueError("El ID Token no es para este cliente (aud distinto)")
            if claims.get("exp", 0) < time.time():
                raise ValueError("El ID Token está vencido")
        # El nonce ata el token a ESTE inicio de sesión: sin esto, uno robado se puede reinyectar.
        if nonce and claims.get("nonce") and claims["nonce"] != nonce:
            raise ValueError("El ID Token no corresponde a este inicio de sesión (nonce distinto)")
        return claims

    def _clave_publica(self, kid: str):
        doc = self._jwks_doc()
        from jwt.algorithms import RSAAlgorithm
        for k in doc.get("keys", []):
            if not kid or k.get("kid") == kid:
                return RSAAlgorithm.from_jwk(k)
        raise ValueError("Mi Catamarca no publica la clave con la que firmó el ID Token")

    def _jwks_doc(self) -> dict:
        cache = MiCatamarcaProvider._jwks
        if cache and cache[0] > time.time():
            return cache[1]
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.get(self.s.mc_jwks_url, headers={"Accept": "application/json"})
                r.raise_for_status()
                doc = r.json()
        except Exception as e:                       # WAF, red caída, respuesta que no es JSON…
            raise _SinJwks(str(e))
        MiCatamarcaProvider._jwks = (time.time() + JWKS_TTL, doc)
        return doc


class _SinJwks(Exception):
    """No se pudieron traer las claves públicas del proveedor."""


class MockMiCatamarca:
    """Proveedor MOCK: sin red. `authorize_url` apunta al endpoint mock del backend, que
    redirige al callback con un code fijo; `identidad_desde_code` devuelve un ciudadano demo."""
    mock = True

    def __init__(self, s):
        self.s = s

    def authorize_url(self, state: str, desafio: Desafio) -> str:
        # El backend expone /api/creditos/portal/auth/mock-authorize sólo cuando el proveedor es mock.
        return f"/api/creditos/portal/auth/mock-authorize?{urlencode({'state': state})}"

    def identidad_desde_code(self, code: str, desafio: Desafio) -> Identidad:
        return Identidad(sub="mc-demo-30123456", email="juan.perez@example.gob.ar",
                         nombre="JUAN CARLOS PEREZ", telefono="+54 383 400 0000",
                         documento="30123456", crudo={"mock": True, "code": code})


def _normalizar(claims: dict) -> Identidad:
    """Mapea los claims OIDC (userinfo) a nuestra Identidad. Tolerante a nombres alternativos."""
    nombre = (claims.get("name")
              or " ".join(x for x in (claims.get("given_name"), claims.get("family_name")) if x)
              or "").strip()
    return Identidad(
        sub=str(claims.get("sub", "")),
        email=claims.get("email", "") or "",
        nombre=nombre,
        telefono=claims.get("phone_number", "") or claims.get("phone", "") or "",
        documento=str(claims.get("documento") or claims.get("dni") or claims.get("cuil") or ""),
        crudo=claims,
    )


def get_provider():
    """Proveedor real si hay credenciales por entorno; si no, el mock (dev/demo/tests).

    Fuera de development el mock exige PORTAL_MOCK_SSO=true: el portal está publicado en Internet y el
    mock deja entrar a cualquiera como el ciudadano demo (y cargar solicitudes en la base real)."""
    s = get_settings()
    if s.micatamarca_configurado:
        return MiCatamarcaProvider(s)
    if s.environment.lower() in ("development", "dev", "test", "testing") or s.portal_mock_sso:
        return MockMiCatamarca(s)
    from fastapi import HTTPException
    raise HTTPException(503, "El portal no tiene configurado el ingreso con Mi Catamarca.")
