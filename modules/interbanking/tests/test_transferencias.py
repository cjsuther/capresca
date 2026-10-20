"""Transferencias: alta (modo mock y modo real), listado, validación de CBU,
estado y registro local."""
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.audit_log import ApiAuditLog
from app.models.transfers import Transfer

BASE = "/api/interbanking/transferencias"

NUEVA = {
    "cuenta_debito_account_number": "46600513539",
    "cuenta_debito_account_type": "CC",
    "cuenta_debito_bank_id": "011",
    "cbu_destino": "0070068930004021957614",
    "monto": "1500.50",
    "moneda": "ARS",
    "comentario": "Pago agencia A001",
}


# ───────────────────────────── Alta en modo mock ───────────────────────────────

def test_crear_transferencia_en_modo_mock_no_sale_a_la_red(client, db, red, h, notificaciones):
    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cbu_destino"] == "0070068930004021957614"
    assert body["status"] == "PENDING_AUTHORIZATION"
    assert body["id_operacion_ib"].startswith("OP-")
    assert body["cuenta_origen"] == "011/46600513539/CC"
    assert float(body["monto"]) == 1500.50
    assert red.llamadas == []

    guardada = db.query(Transfer).one()
    assert guardada.initiated_by == 7 and guardada.moneda == "ARS"
    assert guardada.concepto == "Pago agencia A001"
    assert guardada.last_status_payload["_mock"] is True


def test_el_alta_avisa_al_modulo_de_notificaciones(client, db, h, notificaciones):
    client.post(BASE, json=NUEVA, headers=h)

    assert len(notificaciones) == 1
    aviso = notificaciones[0]
    assert aviso["user_id"] == 7 and aviso["module"] == "interbanking"
    assert aviso["entity_type"] == "transfer"
    assert aviso["entity_id"] == db.query(Transfer).one().id
    assert "1500.50 ARS" in aviso["message"]


@pytest.mark.parametrize("cambio, campo", [
    ({"cuenta_debito_account_type": "XX"}, "cuenta_debito_account_type"),
    ({"moneda": "EUR"}, "moneda"),
    ({"cbu_destino": "123"}, "cbu_destino"),
    ({"comentario": ""}, "comentario"),
    ({"cuenta_debito_account_number": ""}, "cuenta_debito_account_number"),
])
def test_el_alta_valida_el_formulario(client, h, cambio, campo):
    r = client.post(BASE, json={**NUEVA, **cambio}, headers=h)
    assert r.status_code == 422
    assert campo in str(r.json()["detail"])


@pytest.mark.parametrize("monto", ["0", "-5"])
def test_el_monto_invalido_devuelve_422(monto, h):
    """El 422 se arma con jsonable_encoder: `ctx={'gt': Decimal('0')}` no es serializable y antes
    hacía terminar el request en 500."""
    from fastapi.testclient import TestClient
    from app.main import app

    sin_reraise = TestClient(app, raise_server_exceptions=False)
    r = sin_reraise.post(BASE, json={**NUEVA, "monto": monto}, headers=h)

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "monto"


# ──────────────────────────── Listado (Interbanking) ───────────────────────────

def test_listado_en_modo_mock_trae_las_transferencias_semilla(client, h):
    r = client.get(BASE, headers=h).json()

    assert r["mock"] is True and r["_mock"] is True
    assert len(r["transfers"]) == 3
    assert r["general_data"]["total_rows"] == 3
    assert {t["currency"] for t in r["transfers"]} == {"ARS", "USD"}


def test_el_listado_incluye_la_transferencia_recien_creada(client, h):
    client.post(BASE, json=NUEVA, headers=h)

    r = client.get(BASE, headers=h).json()

    assert r["general_data"]["total_rows"] == 4
    # orden desc por alta; las observaciones llevan quién la cargó (Interbanking sólo ve al operador de API)
    assert r["transfers"][0]["transfer_comments"] == "Pago agencia A001 - Cargo: cris"


def test_el_listado_pagina(client, h):
    r = client.get(f"{BASE}?page=0&rows=2", headers=h).json()
    assert len(r["transfers"]) == 2 and r["general_data"]["total_rows"] == 3

    r = client.get(f"{BASE}?page=1&rows=2", headers=h).json()
    assert len(r["transfers"]) == 1


