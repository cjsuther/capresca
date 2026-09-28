"""La liquidación por lote muestra qué solicitud originó cada contrato."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models_productos as m
from app.core.database import SessionLocal


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _a_liquidar(client, h, nombre):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    pers = next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": nombre, "monto": 300_000, "plazo": 12,
        "desembolsar": False}).json()
    assert c["estado"] == "A_LIQUIDAR", c
    return c, pers["id"]


def test_lote_muestra_la_solicitud_que_origino_el_contrato(client):
    h = _auth(client)
    con, producto_id = _a_liquidar(client, h, "SOSA LUIS")
    sin, _ = _a_liquidar(client, h, "RIOS EVA")
    with SessionLocal() as db:
        db.add(m.PPSolicitud(numero="SOL-LOTE-01", estado="ORIGINADA", producto_id=producto_id,
                             contrato_id=con["id"]))
        db.commit()

    hoy = date.today().isoformat()
    lote = next(l for l in client.get("/api/creditos/contratos/lotes-liquidacion", headers=h).json()["items"]
                if l["fecha"] == hoy)
    por_id = {c["id"]: c for c in lote["contratos"]}
    assert por_id[con["id"]]["solicitud"] == "SOL-LOTE-01"
    assert por_id[sin["id"]]["solicitud"] is None
