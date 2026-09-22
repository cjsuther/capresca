"""Seguro del crédito: al otorgar se emite la póliza (el área Seguros de CCyPP no se publica, pero la
póliza forma parte del alta del crédito)."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_seg.db"
os.environ["ENVIRONMENT"] = "development"

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


def _otorgar_con_seguro(client, h, fecha="2026-07-01"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    # la línea francesa del seed tiene compañía y prima de seguro
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "240000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": fecha,
    }).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def test_poliza_emitida_al_otorgar(client):
    from app import models
    from app.core.database import SessionLocal
    h = _auth(client)
    cred = _otorgar_con_seguro(client, h)
    # las cuotas traen seguro (>0) porque la línea tiene prima
    assert any(float(c["seguro"]) > 0 for c in cred["cuotas"])
    with SessionLocal() as db:
        polizas = db.query(models.Poliza).filter_by(credito_id=cred["id"]).all()
        assert len(polizas) == 1
        assert polizas[0].estado == "V"
        assert polizas[0].capital_asegurado == Decimal("240000.00")


def teardown_module(_):
    if os.path.exists("_seg.db"):
        os.remove("_seg.db")
