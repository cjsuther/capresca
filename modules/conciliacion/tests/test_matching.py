"""El corazón del módulo: cruce de liquidaciones contra transacciones de Interbanking por CBU."""
from datetime import date as date_type
from decimal import Decimal

import pytest

from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_record import ReconciliationRecord
from conftest import (FECHA, OTRA_FECHA, agencia, item_liquidacion, movimiento,
                      payload_liquidaciones, transferencia)


def cruzar(client, h, fecha=FECHA):
    r = client.get(f"/api/conciliacion?date={fecha.isoformat()}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def por_agencia(datos, numero):
    return next(r for r in datos["reconciliation_records"] if r["agency_number"] == numero)


def cargar_liquidaciones(client, *items, fecha=FECHA, batch_id=77, created_by=None):
    r = client.post("/internal/conciliacion/liquidaciones",
                    json=payload_liquidaciones(*items, batch_id=batch_id, fecha=fecha,
                                               created_by=created_by))
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Match por CBU
# ─────────────────────────────────────────────────────────────────────────────
def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "conciliacion"}


def test_match_exacto_por_cbu_consolida_la_agencia(client, h, servicios, db):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "135000.00")]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="150000.00",
                                                 premios="15000.00"))

    datos = cruzar(client, h)

    rec = por_agencia(datos, "A001")
    assert rec["importe_adeudado"] == 150000.0
    assert rec["importe_depositado"] == 135000.0
    assert rec["importe_neto"] == 0.0
    assert rec["status"] == "CONSOLIDADO"          # auto-consolidación por saldo 0
    assert rec["has_liquidacion"] is True
    assert [l["match_type"] for l in rec["links"]] == ["AUTO"]

    tx = datos["interbanking_transactions"][0]
    assert tx["resolved_client_id"] == 1
    assert tx["resolved_agency_number"] == "A001"
    assert tx["match_type"] == "AUTO"
    assert tx["reconciliation_record_id"] == rec["id"]

    assert db.query(ReconciliationIbLink).count() == 1


def test_sin_match_la_transaccion_queda_huerfana(client, h, servicios, db):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "9999999999999999999999", "50000.00")]

    datos = cruzar(client, h)

    tx = datos["interbanking_transactions"][0]
    assert tx["resolved_client_id"] is None
    assert tx["match_type"] is None
    assert tx["reconciliation_record_id"] is None
    assert db.query(ReconciliationIbLink).count() == 0
    assert por_agencia(datos, "A001")["importe_depositado"] == 0.0


def test_transaccion_sin_cbu_no_matchea(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, None, "50000.00")]

    datos = cruzar(client, h)

    assert datos["interbanking_transactions"][0]["match_type"] is None


def test_cbu_compartido_por_dos_agencias_no_rompe_el_cruce(client, h, servicios, db):
    """Ambigüedad: dos agencias con el mismo CBU (dato mal cargado en Clientes).

    Antes los dos `merge()` quedaban pendientes con la misma PK y el flush rompía con
    IntegrityError: el cruce del día entero devolvía 500. Ahora gana el último y el cruce sigue.
    """
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu), agencia(2, "A002", cbu)]
    servicios.transacciones = [transferencia(10, cbu, "1000.00")]

    r = cruzar(client, h)
    assert r is not None
    from app.models.cbu_agency_cache import CbuAgencyCache
    cacheados = db.query(CbuAgencyCache).filter_by(cbu=cbu).all()
    assert len(cacheados) == 1 and cacheados[0].client_id == 2   # el último gana


def test_diferencia_de_importe_deja_la_agencia_a_verificar(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "800.00")]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00"))

    rec = por_agencia(cruzar(client, h), "A001")

    assert rec["importe_neto"] == 200.0
    assert rec["status"] == "A_VERIFICAR"


def test_deposito_en_exceso_deja_saldo_a_favor_de_la_agencia(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "1200.00")]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00"))

    rec = por_agencia(cruzar(client, h), "A001")

    assert rec["importe_neto"] == -200.0
    assert rec["status"] == "A_VERIFICAR"


def test_varios_depositos_parciales_suman(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [
        transferencia(10, "0720099620000001234501", "600.00"),
        transferencia(11, "0720099620000001234501", "400.00", tipo="batch_item"),
    ]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00"))

    rec = por_agencia(cruzar(client, h), "A001")

    assert rec["importe_depositado"] == 1000.0 and rec["status"] == "CONSOLIDADO"
    assert len(rec["links"]) == 2


def test_el_cruce_es_idempotente_no_duplica_vinculos(client, h, servicios, db):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "1000.00")]

    cruzar(client, h)
    rec = por_agencia(cruzar(client, h), "A001")

    assert db.query(ReconciliationIbLink).count() == 1
    assert rec["importe_depositado"] == 1000.0


