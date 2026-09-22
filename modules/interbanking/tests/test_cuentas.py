"""Cuentas, saldos y movimientos contra la API Información Financiera.

Toda llamada al proveedor está mockeada; se verifican los parámetros que se le
mandan, los headers de identificación y la traducción de sus errores.
"""
import httpx
import pytest

from app.models.audit_log import ApiAuditLog

BASE = "/api/interbanking/cuentas"

CUENTAS = {"accounts": [
    {"account_number": "46600513539", "account_type": "CC", "bank_id": "011",
     "cbu": "0110599520000046600513", "currency": "ARS"},
]}


@pytest.fixture
def ib_ok(red):
    """Token válido y respuesta genérica de la API de cuentas."""
    red.token()
    return red


# ─────────────────────────── Identidad del gateway ─────────────────────────────

def test_sin_header_de_usuario_no_se_puede_operar(client, cred, ib_ok):
    # El gateway siempre inyecta X-User-Id: sin él FastAPI corta con 422.
    r = client.get(BASE)
    assert r.status_code == 422
    assert ib_ok.llamadas == []


def test_header_de_usuario_no_numerico_es_401(client, cred, ib_ok):
    r = client.get(BASE, headers={"X-User-Id": "no-soy-un-id"})
    assert r.status_code == 401 and "X-User-Id" in r.json()["detail"]


# ─────────────────────────────── Listado de cuentas ────────────────────────────