def test_el_listado_filtra_por_fecha(client, h):
    ayer = "2020-01-01"
    r = client.get(f"{BASE}?date_since={ayer}&date_until={ayer}", headers=h).json()
    assert r["transfers"] == [] and r["general_data"]["total_rows"] == 0


def test_listado_real_pide_el_detalle_a_interbanking(client, cred, red, h, sin_mock):
    red.token()
    red.ruta("/v1/transfers/details", body={"transfers": [], "general_data": {}})

    r = client.get(f"{BASE}?date_since=2026-03-01&date_until=2026-03-31&page=1&rows=50",
                   headers=h)

    assert r.status_code == 200 and r.json()["mock"] is False
    params = red.llamadas_a("/v1/transfers/details")[0]["params"]
    assert params == {"customer-id": "CUST-1", "date-since": "2026-03-01",
                      "date-until": "2026-03-31", "page": 1, "limit": 50}


def test_listado_real_sin_fechas_usa_hoy(client, cred, red, h, sin_mock):
    red.token()
    red.ruta("/v1/transfers/details", body={"transfers": []})

    client.get(BASE, headers=h)

    hoy = date.today().isoformat()
    params = red.llamadas_a("/v1/transfers/details")[0]["params"]
    assert params["date-since"] == hoy and params["date-until"] == hoy


def test_listado_real_sin_customer_id_es_400(client, db, cred, red, h, sin_mock):
    cred.customer_id = None
    db.commit()
    red.token()

    r = client.get(BASE, headers=h)

    assert r.status_code == 400 and r.json()["detail"] == "customer_id no configurado"


# ────────────────────────────── Alta en modo real ──────────────────────────────

def _ruta_cuenta(red, cuentas):
    red.ruta("/v1/accounts/46600513539", body={"accounts": cuentas})


def test_alta_real_resuelve_el_cbu_debito_y_confecciona(client, db, cred, red, h, sin_mock):
    red.token()
    _ruta_cuenta(red, [
        {"account_number": "46600513539", "account_type": "CA", "bank_id": "011", "cbu": "9" * 22},
        {"account_number": "46600513539", "account_type": "CC", "bank_id": "011",
         "cbu": "0110599520000046600513"},
    ])
    red.ruta("/v1/transfers/confection/third-party", body={
        "operation_id": "OP-778",
        "found_transfers": [{"confection_id": "778", "status": "PENDING_AUTHORIZATION"}],
    })

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 200, r.text
    assert r.json()["id_operacion_ib"] == "OP-778"

    envio = red.llamadas_a("/v1/transfers/confection/third-party")[0]
    transferencia = envio["json"]["found_transfers"][0]
    assert transferencia["debit_account"] == {
        "bank_number": 11, "account_type": "CC", "currency": "ARS",
        "account_number": 46600513539, "account_cbu": "0110599520000046600513",
    }
    assert transferencia["credit_account"] == {
        "bank_number": 7, "currency": "ARS", "account_cbu": "0070068930004021957614",
    }
    assert transferencia["amount"] == 1500.50
    # El usuario de la plataforma va en las observaciones y queda en el registro local.
    assert transferencia["comments"] == f"{NUEVA['comentario']} - Cargo: cris"
    assert envio["json"]["description"] == NUEVA["comentario"]
    assert db.query(Transfer).one().cargado_por == "cris" and r.json()["cargado_por"] == "cris"
    assert transferencia["request_date"] == datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
    assert envio["json"]["unified_send"] is True
    # Producción exige confection_id (error 1005 si falta) de hasta 7 dígitos (1007): es el id local.
    assert transferencia["confection_id"] == r.json()["id"]
    assert len(str(transferencia["confection_id"])) <= 7
    assert envio["json"]["payment_number"] == transferencia["confection_id"]

    # Cada scope pidió su propio token: info-financiera para la cuenta, password para el envío.
    grants = [ll["data"]["grant_type"] for ll in red.llamadas_a("/cas/oidc/accessToken")]
    assert sorted(grants) == ["client_credentials", "password"]


