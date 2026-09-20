"""Caja: anulación de recibo (reversa de cobranza)."""
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


def _otorgar(client, h, cuotas=6):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json() if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"], "monto_solicitado": "120000",
        "cantidad_cuotas": cuotas, "fecha_primer_vencimiento": "2026-01-10"}).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def test_anular_recibo_revierte_cobranza(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    saldo0 = Decimal(client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["saldo_capital"])
    recibo = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1], "fecha_pago": "2026-01-10"}).json()
    # tras cobrar, el saldo bajó
    saldo1 = Decimal(client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["saldo_capital"])
    assert saldo1 < saldo0

    # anular
    an = client.post(f"/api/creditos/caja/recibos/{recibo['id']}/anular", headers=h).json()
    assert an["estado"] == "A"
    # el saldo se restauró y la cuota 1 vuelve a estar pendiente
    saldo2 = Decimal(client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["saldo_capital"])
    assert saldo2 == saldo0
    pend = client.get(f"/api/creditos/caja/creditos/{cred['id']}/pendientes", headers=h).json()
    assert any(p["numero"] == 1 for p in pend)

    # no se puede re-anular
    assert client.post(f"/api/creditos/caja/recibos/{recibo['id']}/anular", headers=h).status_code == 409


def test_anular_reactiva_credito_cancelado(client):
    h = _auth(client)
    cred = _otorgar(client, h, cuotas=3)
    recibo = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1, 2, 3], "fecha_pago": "2026-01-10"}).json()
    assert client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["estado"] == "C"
    client.post(f"/api/creditos/caja/recibos/{recibo['id']}/anular", headers=h)
    assert client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["estado"] == "A"
