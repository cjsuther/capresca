"""Informes de Seguros: cobrados por período, primas devengadas, pagos de seguros."""
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


def _credito_con_seguro(client, h, fecha="2026-03-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)  # línea con seguro
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "180000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": fecha}).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1], "fecha_pago": fecha})
    return cred


def test_seguros_cobrados(client):
    h = _auth(client)
    _credito_con_seguro(client, h, fecha="2026-03-10")
    r = client.get("/api/creditos/seguros/cobrados?desde=2026-03-01&hasta=2026-03-31", headers=h).json()
    assert Decimal(r["total_seguro"]) > 0
    assert len(r["dias"]) >= 1


def test_primas_devengadas(client):
    h = _auth(client)
    _credito_con_seguro(client, h, fecha="2026-03-10")
    r = client.get("/api/creditos/seguros/primas-devengadas?desde=2026-01-01&hasta=2026-12-31",
                   headers=h).json()
    # devengado = cobrado + pendiente
    assert Decimal(r["devengado"]) == Decimal(r["cobrado"]) + Decimal(r["pendiente"])
    assert Decimal(r["devengado"]) > 0
    assert Decimal(r["cobrado"]) > 0   # se cobró la cuota 1


def test_pagos_seguros(client):
    h = _auth(client)
    reg = [r for r in client.get("/api/creditos/seguros/regimenes", headers=h).json() if "Renta" in r["nombre"]][0]
    client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/beneficiarios", headers=h,
                json={"apellido_nombre": "SORIA", "monto_mensual": "100000"})
    client.post(f"/api/creditos/seguros/regimenes/{reg['id']}/generar-cuotas?periodo=2026-05", headers=h)
    r = client.get("/api/creditos/seguros/pagos?desde=2026-05-01&hasta=2026-05-31", headers=h).json()
    assert r["cantidad"] >= 1
    assert Decimal(r["total"]) >= Decimal("100000")


def test_seguro_adicional(client):
    h = _auth(client)
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.SeguroAgente(periodo="092002", cuil="20115755456",
        titular="VILLACORTA DARDO", remuneracion=Decimal("168"),
        seg_obligatorio=Decimal("1"), seg_sepelio=Decimal("2"),
        seg_conyuge=Decimal("0"), seg_adicional=Decimal("0")))
    db.add(models.SeguroAgente(periodo="092002", cuil="27066503742",
        titular="GAUNA MARIA", remuneracion=Decimal("500"),
        seg_obligatorio=Decimal("1"), seg_sepelio=Decimal("2"),
        seg_conyuge=Decimal("0"), seg_adicional=Decimal("5")))
    db.commit(); db.close()

    res = client.get("/api/creditos/seguros/adicional/resumen?periodo=092002", headers=h).json()
    assert res["agentes"] == 2
    assert res["con_adicional"] == 1
    assert res["sin_adicional"] == 1
    assert Decimal(res["total_adicional"]) == Decimal("5")

    # agentes sin adicional (informeagentessinseguroadicional)
    sin = client.get("/api/creditos/seguros/adicional/agentes?con_adicional=false&periodo=092002", headers=h).json()
    assert sin["total"] == 1
    assert sin["items"][0]["titular"] == "VILLACORTA DARDO"


def test_titulares_seguro(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.TitularSeguro(cuil="27066500832", apellido_nombre="BUSTAMANTE MARIA",
        tipo_titular="A", organo=1393, sexo="F", no_agente=105,
        fecha_nac=datetime.date(1951, 6, 21), localidad="CAPITAL", cantidad=1))
    db.commit(); db.close()
    r = client.get("/api/creditos/seguros/titulares?q=BUSTAMANTE", headers=h).json()
    assert r["total"] >= 1
    assert r["items"][0]["apellido_nombre"] == "BUSTAMANTE MARIA"
