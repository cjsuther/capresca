"""Doble factor (TOTP con TokenServer): login en dos pasos, enrolamiento, step-up, reset y errores.

TokenServer está simulado (tests/tokenserver_falso.py) detrás del cliente HTTP real.
"""
import httpx
import pytest
from jose import jwt

from app.config import settings
from app.services import auditoria_central as central
from app.services import tokenserver as ts
from app.services.auth_service import (
    SCOPE_LOGIN, SCOPE_STEP_UP, clave_derivada, decode_temp_token, decode_token, create_access_token,
)
from tests.tokenserver_falso import CODIGO_OK, CODIGO_OK_2, TokenServerFalso

CLAVE = "Secreta123!"


@pytest.fixture
def falso(monkeypatch):
    f = TokenServerFalso()
    monkeypatch.setattr(settings, "tokenserver_enabled", True)
    monkeypatch.setattr(settings, "tokenserver_api_key", f.api_key)
    monkeypatch.setattr(settings, "tokenserver_url", "http://tokenserver.test/v1")
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "")
    real = ts._cliente

    def _cliente():
        c = real()
        return httpx.Client(base_url=c.base_url, headers=c.headers, timeout=c.timeout, transport=f.transporte())

    monkeypatch.setattr(ts, "_cliente", _cliente)
    return f


@pytest.fixture
def auditados(monkeypatch):
    eventos = []
    monkeypatch.setattr(central, "registrar", lambda **kw: eventos.append(kw))
    return eventos


def _login(client, username="jperez", password=CLAVE):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _con_2fa(db, falso, user):
    user.totp_activo = True
    db.commit()
    falso.activar_usuario(str(user.id))
    return user


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Apagado: nada cambia ─────────────────────────────────────────────────────────────────────────
def test_apagado_el_login_es_el_de_siempre(client, crear_usuario, db):
    u = crear_usuario()
    u.totp_activo = True          # aunque haya quedado marcado, apagado no se pide nada
    db.commit()
    r = _login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["requires_2fa"] is False
    assert "amr" not in decode_token(body["access_token"])


def test_apagado_los_endpoints_2fa_responden_404(client, crear_usuario):
    crear_usuario()
    tok = _login(client).json()["access_token"]
    r = client.post("/api/auth/2fa/enrolar", headers=_auth(tok))
    assert r.status_code == 404 and r.json()["code"] == "2fa_deshabilitado"
    assert client.get("/api/auth/2fa/estado", headers=_auth(tok)).json()["habilitado"] is False


# ── Login en dos pasos ───────────────────────────────────────────────────────────────────────────
def test_sin_2fa_y_opcional_entra_directo(client, crear_usuario, falso):
    crear_usuario()
    body = _login(client).json()
    assert body["access_token"] and not body["requires_2fa"] and not body["requires_enrollment"]
    assert falso.llamadas == []          # no hizo falta consultar a TokenServer


def test_con_2fa_la_clave_sola_no_da_sesion(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    body = _login(client).json()
    assert body["requires_2fa"] is True
    assert body["access_token"] is None and body["user"] is None and body["permissions"] is None
    assert body["mfa_token"] and 0 < body["mfa_expires_in"] <= settings.tokenserver_login_minutos * 60
    # El token temporal no vale como sesión: ni para renovar ni para operar.
    assert decode_token(body["mfa_token"]) is None
    assert client.post("/api/auth/refresh", headers=_auth(body["mfa_token"])).status_code == 401
    assert client.get("/api/auth/2fa/estado", headers=_auth(body["mfa_token"])).status_code == 401


def test_codigo_correcto_emite_la_sesion_con_amr_otp(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": "123 456"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == u.id
    assert decode_token(body["access_token"])["amr"] == ["pwd", "otp"]
    assert ("POST", f"/v1/users/{u.id}/verify") in falso.llamadas   # uid = id interno, no el mail


def test_el_token_temporal_es_de_un_solo_uso(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    assert client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).status_code == 200
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK_2})
    assert r.status_code == 400 and r.json()["code"] == "mfa_token_invalido"


def test_codigo_incorrecto_informa_intentos_y_deja_reintentar(client, crear_usuario, falso, db, auditados):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": "000000"})
    assert r.status_code == 422
    assert r.json() == {"detail": "El código no es correcto.", "code": "codigo_invalido", "remaining_attempts": 4}
    assert "access_token" not in r.json()
    assert any(e.get("exito") is False for e in auditados)
    assert client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).status_code == 200


