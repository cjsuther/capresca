"""Configuración de Interbanking: alta de credenciales (secretos cifrados),
prueba de conexión por scope y estado de los tokens."""
from datetime import datetime, timedelta, timezone

import httpx

from app.config import decrypt_secret, encrypt_secret
from app.models.credentials import InterbankingCredential
from app.models.tokens import InterbankingToken
from app.scopes import INFO_FINANCIERA, TRANSFERENCIAS_CONFECCION

BASE = "/api/interbanking/config"

ALTA = {
    "name": "Capresca",
    "base_url": "https://api.ib.test",
    "auth_url": "https://auth.ib.test",
    "client_id": "cli-123",
    "client_secret": "secreto-cc",
    "username": "usuario.ib",
    "password": "pass-ib",
    "service_url": "https://api.ib.test/svc",
    "customer_id": "CUST-1",
    "consolidation_account_number": "46600513539",
    "payment_account_number": "99900011122",
}


# ───────────────────────────────── Cifrado ─────────────────────────────────────

def test_el_cifrado_es_reversible_y_no_deja_texto_plano():
    cifrado = encrypt_secret("pass-ib")
    assert cifrado != "pass-ib" and "pass-ib" not in cifrado
    assert decrypt_secret(cifrado) == "pass-ib"


def test_dos_cifrados_del_mismo_secreto_son_distintos():
    # Fernet usa IV + timestamp: el ciphertext nunca se repite.
    assert encrypt_secret("hola") != encrypt_secret("hola")


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "interbanking"}


# ───────────────────────── Alta y lectura de credenciales ──────────────────────

def test_sin_configuracion_activa_devuelve_404(client):
    r = client.get(BASE)
    assert r.status_code == 404 and r.json()["detail"] == "No hay configuración activa"


def test_alta_guarda_los_secretos_cifrados(client, db):
    r = client.post(BASE, json=ALTA)
    assert r.status_code == 200

    body = r.json()
    assert body["has_client_secret"] is True and body["has_password"] is True
    # La respuesta nunca expone los secretos.
    assert "client_secret" not in body and "password" not in body
    assert "secreto-cc" not in r.text and "pass-ib" not in r.text

    cred = db.query(InterbankingCredential).one()
    assert cred.client_secret_encrypted not in (None, "secreto-cc")
    assert cred.password_encrypted not in (None, "pass-ib")
    assert decrypt_secret(cred.client_secret_encrypted) == "secreto-cc"
    assert decrypt_secret(cred.password_encrypted) == "pass-ib"


def test_alta_persiste_las_cuentas_de_consolidacion_y_pagos(client, db):
    client.post(BASE, json=ALTA)
    body = client.get(BASE).json()
    assert body["consolidation_account_number"] == "46600513539"
    assert body["consolidation_account_type"] == "CC"
    assert body["consolidation_bank_number"] == "011"
    assert body["payment_account_number"] == "99900011122"
    assert body["customer_id"] == "CUST-1" and body["username"] == "usuario.ib"


def test_regrabar_sin_secretos_conserva_los_guardados(client, db):
    client.post(BASE, json=ALTA)
    sin_secretos = {**ALTA, "client_secret": "", "password": ""}

    body = client.post(BASE, json=sin_secretos).json()

    assert body["has_client_secret"] is True and body["has_password"] is True
    activa = db.query(InterbankingCredential).filter_by(is_active=True).one()
    assert decrypt_secret(activa.client_secret_encrypted) == "secreto-cc"
    assert decrypt_secret(activa.password_encrypted) == "pass-ib"


def test_cambiar_de_client_id_no_hereda_el_secreto_anterior(client, db):
    client.post(BASE, json=ALTA)

    body = client.post(BASE, json={**ALTA, "client_id": "otro-cli",
                                   "client_secret": "", "username": "otro.user",
                                   "password": ""}).json()

    assert body["has_client_secret"] is False and body["has_password"] is False


def test_el_alta_desactiva_la_credencial_previa_y_sus_tokens(client, db):
    client.post(BASE, json=ALTA)
    vieja = db.query(InterbankingCredential).one()
    db.add(InterbankingToken(credential_id=vieja.id, scope=INFO_FINANCIERA,
                             access_token="tok", expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
                             is_active=True))
    db.commit()

    client.post(BASE, json={**ALTA, "name": "Capresca v2"})

    activas = db.query(InterbankingCredential).filter_by(is_active=True).all()
    assert [c.name for c in activas] == ["Capresca v2"]
    assert db.query(InterbankingToken).one().is_active is False