def test_alta_real_lee_el_cbu_debito_con_los_nombres_de_la_api_productiva(client, cred, red, h, sin_mock):
    """Interbanking productivo responde `account_cbu` y `bank_number` (no `cbu` / `bank_id`)."""
    red.token()
    _ruta_cuenta(red, [
        {"account_number": "46600513539", "account_type": "CA", "bank_number": "011", "account_cbu": "9" * 22},
        {"account_number": "46600513539", "account_type": "CC", "bank_number": "011",
         "account_cbu": "0110599520000046600513", "account_cuit": "30999999999", "account_label": "CAJA",
         "bank_name": "NACION", "currency": "ARS"},
    ])
    red.ruta("/v1/transfers/confection/third-party", body={"operation_id": "OP-9", "found_transfers": [{}]})

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 200, r.text
    envio = red.llamadas_a("/v1/transfers/confection/third-party")[0]
    assert envio["json"]["found_transfers"][0]["debit_account"]["account_cbu"] == "0110599520000046600513"


def test_alta_real_cae_a_la_primera_cuenta_si_no_matchea_el_tipo(client, cred, red, h, sin_mock):
    red.token()
    _ruta_cuenta(red, [{"account_number": "46600513539", "account_type": "CA",
                        "bank_id": "999", "cbu": "1110599520000046600513"}])
    red.ruta("/v1/transfers/confection/third-party", body={"operation_id": "OP-1",
                                                           "found_transfers": [{}]})

    client.post(BASE, json=NUEVA, headers=h)

    envio = red.llamadas_a("/v1/transfers/confection/third-party")[0]
    assert envio["json"]["found_transfers"][0]["debit_account"]["account_cbu"] == "1110599520000046600513"


def test_alta_real_sin_cbu_debito_resoluble_es_400(client, db, cred, red, h, sin_mock):
    red.token()
    _ruta_cuenta(red, [])

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 400
    assert "No se pudo resolver el CBU de la cuenta débito" in r.json()["detail"]
    assert db.query(Transfer).count() == 0


def test_alta_real_con_la_cuenta_debito_caida_es_400(client, db, cred, red, h, sin_mock):
    """Si /v1/accounts falla, el CBU no se resuelve y el alta corta antes de confeccionar."""
    red.token()
    red.ruta("/v1/accounts/46600513539", status=500, body={"message": "cuentas caído"})

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 400
    assert "No se pudo resolver el CBU" in r.json()["detail"]
    assert red.llamadas_a("/confection/third-party") == []
    assert db.query(Transfer).count() == 0


def test_listado_remoto_filtra_por_cbu_de_origen_y_destino(db, cred, red, sin_mock):
    """Filtros que existen en el service pero que el router todavía no expone."""
    from app.services import transfer_service

    red.token()
    red.ruta("/v1/transfers/details", body={"transfers": []})

    transfer_service.listar_transferencias_remoto(
        db=db, user_id=7, date_since="2026-03-01", date_until="2026-03-31",
        debit_cbu="0110599520000046600513", credit_cbu="0070068930004021957614")

    params = red.llamadas_a("/v1/transfers/details")[0]["params"]
    assert params["debit-account-number"] == "0110599520000046600513"
    assert params["credit-account-number"] == "0070068930004021957614"


def test_el_mock_filtra_por_cuenta_de_debito_y_credito():
    from app.services import mock_transfers

    mock_transfers.crear_transferencia(
        amount="100.00", currency="ARS", comments="test", credit_cbu="0" * 22,
        debit_account_number="99900011122")

    solo_debito = mock_transfers.listar_transferencias(
        customer_id="MOCK", debit_account_number="99900011122")
    assert [t["debit_account"]["account_number"] for t in solo_debito["transfers"]] == \
        ["99900011122"]

    sin_match = mock_transfers.listar_transferencias(
        customer_id="MOCK", credit_account_number="no-existe")
    assert sin_match["transfers"] == [] and sin_match["general_data"]["total_rows"] == 0


def test_alta_real_con_error_del_proveedor_queda_en_error(client, db, cred, red, h, sin_mock):
    red.token()
    _ruta_cuenta(red, [{"account_number": "46600513539", "account_type": "CC",
                        "bank_id": "011", "cbu": "0110599520000046600513"}])
    red.ruta("/v1/transfers/confection/third-party", status=500,
             body={"message": "confección rechazada"})

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code == 500 and "confección rechazada" in r.json()["detail"]
    assert db.query(Transfer).one().status == "ERROR"
    fallida = db.query(ApiAuditLog).filter_by(operation="CREAR_TRANSFERENCIA").one()
    assert fallida.success is False


# ────────────────────────────── Validación de CBU ──────────────────────────────