def test_usuario_bloqueado_devuelve_429_con_retry_after(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    for _ in range(5):
        client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": "000000"})
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK})
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert r.json()["code"] == "2fa_bloqueado" and r.json()["retry_after"] == 60


@pytest.mark.parametrize("como", ["caido", "500", "401", "403", "rate_limited"])
def test_tokenserver_no_disponible_falla_cerrado(client, crear_usuario, falso, db, como):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    if como == "caido":
        falso.caido = True
    elif como == "rate_limited":
        falso.forzar = (429, {"error": "rate_limited", "message": "x"}, {"Retry-After": "1"})
    else:
        falso.forzar = (int(como), {"error": "internal_error" if como == "500" else "unauthorized",
                                    "message": "x"}, {})
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK})
    assert r.status_code == 503
    assert r.json()["code"] == "2fa_no_disponible"
    assert "segundo factor" in r.json()["detail"]
    assert "access_token" not in r.json()


def test_sin_api_key_falla_cerrado(client, crear_usuario, falso, db, monkeypatch):
    _con_2fa(db, falso, crear_usuario())
    monkeypatch.setattr(settings, "tokenserver_api_key", "")
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK})
    assert r.status_code == 503 and falso.llamadas == []


def test_sin_dispositivo_activo_niega_y_baja_la_marca(client, crear_usuario, falso, db):
    u = crear_usuario()
    u.totp_activo = True          # marcado localmente, pero en TokenServer no hay tokens (reset del panel)
    db.commit()
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK})
    assert r.status_code == 409 and r.json()["code"] == "2fa_sin_dispositivo"
    assert "access_token" not in r.json()
    db.refresh(u)
    assert u.totp_activo is False