def test_listar_cuentas_manda_customer_id_y_headers_de_la_credencial(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", body=CUENTAS)

    r = client.get(f"{BASE}?account-type=CC&currency=ARS&limit=10&page=2", headers=h)

    assert r.status_code == 200 and r.json() == CUENTAS
    pedido = ib_ok.llamadas_a("/v1/accounts")[0]
    assert pedido["method"] == "GET"
    assert pedido["url"] == "https://api.ib.test/v1/accounts"
    assert pedido["params"] == {"customer-id": "CUST-1", "account-type": "CC",
                                "currency": "ARS", "limit": 10, "page": 2}
    assert pedido["headers"]["Authorization"].startswith("Bearer tok-")
    assert pedido["headers"]["client_id"] == "cli-123"
    assert pedido["headers"]["service"] == "https://api.ib.test/svc"


def test_listar_cuentas_acepta_override_de_customer_id_y_banco(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", body=CUENTAS)

    client.get(f"{BASE}?customer-id=OTRO&bank-number=011", headers=h)

    assert ib_ok.llamadas_a("/v1/accounts")[0]["params"]["customer-id"] == "OTRO"
    assert ib_ok.llamadas_a("/v1/accounts")[0]["params"]["bank-number"] == "011"


def test_sin_credenciales_cargadas_el_modulo_responde_503(client, ib_ok, h):
    r = client.get(BASE, headers=h)
    assert r.status_code == 503 and "No hay credenciales" in r.json()["detail"]


def test_sin_customer_id_configurado_responde_400(client, db, cred, ib_ok, h):
    cred.customer_id = None
    db.commit()

    r = client.get(BASE, headers=h)

    assert r.status_code == 400 and "customer_id no configurado" in r.json()["detail"]


def test_detalle_de_cuenta(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts/46600513539", body=CUENTAS)

    r = client.get(f"{BASE}/46600513539?account-type=CC&bank-number=011&currency=ARS",
                   headers=h)

    assert r.status_code == 200
    pedido = ib_ok.llamadas_a("/v1/accounts/46600513539")[0]
    assert pedido["url"] == "https://api.ib.test/v1/accounts/46600513539"
    assert pedido["params"]["account-type"] == "CC"


# ──────────────────────────────────── Saldos ───────────────────────────────────

def test_saldos_acepta_varias_cuentas_y_rango_de_fechas(client, cred, ib_ok, h):
    saldos = {"balances": [{"account_number": "46600513539", "balance": 1250.5}]}
    ib_ok.ruta("/v1/accounts/balances", body=saldos)

    r = client.get(f"{BASE}/saldos?account-number=111&account-number=222&bank-number=011"
                   f"&account-type=CC&currency=ARS&date-since=2026-01-01&date-until=2026-01-31",
                   headers=h)

    assert r.status_code == 200 and r.json() == saldos
    params = ib_ok.llamadas_a("/v1/accounts/balances")[0]["params"]
    assert params["account-number"] == ["111", "222"]
    assert params["date-since"] == "2026-01-01" and params["date-until"] == "2026-01-31"
    assert params["customer-id"] == "CUST-1"


# ───────────────────────────────── Movimientos ─────────────────────────────────

def test_movimientos_usa_el_segmento_pedido(client, cred, ib_ok, h):
    ib_ok.ruta("/movements/dia", body={"movements_detail": [{"id": 1, "amount": 10}]})

    r = client.get(f"{BASE}/46600513539/movimientos?tipo=dia&account-type=CC", headers=h)

    assert r.status_code == 200
    assert ib_ok.llamadas_a("/movements/dia")[0]["url"].endswith(
        "/v1/accounts/46600513539/movements/dia")


def test_movimientos_historicos_por_defecto(client, cred, ib_ok, h):
    ib_ok.ruta("/movements/anteriores", body={"movements_detail": []})

    client.get(f"{BASE}/46600513539/movimientos?date-since=2026-01-01&date-until=2026-01-05",
               headers=h)

    params = ib_ok.llamadas_a("/movements/anteriores")[0]["params"]
    assert params == {"customer-id": "CUST-1", "date-since": "2026-01-01",
                      "date-until": "2026-01-05", "limit": 100, "page": 0}


def test_movimientos_fuera_de_la_ventana_de_retencion_devuelven_lista_vacia(client, cred, ib_ok, h):
    """La API sólo retiene ~6 meses: fuera de ventana responde 200 sin movimientos,
    no un error. El módulo debe devolver la lista vacía tal cual."""
    ib_ok.ruta("/movements/anteriores",
               body={"movements_detail": [], "general_data": {"total_rows": 0}})

    r = client.get(f"{BASE}/46600513539/movimientos"
                   f"?date-since=2019-01-01&date-until=2019-01-31", headers=h)

    assert r.status_code == 200
    assert r.json()["movements_detail"] == []


# ─────────────────────── Errores del proveedor y auditoría ─────────────────────

def test_el_401_del_proveedor_se_propaga(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", status=401, body={"message": "token rechazado"})

    r = client.get(BASE, headers=h)

    assert r.status_code == 401
    assert "token rechazado" in r.json()["detail"]
    assert "https://api.ib.test/v1/accounts" in r.json()["detail"]


def test_el_500_del_proveedor_se_propaga_con_el_cuerpo_crudo(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", status=500, texto="<html>Internal Server Error</html>")

    r = client.get(BASE, headers=h)

    assert r.status_code == 500
    assert "Internal Server Error" in r.json()["detail"]


def test_el_timeout_del_proveedor_es_502(client, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", error=httpx.ReadTimeout("se colgó"))

    r = client.get(BASE, headers=h)

    assert r.status_code == 502 and "se colgó" in r.json()["detail"]


def test_cada_llamada_queda_auditada_con_ip_y_payload(client, db, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", body=CUENTAS)

    client.get(BASE, headers={**h, "X-Forwarded-For": "200.1.2.3, 10.0.0.1"})

    logs = {l.operation: l for l in db.query(ApiAuditLog).all()}
    assert set(logs) == {"OBTENER_TOKEN[info-financiera]", "LISTAR_CUENTAS"}
    llamada = logs["LISTAR_CUENTAS"]
    assert llamada.success is True and llamada.response_status == 200
    assert llamada.endpoint == "/v1/accounts" and llamada.http_method == "GET"
    assert llamada.user_id == 7 and llamada.credential_id == cred.id
    assert llamada.ip_address == "200.1.2.3"          # primer hop del X-Forwarded-For
    assert llamada.response_payload == CUENTAS
    assert llamada.duration_ms is not None


def test_la_llamada_fallida_queda_auditada_como_error(client, db, cred, ib_ok, h):
    ib_ok.ruta("/v1/accounts", status=500, body={"message": "boom"})

    client.get(BASE, headers=h)

    fallida = db.query(ApiAuditLog).filter_by(operation="LISTAR_CUENTAS").one()
    assert fallida.success is False and fallida.response_status == 500
    assert "boom" in fallida.error_message
    assert fallida.ip_address == "testclient"         # sin X-Forwarded-For