def test_validar_cbu_en_modo_mock(client, red, h):
    r = client.post(f"{BASE}/validar", json={"cbu_or_alias": "0070068930004021957614"},
                    headers=h).json()

    assert r == {"cbu": "0070068930004021957614", "titular": "Titular MOCK",
                 "banco": "Banco Mock S.A.", "tipo_cuenta": "CC", "_mock": True}
    assert red.llamadas == []


def test_validar_alias_en_modo_mock_no_devuelve_cbu(client, h):
    r = client.post(f"{BASE}/validar", json={"cbu_or_alias": "mi.alias.banco"},
                    headers=h).json()
    assert r["cbu"] == "0" * 22


def test_validar_cbu_real_usa_el_scope_de_transferencias(client, cred, red, h, sin_mock):
    red.token()
    red.ruta("/transferencias/validar", body={"titular": "CAPRESCA SA"})

    r = client.post(f"{BASE}/validar", json={"cbu_or_alias": "0070068930004021957614"},
                    headers=h)

    assert r.status_code == 200 and r.json()["titular"] == "CAPRESCA SA"
    assert red.llamadas_a("/transferencias/validar")[0]["json"] == {
        "cbu_or_alias": "0070068930004021957614"}
    assert red.llamadas_a("/cas/oidc/accessToken")[0]["params"] == {
        "scope": "transferencias-confeccion"}


# ──────────────────────── Estado y registro local ──────────────────────────────

def test_estado_en_modo_mock(client, h):
    r = client.get(f"{BASE}/OP-123/estado", headers=h).json()
    assert r == {"id_operacion": "OP-123", "status": "ACREDITADA", "_mock": True}


def test_estado_real_actualiza_la_transferencia_local(client, db, cred, red, h, sin_mock):
    db.add(Transfer(cbu_destino="0070068930004021957614", monto=Decimal("100.00"),
                    id_operacion_ib="OP-9", status="INICIADA", initiated_by=7,
                    initiated_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)))
    db.commit()
    red.token()
    red.ruta("/transferencias/OP-9/estado", body={"status": "ACREDITADA"})

    r = client.get(f"{BASE}/OP-9/estado", headers=h)

    assert r.status_code == 200
    guardada = db.query(Transfer).one()
    assert guardada.status == "ACREDITADA"
    assert guardada.last_status_check is not None
    assert guardada.last_status_payload == {"status": "ACREDITADA"}


def test_estado_real_de_una_transferencia_desconocida_no_rompe(client, db, cred, red, h, sin_mock):
    red.token()
    red.ruta("/transferencias/OP-inexistente/estado", body={"status": "RECHAZADA"})

    r = client.get(f"{BASE}/OP-inexistente/estado", headers=h)

    assert r.status_code == 200 and r.json()["status"] == "RECHAZADA"
    assert db.query(Transfer).count() == 0


def test_listado_local_pagina_y_ordena_por_fecha_desc(client, db, h):
    for i, dia in enumerate([1, 3, 2]):
        db.add(Transfer(cbu_destino=f"00700689300040219576{i}{i}", monto=Decimal("10.00"),
                        concepto=f"t{dia}", status="INICIADA",
                        initiated_at=datetime(2026, 3, dia, 10, 0, tzinfo=timezone.utc)))
    db.commit()

    r = client.get(f"{BASE}/local?page=1&per_page=2").json()
    assert r["total"] == 3 and r["page"] == 1 and r["per_page"] == 2
    assert [t["concepto"] for t in r["data"]] == ["t3", "t2"]

    r = client.get(f"{BASE}/local?page=2&per_page=2").json()
    assert [t["concepto"] for t in r["data"]] == ["t1"]