def test_codigo_de_recuperacion_en_el_login(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    codigos = ts.generar_codigos_recuperacion(u.id)
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": codigos[0].lower()})
    assert r.status_code == 200
    assert r.json()["remaining_recovery_codes"] == 9
    # Ya usado: no vuelve a servir.
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": codigos[0]})
    assert r.status_code == 422


def test_codigo_con_formato_invalido_no_llama_a_tokenserver(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    r = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": "12ab"})
    assert r.status_code == 422 and falso.llamadas == []


def test_token_temporal_vencido_o_falsificado(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    # Firmado con JWT_SECRET (la clave de las sesiones), no con la derivada: no vale.
    falso_tok = jwt.encode({"sub": str(u.id), "scope": SCOPE_LOGIN, "jti": "x", "exp": 9999999999},
                           settings.jwt_secret, algorithm="HS256")
    r = client.post("/api/auth/2fa/login", json={"mfa_token": falso_tok, "code": CODIGO_OK})
    assert r.status_code == 400
    vencido = jwt.encode({"sub": str(u.id), "scope": SCOPE_LOGIN, "jti": "y", "exp": 1},
                         clave_derivada(SCOPE_LOGIN), algorithm="HS256")
    assert client.post("/api/auth/2fa/login", json={"mfa_token": vencido, "code": CODIGO_OK}).status_code == 400


def test_una_sesion_no_sirve_como_token_temporal(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    sesion = create_access_token(1, "jperez")
    r = client.post("/api/auth/2fa/login", json={"mfa_token": sesion, "code": CODIGO_OK})
    assert r.status_code == 400


def test_refresh_conserva_el_segundo_factor(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    tok = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).json()["access_token"]
    nuevo = client.post("/api/auth/refresh", headers=_auth(tok)).json()["access_token"]
    assert decode_token(nuevo)["amr"] == ["pwd", "otp"]


# ── Política: obligatorio ────────────────────────────────────────────────────────────────────────
def test_obligatorio_para_todos_lleva_a_enrolarse_en_el_login(client, crear_usuario, falso, db, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "*")
    u = crear_usuario()
    body = _login(client).json()
    assert body["requires_enrollment"] is True and body["access_token"] is None
    mfa = body["mfa_token"]
    # El token de enrolamiento no sirve para el paso del código (otro propósito, otra clave).
    assert client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).status_code == 400

    en = client.post("/api/auth/2fa/login/enrolar", json={"mfa_token": mfa})
    assert en.status_code == 200, en.text
    en = en.json()
    assert en["qr_png_base64"] and en["secret"] and en["account"] == "jperez"
    r = client.post("/api/auth/2fa/login/activar",
                    json={"mfa_token": mfa, "token_id": en["token_id"], "code": CODIGO_OK})
    assert r.status_code == 200, r.text
    assert len(r.json()["recovery_codes"]) == 10
    assert decode_token(r.json()["access_token"])["amr"] == ["pwd", "otp"]
    db.refresh(u)
    assert u.totp_activo is True and u.totp_activado_en is not None
    # Usado: no se puede volver a enrolar con el mismo token.
    assert client.post("/api/auth/2fa/login/enrolar", json={"mfa_token": mfa}).status_code == 400
    # Próximo login: ya pide el código.
    assert _login(client).json()["requires_2fa"] is True


def test_obligatorio_por_rol_heredado_de_grupo(client, crear_usuario, crear_rol, falso, db, monkeypatch):
    from app.models.group import Group
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "Tesorería, admin")
    u = crear_usuario()
    otro = crear_usuario(username="otro")
    g = Group(name="tes", is_active=True)
    g.roles = [crear_rol(name="tesorería")]
    g.users = [u]
    db.add(g)
    db.commit()
    assert _login(client).json()["requires_enrollment"] is True
    assert _login(client, "otro").json()["access_token"]          # sin ese rol: opcional
    g.is_active = False                                            # grupo inactivo: no hereda
    db.commit()
    assert _login(client).json()["access_token"]
    assert otro


def test_enrolamiento_activacion_codigo_incorrecto_y_vencido(client, crear_usuario, falso, db, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "*")
    crear_usuario()
    mfa = _login(client).json()["mfa_token"]
    en = client.post("/api/auth/2fa/login/enrolar", json={"mfa_token": mfa}).json()
    r = client.post("/api/auth/2fa/login/activar", json={"mfa_token": mfa, "token_id": en["token_id"], "code": "000000"})
    assert r.status_code == 422 and r.json()["remaining_attempts"] == 4
    falso.forzar = (410, {"error": "enrollment_expired", "message": "venció"}, {})
    r = client.post("/api/auth/2fa/login/activar", json={"mfa_token": mfa, "token_id": en["token_id"], "code": CODIGO_OK})
    assert r.status_code == 410 and r.json()["code"] == "enrolamiento_vencido"
    falso.caido = True
    r = client.post("/api/auth/2fa/login/enrolar", json={"mfa_token": mfa})
    assert r.status_code == 503


def test_reenrolar_borra_los_pendientes_anteriores(client, crear_usuario, falso, db):
    u = crear_usuario()
    tok = _login(client).json()["access_token"]
    client.post("/api/auth/2fa/enrolar", headers=_auth(tok))
    client.post("/api/auth/2fa/enrolar", headers=_auth(tok))
    assert len(falso.tokens[str(u.id)]) == 1


# ── Perfil: activar, códigos, desactivar ─────────────────────────────────────────────────────────
def test_activar_desde_el_perfil_renueva_la_sesion_con_2fa(client, crear_usuario, falso, db):
    crear_usuario()
    tok = _login(client).json()["access_token"]
    assert client.get("/api/auth/2fa/estado", headers=_auth(tok)).json()["activo"] is False
    en = client.post("/api/auth/2fa/enrolar", headers=_auth(tok)).json()
    r = client.post("/api/auth/2fa/activar", headers=_auth(tok), json={"token_id": en["token_id"], "code": CODIGO_OK})
    assert r.status_code == 200, r.text
    nuevo = r.json()["access_token"]
    assert decode_token(nuevo)["amr"] == ["pwd", "otp"]
    assert len(r.json()["recovery_codes"]) == 10
    # La sesión vieja quedó revocada.
    assert client.get("/api/auth/2fa/estado", headers=_auth(tok)).status_code == 401
    est = client.get("/api/auth/2fa/estado", headers=_auth(nuevo)).json()
    assert est["activo"] is True and est["sesion_con_2fa"] is True
    assert client.post("/api/auth/2fa/enrolar", headers=_auth(nuevo)).json()["code"] == "2fa_ya_activo"


def test_regenerar_codigos_exige_codigo(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    tok = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).json()["access_token"]
    assert client.post("/api/auth/2fa/codigos-recuperacion", headers=_auth(tok), json={"code": "000000"}).status_code == 422
    r = client.post("/api/auth/2fa/codigos-recuperacion", headers=_auth(tok), json={"code": CODIGO_OK_2})
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == 10


def test_desactivar_exige_codigo_y_respeta_la_politica(client, crear_usuario, falso, db, monkeypatch):
    u = _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    tok = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).json()["access_token"]
    assert client.post("/api/auth/2fa/desactivar", headers=_auth(tok), json={"code": "000000"}).status_code == 422
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "*")
    r = client.post("/api/auth/2fa/desactivar", headers=_auth(tok), json={"code": CODIGO_OK_2})
    assert r.status_code == 403 and r.json()["code"] == "2fa_obligatorio"
    monkeypatch.setattr(settings, "tokenserver_obligatorio_roles", "")
    r = client.post("/api/auth/2fa/desactivar", headers=_auth(tok), json={"code": CODIGO_OK_2})
    assert r.status_code == 200, r.text
    assert "amr" not in decode_token(r.json()["access_token"])
    db.refresh(u)
    assert u.totp_activo is False and str(u.id) not in falso.tokens


