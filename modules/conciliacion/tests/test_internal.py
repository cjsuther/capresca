"""Endpoints internos: cache de CBU y alta de registros desde liquidaciones."""
from decimal import Decimal

from app.models.cbu_agency_cache import CbuAgencyCache
from app.models.liquidacion_record import LiquidacionConciliacionRecord
from app.services import cbu_cache_service
from conftest import FECHA, agencia, item_liquidacion, payload_liquidaciones


# ─────────────────────────────────────────────────────────────────────────────
# Cache de CBU
# ─────────────────────────────────────────────────────────────────────────────
def test_refrescar_el_cache_guarda_un_cbu_por_agencia(client, db, servicios):
    servicios.agencias = [
        agencia(1, "A001", cbus=[{"cbu": "0720099620000001234501"},
                                 {"cbu": "0110012820000034567803"}]),
        agencia(2, "A002", "0170099620000067890106"),
    ]

    r = client.post("/internal/conciliacion/refresh-cbu-cache")

    assert r.json() == {"refreshed": 3}
    assert db.query(CbuAgencyCache).count() == 3
    entrada = cbu_cache_service.lookup(db, "0110012820000034567803")
    assert entrada.client_id == 1 and entrada.agency_number == "A001"
    assert len(cbu_cache_service.get_all(db)) == 3


def test_refrescar_el_cache_con_clientes_caido_no_borra_lo_cacheado(client, db, servicios):
    """Degradación: si clientes no responde ([]), el cache anterior queda intacto."""
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    client.post("/internal/conciliacion/refresh-cbu-cache")

    servicios.agencias = []
    r = client.post("/internal/conciliacion/refresh-cbu-cache")

    assert r.json() == {"refreshed": 0}
    assert db.query(CbuAgencyCache).count() == 1


def test_una_agencia_sin_cbus_no_aporta_al_cache(client, db, servicios):
    servicios.agencias = [agencia(1, "A001", cbus=[])]
    assert client.post("/internal/conciliacion/refresh-cbu-cache").json() == {"refreshed": 0}
    assert db.query(CbuAgencyCache).count() == 0


def test_buscar_un_cbu_que_no_esta_devuelve_none(db):
    assert cbu_cache_service.lookup(db, "0000000000000000000000") is None


# ─────────────────────────────────────────────────────────────────────────────
# Alta desde liquidaciones
# ─────────────────────────────────────────────────────────────────────────────
def test_recibir_liquidaciones_guarda_los_registros(client, db):
    r = client.post("/internal/conciliacion/liquidaciones", json=payload_liquidaciones(
        item_liquidacion("A001", adeudado="1000.50", premios="100.25",
                         recaudacion="5000", comision="250"),
        item_liquidacion("A002", adeudado="800.00"),
        batch_id=42,
    ))

    assert r.json() == {"received": 2, "batch_id": 42,
                        "operation_date": FECHA.isoformat()}
    filas = db.query(LiquidacionConciliacionRecord).order_by(
        LiquidacionConciliacionRecord.agency_number).all()
    assert [f.agency_number for f in filas] == ["A001", "A002"]
    assert Decimal(str(filas[0].importe_adeudado)) == Decimal("1000.50")
    assert Decimal(str(filas[0].comision_total)) == Decimal("250")
    assert filas[0].liquidacion_batch_id == 42 and filas[0].moneda == "ARS"
    assert filas[0].reconciliation_record_id is None


def test_recibir_liquidaciones_notifica_a_quien_subio_el_lote(client, servicios):
    client.post("/internal/conciliacion/liquidaciones", json=payload_liquidaciones(
        item_liquidacion("A001", adeudado="1000"), batch_id=42, created_by=7))

    assert len(servicios.notificaciones) == 1
    n = servicios.notificaciones[0]
    assert n["user_id"] == 7 and n["module"] == "conciliacion"
    assert n["entity_type"] == "liquidacion_batch" and n["entity_id"] == 42
    assert n["redirect_path"] == "/modules/conciliacion"
    assert "1 agencia(s)" in n["message"] and "#42" in n["message"]


def test_sin_created_by_no_se_notifica(client, servicios):
    client.post("/internal/conciliacion/liquidaciones", json=payload_liquidaciones(
        item_liquidacion("A001")))
    assert servicios.notificaciones == []


def test_un_lote_vacio_no_notifica_y_recibe_cero(client, servicios):
    r = client.post("/internal/conciliacion/liquidaciones",
                    json=payload_liquidaciones(batch_id=42, created_by=7))
    assert r.json()["received"] == 0
    assert servicios.notificaciones == []


def test_un_lote_sin_fecha_de_operacion_se_acepta(client, db):
    r = client.post("/internal/conciliacion/liquidaciones", json={
        "batch_id": 1, "operation_date": None, "created_by": None,
        "agencies": [dict(item_liquidacion("A001"), operation_date=None)],
    })

    assert r.json()["operation_date"] is None
    assert db.query(LiquidacionConciliacionRecord).one().operation_date is None


def test_un_payload_invalido_es_rechazado(client):
    r = client.post("/internal/conciliacion/liquidaciones", json={
        "batch_id": 1, "operation_date": FECHA.isoformat(),
        "agencies": [{"agency_number": "A001"}],
    })
    assert r.status_code == 422
