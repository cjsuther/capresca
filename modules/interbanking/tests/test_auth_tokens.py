"""Autenticación OAuth contra Interbanking: un token por scope, cacheo, renovación
y traducción de los errores del proveedor."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import HTTPException

from app.models.audit_log import ApiAuditLog
from app.models.tokens import InterbankingToken
from app.scopes import INFO_FINANCIERA, TRANSFERENCIAS_CONFECCION, grant_for
from app.services import token_manager


def _token_vigente(db, cred, scope, minutos=60, access_token="tok-guardado"):
    t = InterbankingToken(
        credential_id=cred.id, scope=scope, access_token=access_token,
        token_type="Bearer",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutos),
        is_active=True,
    )
    db.add(t)
    db.commit()
    return t


# ─────────────────────────────── Scopes y grants ───────────────────────────────

def test_cada_scope_tiene_su_grant():
    assert grant_for(INFO_FINANCIERA) == "client_credentials"
    assert grant_for(TRANSFERENCIAS_CONFECCION) == "password"


def test_scope_desconocido_es_error():
    with pytest.raises(ValueError, match="Scope desconocido"):
        grant_for("cualquier-cosa")


# ─────────────────────────── Obtención del token ───────────────────────────────

def test_info_financiera_pide_el_token_con_client_credentials(db, cred, red):
    red.token(body={"access_token": "tok-info", "token_type": "Bearer", "expires_in": 1800})

    token, cred_id = token_manager.get_valid_token(db, INFO_FINANCIERA, user_id=7)

    assert (token, cred_id) == ("tok-info", cred.id)
    pedido = red.ultima
    assert pedido["url"] == "https://auth.ib.test/cas/oidc/accessToken"
    assert pedido["params"] == {"scope": INFO_FINANCIERA}
    # El secreto viaja descifrado al proveedor, nunca el blob de la base.
    assert pedido["data"] == {"grant_type": "client_credentials",
                              "client_id": "cli-123", "client_secret": "secreto-cc"}
    assert pedido["headers"]["service"] == "https://api.ib.test/svc"


def test_transferencias_pide_el_token_con_password_grant(db, cred, red):
    red.token(body={"access_token": "tok-transf", "expires_in": 600})

    token, _ = token_manager.get_valid_token(db, TRANSFERENCIAS_CONFECCION, user_id=7)

    assert token == "tok-transf"
    assert red.ultima["data"] == {"grant_type": "password", "username": "usuario.ib",
                                  "password": "pass-ib", "client_id": "cli-123"}


def test_el_token_se_guarda_con_su_scope_y_vencimiento(db, cred, red):
    red.token(body={"access_token": "tok-x", "expires_in": 120})
    antes = datetime.now(timezone.utc)

    token_manager.get_valid_token(db, INFO_FINANCIERA)

    fila = db.query(InterbankingToken).one()
    assert (fila.scope, fila.access_token, fila.is_active) == (INFO_FINANCIERA, "tok-x", True)
    vence = fila.expires_at.replace(tzinfo=timezone.utc)
    assert timedelta(seconds=110) <= vence - antes <= timedelta(seconds=130)


def test_los_scopes_no_comparten_token(db, cred, red):
    red.token(body={"access_token": "tok-uno", "expires_in": 3600})
    token_manager.get_valid_token(db, INFO_FINANCIERA)
    red.limpiar_rutas()
    red.token(body={"access_token": "tok-dos", "expires_in": 3600})
    token_manager.get_valid_token(db, TRANSFERENCIAS_CONFECCION)

    guardados = {t.scope: t.access_token for t in db.query(InterbankingToken).all()}
    assert guardados == {INFO_FINANCIERA: "tok-uno", TRANSFERENCIAS_CONFECCION: "tok-dos"}


def test_el_token_vigente_se_reutiliza_sin_llamar_al_proveedor(db, cred, red):
    _token_vigente(db, cred, INFO_FINANCIERA, minutos=60, access_token="tok-cacheado")

    token, _ = token_manager.get_valid_token(db, INFO_FINANCIERA)

    assert token == "tok-cacheado"
    assert red.llamadas == []


def test_el_token_por_vencer_se_renueva_y_el_viejo_se_desactiva(db, cred, red):
    # 2 minutos de vida: por debajo del margen de refresco de 5 minutos.
    _token_vigente(db, cred, INFO_FINANCIERA, minutos=2, access_token="tok-viejo")
    red.token(body={"access_token": "tok-nuevo", "expires_in": 3600})

    token, _ = token_manager.get_valid_token(db, INFO_FINANCIERA)

    assert token == "tok-nuevo"
    estados = {t.access_token: t.is_active for t in db.query(InterbankingToken).all()}
    assert estados == {"tok-viejo": False, "tok-nuevo": True}


def test_el_token_de_otro_scope_no_sirve_y_dispara_pedido(db, cred, red):
    _token_vigente(db, cred, INFO_FINANCIERA, access_token="tok-info")
    red.token(body={"access_token": "tok-transf", "expires_in": 3600})

    token, _ = token_manager.get_valid_token(db, TRANSFERENCIAS_CONFECCION)

    assert token == "tok-transf"
    assert len(red.llamadas) == 1


def test_sin_credencial_activa_es_503(db, red):
    with pytest.raises(HTTPException) as e:
        token_manager.get_valid_token(db, INFO_FINANCIERA)
    assert e.value.status_code == 503
    assert "No hay credenciales" in e.value.detail


def test_sin_client_secret_no_se_puede_pedir_info_financiera(db, cred, red):
    cred.client_secret_encrypted = None
    db.commit()

    with pytest.raises(HTTPException) as e:
        token_manager.get_valid_token(db, INFO_FINANCIERA)
    assert e.value.status_code == 400
    assert "client_secret" in e.value.detail
    assert red.llamadas == []


def test_sin_usuario_no_se_puede_pedir_transferencias(db, cred, red):
    cred.password_encrypted = None
    db.commit()

    with pytest.raises(HTTPException) as e:
        token_manager.get_valid_token(db, TRANSFERENCIAS_CONFECCION)
    assert e.value.status_code == 400
    assert "usuario/contraseña" in e.value.detail


# ────────────────────────── Errores del proveedor ──────────────────────────────

@pytest.mark.parametrize("status", [401, 500])
def test_el_error_http_del_proveedor_se_traduce_a_502(db, cred, red, status):
    red.token(status=status, body={"error": "invalid_client"})

    with pytest.raises(HTTPException) as e:
        token_manager.get_valid_token(db, INFO_FINANCIERA)

    assert e.value.status_code == 502
    assert "Error al obtener token de Interbanking (info-financiera)" in e.value.detail
    assert db.query(InterbankingToken).count() == 0


def test_el_timeout_del_proveedor_se_traduce_a_502(db, cred, red):
    red.token(error=httpx.TimeoutException("tardó demasiado"))

    with pytest.raises(HTTPException) as e:
        token_manager.get_valid_token(db, INFO_FINANCIERA)

    assert e.value.status_code == 502
    assert "tardó demasiado" in e.value.detail


def test_el_pedido_de_token_queda_auditado_sin_secretos(db, cred, red):
    red.token(body={"access_token": "tok-secreto", "token_type": "Bearer", "expires_in": 60})

    token_manager.get_valid_token(db, INFO_FINANCIERA, user_id=7)

    log = db.query(ApiAuditLog).one()
    assert log.operation == "OBTENER_TOKEN[info-financiera]"
    assert (log.endpoint, log.http_method, log.success) == ("/cas/oidc/accessToken", "POST", True)
    assert log.credential_id == cred.id and log.user_id == 7
    assert log.request_payload == {"client_id": "cli-123", "grant_type": "client_credentials",
                                   "scope": "info-financiera", "username": "usuario.ib"}
    # Ni el secreto ni el access_token se guardan en la auditoría.
    assert log.response_payload == {"token_type": "Bearer"}
    assert "secreto-cc" not in str(log.request_payload)


def test_el_token_fallido_queda_auditado_con_el_error(db, cred, red):
    red.token(status=401, body={"error": "invalid_client"})

    with pytest.raises(HTTPException):
        token_manager.get_valid_token(db, TRANSFERENCIAS_CONFECCION, user_id=3)

    log = db.query(ApiAuditLog).one()
    assert log.success is False and log.response_status == 401
    assert log.response_payload is None and log.error_message
    assert log.operation == "OBTENER_TOKEN[transferencias-confeccion]"


def test_respuesta_200_sin_access_token_rompe_con_keyerror(db, cred, red):
    # TODO(bug): token_manager.py:137 asume que un 200 siempre trae "access_token".
    # Si el proveedor responde 200 con otro cuerpo el KeyError sube sin traducir y
    # el módulo devuelve 500 en vez de 502. Se testea el comportamiento ACTUAL.
    red.token(body={"token_type": "Bearer", "expires_in": 3600})

    with pytest.raises(KeyError):
        token_manager.get_valid_token(db, INFO_FINANCIERA)


# ──────────────────────────── Estado de los tokens ─────────────────────────────

def test_estado_de_tokens_sin_credencial(db):
    assert token_manager.get_token_status(db) == {"tokens": []}


def test_estado_de_tokens_informa_los_dos_scopes(db, cred):
    _token_vigente(db, cred, INFO_FINANCIERA, minutos=30)

    estado = token_manager.get_token_status(db)["tokens"]

    por_scope = {t["scope"]: t for t in estado}
    assert set(por_scope) == {INFO_FINANCIERA, TRANSFERENCIAS_CONFECCION}
    assert por_scope[INFO_FINANCIERA]["has_active_token"] is True
    assert 28 <= por_scope[INFO_FINANCIERA]["minutes_remaining"] <= 30
    assert por_scope[TRANSFERENCIAS_CONFECCION] == {"scope": TRANSFERENCIAS_CONFECCION,
                                                    "has_active_token": False}


def test_un_token_vencido_figura_como_inactivo(db, cred):
    _token_vigente(db, cred, INFO_FINANCIERA, minutos=-10)

    estado = {t["scope"]: t for t in token_manager.get_token_status(db)["tokens"]}

    assert estado[INFO_FINANCIERA]["has_active_token"] is False
    assert estado[INFO_FINANCIERA]["minutes_remaining"] == 0