def test_reasignar_el_cbu_a_otra_agencia_mueve_el_deposito(client, h, servicios, db):
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu)]
    servicios.transacciones = [transferencia(10, cbu, "1000.00")]
    cruzar(client, h)

    # El CBU pasa a ser de otra agencia (corrección en el módulo de clientes).
    servicios.agencias = [agencia(1, "A001"), agencia(2, "A002", cbu)]
    datos = cruzar(client, h)

    assert por_agencia(datos, "A001")["importe_depositado"] == 0.0
    assert por_agencia(datos, "A002")["importe_depositado"] == 1000.0
    vinculos = db.query(ReconciliationIbLink).order_by(ReconciliationIbLink.id).all()
    assert len(vinculos) == 2
    assert vinculos[0].unlinked_at is not None and vinculos[0].unlinked_by_user_id == 0
    assert vinculos[1].unlinked_at is None and vinculos[1].match_type == "AUTO"


def test_registro_sin_movimiento_no_se_auto_consolida(client, h, servicios):
    """Una agencia en 0/0/0 (sin liquidación ni depósito) sigue A_VERIFICAR."""
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]

    rec = por_agencia(cruzar(client, h), "A001")

    assert (rec["importe_adeudado"], rec["importe_depositado"]) == (0.0, 0.0)
    assert rec["status"] == "A_VERIFICAR"


def test_la_auto_consolidacion_no_pisa_un_estado_manual(client, h, servicios, db):
    from conftest import crear_registro
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "1000.00")]
    crear_registro(db, client_id=1, adeudado="1000.00", status="CONSOLIDADO_MANUAL")
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00"))

    rec = por_agencia(cruzar(client, h), "A001")

    assert rec["importe_neto"] == 0.0
    assert rec["status"] == "CONSOLIDADO_MANUAL"


# ─────────────────────────────────────────────────────────────────────────────
# Movimientos de la cuenta de consolidación (se identifican por CUIT)
# ─────────────────────────────────────────────────────────────────────────────
def test_los_movimientos_de_la_cuenta_se_resuelven_por_cuit(client, h, servicios):
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu, tax_id="30-71234567-8")]
    servicios.cuenta_consolidacion = {"account_number": "123456", "account_type": "CC",
                                      "bank_number": "011", "currency": "ARS"}
    servicios.movimientos = [movimiento(500, "700.00", cuit="30712345678")]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="700.00"))

    datos = cruzar(client, h)

    assert servicios.movimientos_pedidos == [(FECHA.isoformat(), servicios.cuenta_consolidacion)]
    rec = por_agencia(datos, "A001")
    assert rec["importe_depositado"] == 700.0 and rec["status"] == "CONSOLIDADO"
    assert rec["links"][0]["ib_cbu"] == cbu


def test_movimiento_con_cuit_desconocido_no_matchea(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501", tax_id="30-71234567-8")]
    servicios.cuenta_consolidacion = {"account_number": "123456"}
    servicios.movimientos = [movimiento(500, "700.00", cuit="20-99999999-9")]

    datos = cruzar(client, h)

    mov = next(t for t in datos["interbanking_transactions"] if t["id"] == 500)
    assert mov["match_type"] is None
    assert por_agencia(datos, "A001")["importe_depositado"] == 0.0


def test_sin_cuenta_de_consolidacion_no_se_piden_movimientos(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.cuenta_consolidacion = None

    cruzar(client, h)

    assert servicios.movimientos_pedidos == []


# ─────────────────────────────────────────────────────────────────────────────
# Degradación cuando un servicio vecino está caído
# ─────────────────────────────────────────────────────────────────────────────
def test_clientes_caido_no_rompe_el_cruce(client, h, servicios):
    """`clientes_client` degrada a [] cuando el módulo está caído."""
    servicios.agencias = []
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "1000.00")]

    datos = cruzar(client, h)

    assert datos["reconciliation_records"] == []
    assert datos["interbanking_transactions"][0]["match_type"] is None


