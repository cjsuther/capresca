"""Auditoría (tabla legacy): la consulta filtra por usuario."""
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.services.auditoria import registrar


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_filtro_por_usuario(client):
    h = _auth(client)
    with SessionLocal() as db:
        registrar(db, usuario="audi", proceso="CAJA", opcion="Cobranza")
        registrar(db, usuario="otro", proceso="CAJA", opcion="Cobranza")
    eventos = client.get("/api/creditos/admin/auditoria?usuario=audi", headers=h).json()["items"]
    assert eventos and all("AUDI" in e["usuario"].upper() for e in eventos)