def test_el_alta_valida_los_campos_obligatorios(client):
    assert client.post(BASE, json={"name": "sin urls"}).status_code == 422


# ─────────────────────────── Prueba de conexión (/test) ────────────────────────

def test_probar_conexion_info_financiera(client, red):
    red.token(body={"access_token": "tok-de-prueba-largo-123456", "expires_in": 900})

    r = client.post(f"{BASE}/test?scope={INFO_FINANCIERA}", json=ALTA).json()

    assert r == {"success": True, "scope": INFO_FINANCIERA,
                 "token_preview": "tok-de-prueba-largo-...", "expires_in": 900}
    pedido = red.ultima
    assert pedido["url"] == "https://auth.ib.test/cas/oidc/accessToken"
    assert pedido["data"]["grant_type"] == "client_credentials"
    assert pedido["params"] == {"scope": INFO_FINANCIERA}


def test_probar_conexion_transferencias_usa_password(client, red):
    red.token()

    r = client.post(f"{BASE}/test?scope={TRANSFERENCIAS_CONFECCION}", json=ALTA).json()

    assert r["success"] is True and r["scope"] == TRANSFERENCIAS_CONFECCION
    assert red.ultima["data"] == {"grant_type": "password", "username": "usuario.ib",
                                  "password": "pass-ib", "client_id": "cli-123"}


def test_probar_conexion_con_scope_invalido(client):
    r = client.post(f"{BASE}/test?scope=inventado", json=ALTA)
    assert r.status_code == 400 and "Scope inválido" in r.json()["detail"]


def test_probar_conexion_sin_client_secret(client, red):
    r = client.post(f"{BASE}/test", json={**ALTA, "client_secret": ""}).json()
    assert r == {"success": False, "error": "Falta client_secret para info-financiera"}
    assert red.llamadas == []


def test_probar_conexion_sin_usuario_ni_password(client, red):
    r = client.post(f"{BASE}/test?scope={TRANSFERENCIAS_CONFECCION}",
                    json={**ALTA, "username": "", "password": ""}).json()
    assert r == {"success": False,
                 "error": "Faltan usuario/contraseña para transferencias-confeccion"}
    assert red.llamadas == []


def test_probar_conexion_completa_los_secretos_guardados(client, red):
    """El form no reenvía los secretos: se toman los de la credencial activa."""
    client.post(BASE, json=ALTA)
    red.token()

    r = client.post(f"{BASE}/test", json={**ALTA, "client_secret": ""}).json()

    assert r["success"] is True
    assert red.ultima["data"]["client_secret"] == "secreto-cc"


def test_probar_conexion_completa_usuario_y_password_guardados(client, red):
    client.post(BASE, json=ALTA)
    red.token()

    client.post(f"{BASE}/test?scope={TRANSFERENCIAS_CONFECCION}",
                json={**ALTA, "password": "", "username": ""})

    assert red.ultima["data"]["username"] == "usuario.ib"
    assert red.ultima["data"]["password"] == "pass-ib"


def test_probar_conexion_informa_el_error_del_proveedor(client, red):
    red.token(status=401, body={"error": "invalid_client"})

    r = client.post(f"{BASE}/test", json=ALTA).json()

    assert r["success"] is False and r["scope"] == INFO_FINANCIERA
    assert "401" in r["error"]


def test_probar_conexion_informa_el_timeout(client, red):
    red.token(error=httpx.ConnectTimeout("sin respuesta"))

    r = client.post(f"{BASE}/test", json=ALTA).json()

    assert r["success"] is False and "sin respuesta" in r["error"]


# ───────────────────────────── Estado de tokens ────────────────────────────────

def test_token_status_sin_credenciales(client):
    assert client.get(f"{BASE}/token-status").json() == {"tokens": []}


def test_token_status_lista_los_dos_scopes(client, db, cred):
    db.add(InterbankingToken(credential_id=cred.id, scope=INFO_FINANCIERA,
                             access_token="tok", expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
                             is_active=True))
    db.commit()

    tokens = {t["scope"]: t for t in client.get(f"{BASE}/token-status").json()["tokens"]}

    assert tokens[INFO_FINANCIERA]["has_active_token"] is True
    assert tokens[INFO_FINANCIERA]["minutes_remaining"] > 0
    assert tokens[TRANSFERENCIAS_CONFECCION]["has_active_token"] is False