def test_listado_local_filtra_los_rechazados_por_dia_y_da_el_motivo(client, db, h):
    error = ("Error de Interbanking: Se encontraron los siguientes errores en el body: 1078 - El operador no "
             "tiene acceso o no existe la cuenta crédito (confection_id 10) "
             "[url=https://api-gw.interbanking.com.ar/api/prod/v1/transfers/confection/third-party]")
    db.add_all([
        # 19/10 22:30 en Argentina: el día en UTC ya es 20/10, pero cuenta como 19.
        Transfer(cbu_destino="1" * 22, monto=10, status="ERROR", concepto="ayer",
                 initiated_at=datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc),
                 last_status_payload={"confection_id": 9, "error": error}),
        Transfer(cbu_destino="2" * 22, monto=10, status="ERROR", concepto="hoy",
                 initiated_at=datetime(2026, 10, 20, 13, 27, tzinfo=timezone.utc),
                 last_status_payload={"confection_id": 10, "error": error}),
        Transfer(cbu_destino="3" * 22, monto=10, status="INICIADA", concepto="salió",
                 initiated_at=datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)),
    ])
    db.commit()

    r = client.get(f"{BASE}/local", params={"status": "ERROR", "date_since": "2026-10-20",
                                            "date_until": "2026-10-20"}, headers=h).json()
    assert [t["concepto"] for t in r["data"]] == ["hoy"]
    assert r["data"][0]["motivo"] == ("1078 - El operador no tiene acceso o no existe la cuenta crédito "
                                      "(confection_id 10)")

    r = client.get(f"{BASE}/local", params={"status": "ERROR", "date_since": "2026-10-19",
                                            "date_until": "2026-10-19"}, headers=h).json()
    assert [t["concepto"] for t in r["data"]] == ["ayer"]

    sin_error = client.get(f"{BASE}/local", params={"status": "INICIADA"}, headers=h).json()["data"]
    assert sin_error[0]["motivo"] is None


def test_listado_local_con_fecha_invalida_es_422(client, h):
    assert client.get(f"{BASE}/local", params={"date_since": "20/10/2026"}, headers=h).status_code == 422


def test_alta_real_informa_el_numero_de_operador(client, db, cred, red, h, sin_mock):
    cred.username = "-3|1791557092844|portezuelo"
    db.commit()
    red.token()
    _ruta_cuenta(red, [{"account_number": "46600513539", "account_type": "CC", "bank_number": "011",
                        "account_cbu": "0110599520000046600513"}])
    red.ruta("/v1/transfers/confection/third-party", body={"operation_id": "OP-1", "found_transfers": [{}]})

    assert client.post(BASE, json=NUEVA, headers=h).status_code == 200
    envio = red.llamadas_a("/v1/transfers/confection/third-party")[0]["json"]
    assert envio["operator_id"] == 1791557092844


def test_alta_real_rechazada_queda_registrada_como_error(client, db, cred, red, h, sin_mock):
    red.token()
    _ruta_cuenta(red, [{"account_number": "46600513539", "account_type": "CC", "bank_number": "011",
                        "account_cbu": "0110599520000046600513"}])
    red.ruta("/v1/transfers/confection/third-party", status=400,
             body={"message": "1004 - La fecha de solicitud no es una fecha válida"})

    r = client.post(BASE, json=NUEVA, headers=h)

    assert r.status_code >= 400
    t = db.query(Transfer).one()
    assert t.status == "ERROR"
    assert t.last_status_payload["confection_id"] == t.id
    # El próximo intento usa otro confection_id.
    red.limpiar_rutas().token()
    _ruta_cuenta(red, [{"account_number": "46600513539", "account_type": "CC", "bank_number": "011",
                        "account_cbu": "0110599520000046600513"}])
    red.ruta("/v1/transfers/confection/third-party", body={"operation_id": "OP-2", "found_transfers": [{}]})
    assert client.post(BASE, json=NUEVA, headers=h).status_code == 200
    ids = [ll["json"]["found_transfers"][0]["confection_id"] for ll in red.llamadas_a("/v1/transfers/confection/third-party")]
    assert ids[0] != ids[-1]


def test_los_envios_rechazados_no_van_a_conciliacion(client, db):
    db.add_all([Transfer(cbu_destino="1" * 22, monto=10, status="ERROR"),
                Transfer(cbu_destino="2" * 22, monto=20, status="PENDING_AUTHORIZATION")])
    db.commit()
    r = client.get(f"/internal/interbanking/transactions?date={date.today().isoformat()}",
                   headers={"X-Internal-API-Key": os.environ.get("INTERNAL_API_KEY", "")})
    assert r.status_code == 200, r.text
    assert [t["status_ib"] for t in r.json()] == ["PENDING_AUTHORIZATION"]


def test_observaciones_con_el_usuario_que_cargo():
    from app.services.transfer_service import _comentario_con_usuario
    assert _comentario_con_usuario("Pago", "jperez") == "Pago - Cargo: jperez"
    assert _comentario_con_usuario("Pago", None) == "Pago" and _comentario_con_usuario("Pago", " ") == "Pago"
    largo = _comentario_con_usuario("x" * 300, "jperez")
    assert len(largo) == 120 and largo.endswith(" - Cargo: jperez")
