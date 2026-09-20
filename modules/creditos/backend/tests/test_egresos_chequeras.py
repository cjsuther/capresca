"""Tesorería: chequeras y revisión de pagos pendientes/incompletos."""
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


def _op(client, h, importe="50000"):
    return client.post("/api/creditos/egresos/ordenes", headers=h, json={
        "beneficiario": "PROV", "concepto": "x", "importe": importe}).json()


def test_chequera_y_pago(client):
    h = _auth(client)
    ch = client.post("/api/creditos/egresos/chequeras", headers=h, json={
        "banco": "Banco Nación", "cuenta": "123-4", "desde": 1001, "hasta": 1003}).json()
    assert ch["proximo"] == 1001
    op = _op(client, h)
    # pagar tomando el próximo cheque de la chequera
    pagada = client.post(f"/api/creditos/egresos/ordenes/{op['id']}/pagar-chequera", headers=h,
                         json={"chequera_id": ch["id"]}).json()
    assert pagada["estado"] == "G"
    assert pagada["cheque_numero"] == "1001"
    # la chequera avanzó
    ch2 = [c for c in client.get("/api/creditos/egresos/chequeras", headers=h).json() if c["id"] == ch["id"]][0]
    assert ch2["proximo"] == 1002


def test_chequera_se_agota(client):
    h = _auth(client)
    ch = client.post("/api/creditos/egresos/chequeras", headers=h, json={
        "banco": "Nación", "desde": 5, "hasta": 5}).json()  # un solo cheque
    op1 = _op(client, h)
    client.post(f"/api/creditos/egresos/ordenes/{op1['id']}/pagar-chequera", headers=h,
                json={"chequera_id": ch["id"]})
    op2 = _op(client, h)
    r = client.post(f"/api/creditos/egresos/ordenes/{op2['id']}/pagar-chequera", headers=h,
                    json={"chequera_id": ch["id"]})
    assert r.status_code == 409  # agotada


def test_revision_pendientes(client):
    h = _auth(client)
    _op(client, h, "70000")
    r = client.get("/api/creditos/egresos/revision", headers=h).json()
    assert len(r["pendientes"]) >= 1
    assert Decimal(r["total_pendiente"]) >= Decimal("70000")