def test_interbanking_caido_deja_las_agencias_sin_depositos(client, h, servicios):
    """`interbanking_client` degrada a [] : se ven las deudas, sin depósitos."""
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = []
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00"))

    datos = cruzar(client, h)

    assert datos["interbanking_transactions"] == []
    rec = por_agencia(datos, "A001")
    assert rec["importe_neto"] == 1000.0 and rec["status"] == "A_VERIFICAR"


# ─────────────────────────────────────────────────────────────────────────────
# Alta de registros desde liquidaciones
# ─────────────────────────────────────────────────────────────────────────────
def test_liquidacion_de_agencia_desconocida_crea_registro_con_client_id_negativo(
        client, h, servicios, db):
    servicios.agencias = []
    cargar_liquidaciones(client, item_liquidacion("A404", adeudado="5000.00",
                                                  premios="500.00"))

    datos = cruzar(client, h)

    rec = por_agencia(datos, "A404")
    assert rec["client_id"] < 0
    assert rec["agency_legal_name"] == "Agencia A404"
    assert (rec["importe_adeudado"], rec["importe_premios"]) == (5000.0, 500.0)
    # y en la segunda corrida se reusa el mismo registro, no crea otro
    cruzar(client, h)
    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.agency_number == "A404").count() == 1


def test_varias_liquidaciones_de_la_misma_agencia_se_agregan(client, h, servicios, db):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    cargar_liquidaciones(client,
                         item_liquidacion("A001", adeudado="600.00", premios="50.00"),
                         item_liquidacion("A001", adeudado="400.00", premios="25.00"))

    rec = por_agencia(cruzar(client, h), "A001")

    assert rec["importe_adeudado"] == 1000.0 and rec["importe_premios"] == 75.0


def test_las_liquidaciones_de_otra_fecha_no_entran(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    cargar_liquidaciones(client, item_liquidacion("A001", adeudado="1000.00",
                                                  fecha=OTRA_FECHA), fecha=OTRA_FECHA)

    rec = por_agencia(cruzar(client, h, FECHA), "A001")

    assert rec["importe_adeudado"] == 0.0 and rec["has_liquidacion"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Asignación manual de una transacción a una agencia
# ─────────────────────────────────────────────────────────────────────────────
def test_asignar_una_transaccion_huerfana_crea_vinculo_manual(client, h, servicios, db):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = [transferencia(10, "9999999999999999999999", "300.00")]
    cruzar(client, h)

    r = client.put("/api/conciliacion/interbanking/transfer/10/agency",
                   json={"client_id": 1}, headers=h)

    assert r.status_code == 200, r.text
    nuevo = r.json()["new_record"]
    assert "previous_record" not in r.json()
    assert nuevo["client_id"] == 1
    assert [l["match_type"] for l in nuevo["links"]] == ["MANUAL"]
    assert db.query(ReconciliationIbLink).filter_by(linked_by_user_id=7).count() == 1
    # El importe devuelto ya incluye el depósito recién asignado (antes faltaba el flush
    # previo al recálculo y volvía en 0 hasta el próximo cruce).
    assert nuevo["importe_depositado"] == 300.0
    # TODO(bug): app/routers/conciliacion.py:122 — sin vínculo previo la transacción se
    # imputa al día de HOY, no a la fecha del movimiento que se está conciliando.
    assert nuevo["reconciliation_date"] == date_type.today().isoformat()
    assert por_agencia(cruzar(client, h, date_type.today()), "A001")["importe_depositado"] == 300.0


def test_asignar_a_la_agencia_duena_del_cbu_queda_como_auto(client, h, servicios):
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu)]
    servicios.transacciones = [transferencia(10, cbu, "300.00")]
    cruzar(client, h)

    r = client.put("/api/conciliacion/interbanking/transfer/10/agency",
                   json={"client_id": 1}, headers=h)

    assert [l["match_type"] for l in r.json()["new_record"]["links"]] == ["AUTO"]


def test_reasignar_devuelve_tambien_el_registro_que_pierde_el_deposito(client, h, servicios):
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu), agencia(2, "A002", "0110012820000034567803")]
    servicios.transacciones = [transferencia(10, cbu, "300.00")]
    cruzar(client, h)

    r = client.put("/api/conciliacion/interbanking/transfer/10/agency",
                   json={"client_id": 2}, headers=h).json()

    assert r["new_record"]["client_id"] == 2
    assert r["previous_record"]["client_id"] == 1
    assert r["previous_record"]["importe_depositado"] == 0.0     # perdió el depósito
    assert r["new_record"]["importe_depositado"] == 300.0        # y el nuevo lo recibe en el acto


