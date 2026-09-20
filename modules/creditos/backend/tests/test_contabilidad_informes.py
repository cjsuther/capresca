"""Informes de Contabilidad: OP devengadas por período, solicitudes de baja."""
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


def test_op_devengadas(client):
    h = _auth(client)
    # una OP a proveedor con fecha conocida
    client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV X", "concepto": "insumos", "importe": "50000",
        "fecha": "2026-04-10"})
    r = client.get("/api/creditos/contabilidad/op-devengadas?desde=2026-04-01&hasta=2026-04-30",
                   headers=h).json()
    assert r["cantidad"] >= 1
    assert Decimal(r["total"]) >= Decimal("50000")
    assert any(t["tipo"] == "PROVEEDOR" for t in r["por_tipo"])


def test_solicitudes_baja_vacio_inicial(client):
    h = _auth(client)
    r = client.get("/api/creditos/contabilidad/solicitudes-baja", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)  # sin bajas todavía → lista (posiblemente vacía)