# ── Step-up ──────────────────────────────────────────────────────────────────────────────────────
def test_step_up_emite_token_atado_a_la_sesion(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    tok = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).json()["access_token"]
    r = client.post("/api/auth/2fa/step-up", headers=_auth(tok), json={"code": CODIGO_OK_2})
    assert r.status_code == 200, r.text
    assert r.json()["expires_in"] == settings.tokenserver_stepup_minutos * 60
    p = decode_temp_token(r.json()["step_up_token"], SCOPE_STEP_UP)
    assert p["sub"] == str(u.id) and p["sid"] == decode_token(tok)["jti"]
    assert decode_token(r.json()["step_up_token"]) is None        # no es una sesión


def test_step_up_sin_2fa_o_con_codigo_malo(client, crear_usuario, falso, db):
    crear_usuario()
    tok = _login(client).json()["access_token"]
    r = client.post("/api/auth/2fa/step-up", headers=_auth(tok), json={"code": CODIGO_OK})
    assert r.status_code == 409 and r.json()["code"] == "2fa_no_activo"
    assert client.post("/api/auth/2fa/step-up", json={"code": CODIGO_OK}).status_code == 401


def test_step_up_tokenserver_caido(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    mfa = _login(client).json()["mfa_token"]
    tok = client.post("/api/auth/2fa/login", json={"mfa_token": mfa, "code": CODIGO_OK}).json()["access_token"]
    falso.caido = True
    r = client.post("/api/auth/2fa/step-up", headers=_auth(tok), json={"code": CODIGO_OK_2})
    assert r.status_code == 503 and "step_up_token" not in r.json()


# ── Reset por un administrador ───────────────────────────────────────────────────────────────────
def test_admin_resetea_el_2fa_y_queda_auditado(client, crear_usuario, falso, db, auditados):
    u = _con_2fa(db, falso, crear_usuario())
    r = client.delete(f"/api/security/users/{u.id}/2fa", headers={"X-User-Id": "999", "X-Username": "admin"})
    assert r.status_code == 200, r.text
    assert r.json() == {"user_id": u.id, "totp_activo": False, "dispositivos_borrados": 1}
    db.refresh(u)
    assert u.totp_activo is False
    assert ("DELETE", f"/v1/users/{u.id}") in falso.llamadas
    ev = [e for e in auditados if "Reset del doble factor" in e.get("descripcion", "")]
    assert ev and ev[0]["entidad_id"] == str(u.id) and "admin" in ev[0]["descripcion"]
    # Después del reset el login ya no pide código (y si es obligatorio, lo manda a enrolarse).
    assert _login(client).json()["access_token"]


def test_admin_no_resetea_el_propio(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    r = client.delete(f"/api/security/users/{u.id}/2fa", headers={"X-User-Id": str(u.id)})
    assert r.status_code == 403
    db.refresh(u)
    assert u.totp_activo is True


def test_reset_con_tokenserver_caido_no_baja_la_marca(client, crear_usuario, falso, db):
    u = _con_2fa(db, falso, crear_usuario())
    falso.caido = True
    r = client.delete(f"/api/security/users/{u.id}/2fa", headers={"X-User-Id": "999"})
    assert r.status_code == 503
    db.refresh(u)
    assert u.totp_activo is True


def test_listado_de_usuarios_muestra_el_estado(client, crear_usuario, falso, db):
    _con_2fa(db, falso, crear_usuario())
    data = client.get("/api/security/users").json()["data"]
    assert data[0]["totp_activo"] is True
