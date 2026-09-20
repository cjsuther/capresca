"""Informes 🔷 desbloqueados por los conceptos reales (H-011):
IVA de gastos originación/quebranto, previo pago, IVA de egresos."""
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


def _cli_linea(client, h):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json() if l["tipo_calculo"] == 1)
    return cli, linea["id"]


def test_iva_gsoq_periodo(client):
    h = _auth(client)
    cli, linea = _cli_linea(client, h)
    client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea, "monto_solicitado": "100000",
        "cantidad_cuotas": 12, "fecha_primer_vencimiento": "2026-05-10",
        "iva_gastos_originacion": "2100", "iva_quebranto": "500"})
    r = client.get("/api/creditos/contabilidad/iva-gsoq?desde=2026-01-01&hasta=2026-12-31",
                   headers=h).json()
    assert Decimal(r["iva_gastos_originacion"]) >= Decimal("2100")
    assert Decimal(r["iva_quebranto"]) >= Decimal("500")
    assert Decimal(r["iva_total"]) == Decimal(r["iva_gastos_originacion"]) + Decimal(r["iva_quebranto"])


def test_previo_pago(client):
    h = _auth(client)
    cli, linea = _cli_linea(client, h)
    client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea, "monto_solicitado": "100000",
        "cantidad_cuotas": 12, "fecha_primer_vencimiento": "2026-05-10",
        "credito_previo_pago": 99999, "importe_previo_pago": "35000"})
    r = client.get("/api/creditos/creditos/consultas/previo-pago", headers=h).json()
    assert any(x["credito_cancelado"] == 99999 and Decimal(x["importe_previo_pago"]) == Decimal("35000")
               for x in r)


def test_iva_egresos(client):
    h = _auth(client)
    # una OP; el IVA por defecto es 0 pero el endpoint responde
    client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV", "concepto": "x", "importe": "10000", "fecha": "2026-04-10"})
    r = client.get("/api/creditos/contabilidad/iva-egresos?desde=2026-04-01&hasta=2026-04-30",
                   headers=h).json()
    assert r["cantidad_op"] >= 1
    assert "iva_egresos" in r
