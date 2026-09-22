"""Endpoints internos que consume conciliación (sin identidad de usuario: van por
la red interna, no por el gateway)."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models.transfers import Transfer

BASE = "/internal/interbanking"


def _movimiento(**kw):
    base = {
        "id": "1001", "amount": "25000.50", "debit_credit_type": "C",
        "movement_date": "2026-03-15T00:00:00", "customer_cuit": " 30-12345678-9 ",
        "depositor_description": "LOTERIA EL DORADO",
        "code_description_ib": "TRANSFERENCIA RECIBIDA",
    }
    base.update(kw)
    return base


# ──────────────────────────── Cuentas configuradas ─────────────────────────────

def test_cuenta_de_consolidacion_sin_configurar_es_null(client):
    assert client.get(f"{BASE}/consolidation-account").json() is None


def test_cuenta_de_consolidacion_configurada(client, cred):
    assert client.get(f"{BASE}/consolidation-account").json() == {
        "account_number": "46600513539", "account_type": "CC",
        "bank_number": "011", "currency": "ARS"}


def test_cuenta_de_consolidacion_usa_defaults_si_faltan_datos(client, db, cred):
    cred.consolidation_account_type = None
    cred.consolidation_bank_number = None
    cred.consolidation_currency = None
    db.commit()

    r = client.get(f"{BASE}/consolidation-account").json()

    assert r == {"account_number": "46600513539", "account_type": "CC",
                 "bank_number": "011", "currency": "ARS"}


def test_cuenta_de_pagos_sin_configurar_es_null(client, db, cred):
    cred.payment_account_number = None
    db.commit()
    assert client.get(f"{BASE}/payment-account").json() is None


def test_cuenta_de_pagos_configurada(client, cred):
    assert client.get(f"{BASE}/payment-account").json() == {
        "account_number": "99900011122", "account_type": "CC",
        "bank_number": "011", "currency": "ARS"}


# ─────────────────────────────── Pagos salientes ───────────────────────────────

def test_pago_saliente_sin_cuenta_configurada_es_400(client):
    r = client.post(f"{BASE}/payments", json={"cbu_destino": "0" * 22, "monto": 100})
    assert r.status_code == 400
    assert "cuenta de pagos salientes" in r.json()["detail"]


def test_pago_saliente_crea_la_transferencia_desde_la_cuenta_de_pagos(client, db, cred, red):
    r = client.post(f"{BASE}/payments", json={
        "cbu_destino": "0070068930004021957614", "monto": 75000.25,
        "moneda": "ARS", "concepto": "Pago agencia A005"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PENDING_AUTHORIZATION"
    assert body["id_operacion_ib"].startswith("OP-")

    guardada = db.query(Transfer).one()
    assert guardada.id == body["id"]
    assert guardada.cuenta_origen == "011/99900011122/CC"
    assert guardada.monto == Decimal("75000.25")
    assert guardada.initiated_by == 0          # llamada máquina-a-máquina
    assert red.llamadas == []                  # modo mock: no sale a la red


def test_pago_saliente_usa_el_concepto_por_defecto(client, db, cred):
    client.post(f"{BASE}/payments", json={"cbu_destino": "0" * 22, "monto": 10})
    assert db.query(Transfer).one().concepto == "Pago Capresca"


def test_estado_de_un_pago_saliente(client, db, cred, red):
    """Tesorería consulta el estado de lo que envió; en modo mock el banco responde ACREDITADA."""
    body = client.post(f"{BASE}/payments", json={"cbu_destino": "0" * 22, "monto": 10}).json()
    r = client.get(f"{BASE}/payments/{body['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == body["id"] and r.json()["id_operacion_ib"] == body["id_operacion_ib"]
    assert r.json()["status"] in ("PENDING_AUTHORIZATION", "ACREDITADA")
    assert client.get(f"{BASE}/payments/99999").status_code == 404


# ──────────────────────── Transferencias del día (matcher) ─────────────────────

def test_transacciones_del_dia_filtra_por_fecha(client, db):
    db.add(Transfer(cbu_destino="0070068930004021957614", monto=Decimal("135000.00"),
                    concepto="PAGO QUINIELA", status="ACREDITADA", id_operacion_ib="OP-1",
                    initiated_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)))
    db.add(Transfer(cbu_destino="0140018920000045678904", monto=Decimal("1.00"),
                    concepto="otro día", status="ACREDITADA",
                    initiated_at=datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)))
    db.commit()

    r = client.get(f"{BASE}/transactions?date=2026-03-15").json()

    assert r == [{"id": r[0]["id"], "type": "transfer", "date": "2026-03-15",
                  "cbu": "0070068930004021957614", "concepto": "PAGO QUINIELA",
                  "amount": 135000.0, "status_ib": "ACREDITADA", "id_operacion_ib": "OP-1"}]


def test_transacciones_sin_movimientos_devuelve_lista_vacia(client):
    assert client.get(f"{BASE}/transactions?date=2026-03-15").json() == []


def test_transacciones_sin_monto_devuelve_cero(client, db):
    db.add(Transfer(cbu_destino="0" * 22, monto=None, status="INICIADA",
                    initiated_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)))
    db.commit()

    assert client.get(f"{BASE}/transactions?date=2026-03-15").json()[0]["amount"] == 0.0


# ───────────────── Movimientos bancarios normalizados (matcher) ────────────────

def test_movimientos_devuelve_solo_los_creditos_normalizados(client, cred, red):
    red.token()
    red.ruta("/movements/anteriores", body={"movements_detail": [
        _movimiento(),
        _movimiento(id="1002", debit_credit_type="D", amount="999"),   # débito: se ignora
    ]})

    r = client.get(f"{BASE}/movements?date=2026-03-15&account_number=46600513539").json()

    assert r == [{
        "id": 1001, "type": "movement", "date": "2026-03-15", "cbu": None,
        "cuit": "30-12345678-9", "depositor": "LOTERIA EL DORADO",
        "concepto": "TRANSFERENCIA RECIBIDA", "amount": 25000.5, "debit_credit": "C",
    }]
    params = red.llamadas_a("/movements/anteriores")[0]["params"]
    assert params["date-since"] == "2026-03-15" and params["date-until"] == "2026-03-15"
    assert params["customer-id"] == "CUST-1" and params["limit"] == 500


def test_movimientos_acepta_override_de_cuenta_y_customer(client, cred, red):
    red.token()
    red.ruta("/movements/anteriores", body={"movements_detail": []})

    client.get(f"{BASE}/movements?date=2026-03-15&account_number=123"
               f"&account-type=CA&bank-number=017&currency=USD&customer-id=OTRO")

    llamada = red.llamadas_a("/movements/anteriores")[0]
    assert llamada["url"].endswith("/v1/accounts/123/movements/anteriores")
    assert llamada["params"]["account-type"] == "CA"
    assert llamada["params"]["bank-number"] == "017"
    assert llamada["params"]["currency"] == "USD"
    assert llamada["params"]["customer-id"] == "OTRO"


def test_movimientos_fuera_de_la_ventana_de_retencion_es_lista_vacia(client, cred, red):
    """Interbanking retiene ~6 meses: más atrás responde 200 con `movements_detail`
    vacío (no un error) y el endpoint devuelve [] sin romper la consolidación."""
    red.token()
    red.ruta("/movements/anteriores", body={"movements_detail": [], "general_data": {}})

    r = client.get(f"{BASE}/movements?date=2019-01-01&account_number=46600513539")

    assert r.status_code == 200 and r.json() == []


def test_movimientos_sin_movements_detail_es_lista_vacia(client, cred, red):
    red.token()
    red.ruta("/movements/anteriores", body={"general_data": {}})

    assert client.get(f"{BASE}/movements?date=2026-03-15&account_number=1").json() == []


def test_movimientos_con_id_no_numerico_usa_un_hash_estable(client, cred, red):
    red.token()
    red.ruta("/movements/anteriores", body={"movements_detail": [
        _movimiento(id="MOV-ABC"),
    ]})

    primero = client.get(f"{BASE}/movements?date=2026-03-15&account_number=1").json()[0]
    segundo = client.get(f"{BASE}/movements?date=2026-03-15&account_number=1").json()[0]

    assert isinstance(primero["id"], int) and primero["id"] == segundo["id"]


def test_movimientos_tolera_importes_y_fechas_ausentes(client, cred, red):
    red.token()
    red.ruta("/movements/anteriores", body={"movements_detail": [{
        "debit_credit_type": "c", "amount": "no-es-un-numero", "id": None,
        "code_description_bank": "DEPOSITO EN EFECTIVO",
    }]})

    m = client.get(f"{BASE}/movements?date=2026-03-15&account_number=1").json()[0]

    assert m["amount"] == 0.0            # importe ilegible → 0
    assert m["id"] == 0                  # sin id → 0
    assert m["date"] == "2026-03-15"     # sin fecha → la pedida
    assert m["cuit"] == ""
    assert m["concepto"] == "DEPOSITO EN EFECTIVO"


def test_movimientos_sin_credenciales_es_503(client):
    r = client.get(f"{BASE}/movements?date=2026-03-15&account_number=1")
    assert r.status_code == 503


# ───────────────────── Cuenta de origen elegible (Tesorería) ────────────────────

def test_pago_saliente_desde_la_cuenta_elegida(client, db, cred):
    """Tesorería elige desde qué cuenta sale el lote; sin elección, la configurada."""
    r = client.post(f"{BASE}/payments", json={"cbu_destino": "0" * 22, "monto": 10, "cuenta_origen": "12345678901",
                                              "cuenta_origen_tipo": "CA", "cuenta_origen_banco": "017"})
    assert r.status_code == 200, r.text
    assert db.query(Transfer).filter_by(id=r.json()["id"]).one().cuenta_origen == "017/12345678901/CA"

    r2 = client.post(f"{BASE}/payments", json={"cbu_destino": "0" * 22, "monto": 10, "cuenta_origen": "12345678901"})
    assert db.query(Transfer).filter_by(id=r2.json()["id"]).one().cuenta_origen == "011/12345678901/CC"  # defaults


def test_cuentas_para_pagar_sin_credenciales(client):
    assert client.get(f"{BASE}/payment-accounts").json() == {
        "items": [], "error": "No hay credenciales de Interbanking configuradas"}


def test_cuentas_para_pagar_marca_la_configurada(client, cred, red):
    """Sin customer-id no se consulta al banco, pero la configurada siempre está."""
    cred.customer_id = None
    r = client.get(f"{BASE}/payment-accounts").json()
    assert r["items"] == [{"account_number": "99900011122", "account_type": "CC", "bank_number": "011",
                           "currency": "ARS", "nombre": "Cuenta de pagos configurada", "predeterminada": True}]


def test_cuentas_para_pagar_lista_las_del_banco(client, cred, red):
    red.token()
    red.ruta("/accounts", body={"accounts": [
        {"account_number": "99900011122", "account_type": "CC", "bank_number": "011", "currency": "ARS",
         "description": "Cuenta pagos"},
        {"account_number": "46600513539", "account_type": "CA", "bank_number": "011", "currency": "USD"},
        {"description": "sin número: se ignora"},
    ]})

    r = client.get(f"{BASE}/payment-accounts").json()

    assert r["error"] == ""
    assert [(c["account_number"], c["predeterminada"]) for c in r["items"]] == [("99900011122", True), ("46600513539", False)]


def test_si_el_banco_no_responde_igual_se_puede_elegir_la_configurada(client, cred, red):
    red.token()
    red.ruta("/accounts", status=500)

    r = client.get(f"{BASE}/payment-accounts").json()

    assert [c["account_number"] for c in r["items"]] == ["99900011122"]
    assert "No se pudieron listar las cuentas" in r["error"]
