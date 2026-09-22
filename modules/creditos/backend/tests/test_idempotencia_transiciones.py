"""Idempotencia de transiciones críticas (H-108): un reintento con la misma Idempotency-Key no
duplica la operación (alta de solicitud, otorgamiento, desembolso, devengo)."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_idem.db"
os.environ["ENVIRONMENT"] = "development"

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


def _payload(client, h):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json()
                 if l["activa"] and l["tipo_calculo"] == 1)   # francés (sin cuota fija)
    return {"cliente_id": cli, "linea_id": linea["id"], "monto_solicitado": "80000",
            "cantidad_cuotas": 6, "fecha_primer_vencimiento": "2026-03-10"}


def test_alta_solicitud_idempotente(client):
    """Dos POST /creditos/solicitudes con la misma Idempotency-Key crean UNA sola solicitud."""
    h = _auth(client)
    body = _payload(client, h)
    hk = {**h, "Idempotency-Key": "sol-key-1"}
    r1 = client.post("/api/creditos/creditos/solicitudes", headers=hk, json=body)
    assert r1.status_code == 201
    id1 = r1.json()["id"]
    r2 = client.post("/api/creditos/creditos/solicitudes", headers=hk, json=body)   # mismo key → replay
    assert r2.status_code in (200, 201)
    assert r2.json()["id"] == id1                       # misma solicitud, no una nueva

    # sin key, un segundo POST sí crea otra (control): comprueba que el dedup es por la key
    r3 = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body)
    assert r3.json()["id"] != id1


def test_otorgar_idempotente(client):
    """Dos otorgar con la misma Idempotency-Key otorgan UN solo crédito de la solicitud."""
    h = _auth(client)
    body = _payload(client, h)
    sid = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body).json()["id"]
    hk = {**h, "Idempotency-Key": "otorgar-key-1"}
    r1 = client.post(f"/api/creditos/creditos/solicitudes/{sid}/otorgar", headers=hk)
    assert r1.status_code == 200
    cred1 = r1.json()["id"]
    r2 = client.post(f"/api/creditos/creditos/solicitudes/{sid}/otorgar", headers=hk)   # replay
    assert r2.status_code == 200 and r2.json()["id"] == cred1
