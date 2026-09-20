"""Módulo Tesorería / Egresos: órdenes de pago."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_desembolso_genera_op_al_otorgar(client):
    h = _auth(client)
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "200000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": "2026-04-10",
    }).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()

    ops = client.get("/api/creditos/egresos/ordenes?estado=P", headers=h).json()["items"]
    desembolso = [o for o in ops if o["credito_id"] == cred["id"]]
    assert len(desembolso) == 1
    assert desembolso[0]["tipo"] == "CREDITO"
    assert Decimal(desembolso[0]["importe"]) == Decimal("200000.00")
    assert desembolso[0]["estado"] == "P"


def test_crear_y_pagar_op(client):
    h = _auth(client)
    # OP a proveedor (licitación/compra)
    op = client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "LIBRERIA CENTRAL SRL", "concepto": "Compra de insumos",
        "importe": "85000", "tipo": "PROVEEDOR", "cuit": "30712345678",
    }).json()
    assert op["estado"] == "P"
    oid = op["id"]

    # pagar con cheque
    pagada = client.post(f"/api/creditos/egresos/ordenes/{oid}/pagar", headers=h, json={
        "banco": "Banco Nación", "cheque_numero": "00012345", "fecha_pago": "2026-04-15",
    }).json()
    assert pagada["estado"] == "G"
    assert pagada["cheque_numero"] == "00012345"

    # no se puede volver a pagar
    r = client.post(f"/api/creditos/egresos/ordenes/{oid}/pagar", headers=h, json={
        "banco": "X", "cheque_numero": "Y",
    })
    assert r.status_code == 409


def test_pagar_op_idempotente(client):
    """H-157: pagar una OP es idempotente — un doble-POST con la misma Idempotency-Key no paga dos veces
    (devuelve el mismo resultado), no crea un segundo movimiento."""
    h = _auth(client)
    op = client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV IDEMP", "concepto": "x", "importe": "50000", "tipo": "PROVEEDOR",
        "cuit": "30712345678"}).json()
    oid = op["id"]
    hk = {**h, "Idempotency-Key": "op-pay-k1"}
    body = {"banco": "Banco Nación", "cheque_numero": "00099999", "fecha_pago": "2026-04-15"}
    r1 = client.post(f"/api/creditos/egresos/ordenes/{oid}/pagar", headers=hk, json=body)
    r2 = client.post(f"/api/creditos/egresos/ordenes/{oid}/pagar", headers=hk, json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["estado"] == "G" and r2.json()["estado"] == "G"
    assert r1.json()["id"] == r2.json()["id"] and r2.json()["cheque_numero"] == "00099999"


def test_totales_egresos(client):
    h = _auth(client)
    client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV A", "concepto": "x", "importe": "10000",
    })
    t = client.get("/api/creditos/egresos/totales", headers=h).json()
    assert Decimal(t["pendiente"]) >= Decimal("10000")


def test_informe_op_filtros_y_excel(client):
    h = _auth(client)
    client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV FILTRO", "concepto": "z", "importe": "12345",
        "tipo": "PROVEEDOR", "cuit": "30111111118"})
    # filtro por tipo + búsqueda
    r = client.get("/api/creditos/egresos/ordenes?tipo=PROVEEDOR&q=FILTRO", headers=h).json()
    assert r["total"] >= 1
    assert all(o["tipo"] == "PROVEEDOR" for o in r["items"])
    # excel
    x = client.get("/api/creditos/egresos/ordenes/excel?tipo=PROVEEDOR", headers=h)
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_reporte_ordenes_por_tipo(client):
    h = _auth(client)
    client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV REP", "concepto": "z", "importe": "40000",
        "tipo": "PROVEEDOR"})
    rep = client.get("/api/creditos/egresos/reporte", headers=h).json()
    prov = next(f for f in rep["por_tipo"] if f["tipo"] == "PROVEEDOR")
    assert Decimal(prov["pendiente"]) >= Decimal("40000")
    # el total general acumula al menos lo pendiente del tipo
    assert Decimal(rep["total"]["importe"]) >= Decimal("40000")
    assert rep["total"]["tipo"] == "TOTAL"


def test_no_anular_op_girada(client):
    h = _auth(client)
    op = client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV B", "concepto": "y", "importe": "5000",
    }).json()
    client.post(f"/api/creditos/egresos/ordenes/{op['id']}/pagar", headers=h, json={
        "banco": "Nación", "cheque_numero": "999",
    })
    r = client.post(f"/api/creditos/egresos/ordenes/{op['id']}/anular", headers=h)
    assert r.status_code == 409


def test_maestro_op_cupo_autorizado(client):
    """Maestro de OP = cupo autorizado (805100): alta con saldo=importe, listado con
    totales, y edición que recalcula saldo = importe - usado."""
    h = _auth(client)
    r = client.post("/api/creditos/egresos/autorizaciones", headers=h, json={
        "nop": 500, "fecha": "2026-01-10", "vigencia": "2028-01-10",
        "importe": "1000000", "sistema": "CRED", "habilitada": True,
        "nres1": 45, "fres1": "2026-01-05"})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert Decimal(r.json()["saldo"]) == Decimal("1000000.00")   # saldo inicial = importe
    assert Decimal(r.json()["importe_usado"]) == 0

    # aparece en el listado (con saldo)
    lst = client.get("/api/creditos/egresos/autorizaciones?con_saldo=true&q=500", headers=h).json()
    assert any(a["id"] == aid for a in lst["items"])

    # totales
    tot = client.get("/api/creditos/egresos/autorizaciones/totales?habilitada=true", headers=h).json()
    assert Decimal(tot["saldo"]) >= Decimal("1000000.00")

    # editar importe -> recalcula saldo
    r2 = client.put(f"/api/creditos/egresos/autorizaciones/{aid}", headers=h, json={
        "nop": 500, "importe": "1200000", "habilitada": True})
    assert r2.status_code == 200
    assert Decimal(r2.json()["saldo"]) == Decimal("1200000.00")  # 1200000 - 0


def test_consumo_cupo_op_validaciones(client):
    """Consumo del cupo de OP (820100): valida vigencia, sistema y saldo, y descuenta
    manteniendo el invariante saldo = importe - usado."""
    h = _auth(client)
    # cupo vigente $100.000, sistema CRED
    r = client.post("/api/creditos/egresos/autorizaciones", headers=h, json={
        "nop": 900, "fecha": "2026-01-01", "vigencia": "2099-01-01",
        "importe": "100000", "sistema": "CRED", "habilitada": True})
    assert r.status_code == 201

    # consumir 30.000 -> saldo 70.000, usado 30.000
    c = client.post("/api/creditos/egresos/autorizaciones/900/consumir", headers=h,
                    json={"importe": "30000"}).json()
    assert Decimal(c["importe_usado"]) == Decimal("30000.00")
    assert Decimal(c["saldo"]) == Decimal("70000.00")

    # sistema que no coincide -> 409
    assert client.post("/api/creditos/egresos/autorizaciones/900/consumir", headers=h,
                       json={"importe": "1000", "sistema": "SEGURO"}).status_code == 409
    # saldo insuficiente -> 409
    assert client.post("/api/creditos/egresos/autorizaciones/900/consumir", headers=h,
                       json={"importe": "80000"}).status_code == 409

    # reintegrar 30.000 -> vuelve a saldo 100.000
    rr = client.post("/api/creditos/egresos/autorizaciones/900/reintegrar", headers=h,
                     json={"importe": "30000"}).json()
    assert Decimal(rr["saldo"]) == Decimal("100000.00") and Decimal(rr["importe_usado"]) == 0


def test_consumo_cupo_vencido_rechazado(client):
    """Una OP vencida (fvigencia <= hoy) no puede utilizarse."""
    h = _auth(client)
    client.post("/api/creditos/egresos/autorizaciones", headers=h, json={
        "nop": 901, "fecha": "2015-01-01", "vigencia": "2016-01-01",
        "importe": "50000", "habilitada": True})
    r = client.post("/api/creditos/egresos/autorizaciones/901/consumir", headers=h,
                    json={"importe": "1000"})
    assert r.status_code == 409 and "vencida" in r.json()["detail"].lower()


def test_reimpresion_comprobante_egreso_pdf(client):
    """Reimpresión de comprobante de egreso (consolida los reimp* de VFP): devuelve un PDF."""
    from decimal import Decimal as D
    from datetime import date
    from app.core.database import SessionLocal
    from app import models
    h = _auth(client)
    s = SessionLocal()
    try:
        e = models.Egreso(sub_tipo=1, apenom="PEREZ JUAN", no_recibo=12345, no_op=999,
                          fecha_op=date(2026, 1, 10), importe=D("1000"), total=D("1000"), anulado=False)
        s.add(e); s.commit(); eid = e.id
    finally:
        s.close()
    r = client.get(f"/api/creditos/egresos/{eid}/comprobante-pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    # 404 para un egreso inexistente
    assert client.get("/api/creditos/egresos/99999999/comprobante-pdf", headers=h).status_code == 404
    s = SessionLocal()
    try:
        s.query(models.Egreso).filter_by(id=eid).delete(); s.commit()
    finally:
        s.close()