def test_asignar_una_transaccion_inexistente_da_404(client, h, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.transacciones = []

    r = client.put("/api/conciliacion/interbanking/transfer/999/agency",
                   json={"client_id": 1}, headers=h)

    assert r.status_code == 404 and r.json()["detail"] == "Transacción IB no encontrada"


def test_asignar_a_un_cliente_sin_cache_usa_un_nombre_generico(client, h, servicios, db):
    """Sin entrada en el cache de CBU no hay razón social: queda "Cliente N"."""
    from datetime import date as date_type
    servicios.agencias = []
    servicios.transacciones = [transferencia(10, "9999999999999999999999", "300.00")]

    r = client.put("/api/conciliacion/interbanking/transfer/10/agency",
                   json={"client_id": 42}, headers=h)

    nuevo = r.json()["new_record"]
    assert nuevo["agency_legal_name"] == "Cliente 42"
    # Sin vínculo previo el endpoint no sabe la fecha de la transacción y usa HOY.
    # TODO(bug): app/routers/conciliacion.py:122 ignora la fecha de la transacción IB;
    # una transferencia de otro día se imputa al día de hoy.
    assert nuevo["reconciliation_date"] == date_type.today().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Resumen por fecha
# ─────────────────────────────────────────────────────────────────────────────
def test_resumen_cuenta_por_estado_y_suma_importes(client, h, servicios, db):
    from conftest import crear_registro
    crear_registro(db, client_id=1, agency_number="A001", adeudado="1000", depositado="1000",
                   status="CONSOLIDADO")
    crear_registro(db, client_id=2, agency_number="A002", adeudado="500", depositado="0")
    crear_registro(db, client_id=3, agency_number="A003", adeudado="800", depositado="300",
                   status="CONSOLIDADO_MANUAL")
    crear_registro(db, client_id=4, agency_number="A004", fecha=OTRA_FECHA, adeudado="9999")

    r = client.get(f"/api/conciliacion/summary?date={FECHA.isoformat()}").json()

    assert r["date"] == FECHA.isoformat()
    assert (r["A_VERIFICAR"], r["CONSOLIDADO"], r["CONSOLIDADO_MANUAL"]) == (1, 1, 1)
    assert r["total_records"] == 3
    assert Decimal(str(r["total_importe_adeudado"])) == Decimal("2300")
    assert Decimal(str(r["total_importe_depositado"])) == Decimal("1300")
    assert Decimal(str(r["total_importe_neto"])) == Decimal("1000")


def test_resumen_de_una_fecha_sin_datos_viene_en_cero(client):
    r = client.get(f"/api/conciliacion/summary?date={FECHA.isoformat()}").json()
    assert r["total_records"] == 0 and r["total_importe_adeudado"] == 0


def test_listado_de_agencias_delega_en_clientes(client, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    assert client.get("/api/conciliacion/agencies").json()[0]["agency_number"] == "A001"


# ─────────────────────────────────────────────────────────────────────────────
# Identidad inyectada por el gateway
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("headers,esperado", [({}, 422), ({"X-User-Id": "no-numero"}, 401)])
def test_el_cruce_exige_un_x_user_id_valido(client, headers, esperado):
    r = client.get(f"/api/conciliacion?date={FECHA.isoformat()}", headers=headers)
    assert r.status_code == esperado


def test_el_cruce_automatico_deshace_una_asignacion_manual_contra_el_cbu(client, h, servicios, db):
    """Si el CBU de la transacción pertenece a otra agencia, la próxima corrida del cruce
    devuelve el depósito a la dueña del CBU y descarta la asignación manual.
    """
    cbu = "0720099620000001234501"
    servicios.agencias = [agencia(1, "A001", cbu), agencia(2, "A002", "0110012820000034567803")]
    servicios.transacciones = [transferencia(10, cbu, "300.00")]
    cruzar(client, h)
    client.put("/api/conciliacion/interbanking/transfer/10/agency",
               json={"client_id": 2}, headers=h)

    datos = cruzar(client, h)

    assert por_agencia(datos, "A001")["importe_depositado"] == 300.0
    assert por_agencia(datos, "A002")["importe_depositado"] == 0.0
    assert [l["match_type"] for l in por_agencia(datos, "A001")["links"]] == ["AUTO"]
    activos = db.query(ReconciliationIbLink).filter(
        ReconciliationIbLink.unlinked_at.is_(None)).all()
    assert len(activos) == 1 and activos[0].match_type == "AUTO"
