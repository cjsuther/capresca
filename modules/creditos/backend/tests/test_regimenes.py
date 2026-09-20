"""Regímenes especiales de Seguros (Malvinas, excombatientes, subsidios)."""
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


def _regimen(client, h, nombre_contiene="Renta"):
    regs = client.get("/api/creditos/seguros/regimenes", headers=h).json()
    return next(r for r in regs if nombre_contiene in r["nombre"])


def test_alta_beneficiario_usa_monto_default(client):
    h = _auth(client)
    reg = _regimen(client, h)
    b = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/beneficiarios", headers=h, json={
        "apellido_nombre": "SORIA, HÉCTOR", "cuil": "20180000005",
        "cbu": "0110000000000000000001"}).json()
    assert b["estado"] == "V"
    assert Decimal(b["monto_mensual"]) == Decimal(reg["monto_default"])


def test_generar_cuotas_crea_op_y_es_idempotente(client):
    h = _auth(client)
    reg = _regimen(client, h)  # tipo P (paga)
    for nom in ("A", "B"):
        client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/beneficiarios", headers=h,
                    json={"apellido_nombre": nom, "monto_mensual": "100000"})

    # OPs antes
    ops_antes = client.get("/api/creditos/egresos/ordenes?estado=P", headers=h).json()["total"]

    g = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/generar-cuotas?periodo=2026-05",
                    headers=h).json()
    assert g["cuotas_generadas"] == 2
    assert g["ordenes_pago"] == 2          # régimen de pago -> emite OP
    assert Decimal(g["total"]) == Decimal("200000")

    # una OP nueva por beneficiario, tipo SEGURO
    ops = client.get("/api/creditos/egresos/ordenes", headers=h).json()["items"]
    assert len([o for o in ops if o["tipo"] == "SEGURO"]) == 2
    assert client.get("/api/creditos/egresos/ordenes?estado=P", headers=h).json()["total"] == ops_antes + 2

    # re-generar el mismo período: no duplica
    g2 = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/generar-cuotas?periodo=2026-05",
                     headers=h).json()
    assert g2["cuotas_generadas"] == 0


def test_baja_excluye_de_generacion(client):
    h = _auth(client)
    reg = _regimen(client, h, "Excombatientes")
    b = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/beneficiarios", headers=h,
                    json={"apellido_nombre": "BAJA TEST", "monto_mensual": "50000"}).json()
    client.post(f"/api/creditos/seguros/beneficiarios/{b['id']}/baja", headers=h)
    g = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/generar-cuotas?periodo=2026-06",
                    headers=h).json()
    assert g["cuotas_generadas"] == 0


def test_periodo_invalido(client):
    h = _auth(client)
    reg = _regimen(client, h)
    r = client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/generar-cuotas?periodo=2026",
                    headers=h)
    assert r.status_code == 422
