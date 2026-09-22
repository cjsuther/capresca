"""Consultas e informes del módulo Créditos."""
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


def _otorgar(client, h, cuotas=6, primer_vto="2026-03-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "180000", "cantidad_cuotas": cuotas,
        "fecha_primer_vencimiento": primer_vto,
    }).json()
    client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h)
    return cli


def test_situacion_cliente(client):
    h = _auth(client)
    cli = _otorgar(client, h)
    r = client.get(f"/api/creditos/creditos/consultas/cliente/{cli}/situacion", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["creditos_activos"] == 1
    assert Decimal(d["saldo_total"]) == Decimal("180000.00")
    assert len(d["creditos"]) == 1
    assert d["creditos"][0]["cuotas_pendientes"] == 6
    assert d["margen_disponible"] is not None


def test_estadisticas_cartera(client):
    h = _auth(client)
    _otorgar(client, h)
    r = client.get("/api/creditos/creditos/consultas/estadisticas", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["creditos_activos"] >= 1
    assert Decimal(d["capital_otorgado_total"]) >= Decimal("180000")
    assert len(d["por_linea"]) >= 1


def test_envios_periodo(client):
    h = _auth(client)
    _otorgar(client, h, cuotas=6, primer_vto="2026-03-10")
    # el período de marzo debe traer la cuota 1
    r = client.get("/api/creditos/creditos/consultas/envios?desde=2026-03-01&hasta=2026-03-31",
                   headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["cantidad"] >= 1
    assert Decimal(d["total"]) > 0
    assert d["items"][0]["cbu"]  # trae el CBU para el débito
