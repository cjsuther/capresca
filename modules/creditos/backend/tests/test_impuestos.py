"""Maestro de impuestos (Contabilidad → Impuestos)."""
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


def test_impuestos_sembrados(client):
    h = _auth(client)
    r = client.get("/api/creditos/impuestos", headers=h)
    assert r.status_code == 200
    cods = {i["codigo"] for i in r.json()["items"]}
    assert {"IVA21", "IVA105", "IIBB-CAT", "SELLOS"} <= cods


def test_abm_impuesto(client):
    h = _auth(client)
    r = client.post("/api/creditos/impuestos", headers=h, json={"codigo": "iva27", "nombre": "IVA 27%", "tipo": "IVA", "alicuota": 27, "base": "INTERES"})
    assert r.status_code == 201 and r.json()["codigo"] == "IVA27" and r.json()["alicuota"] == 27
    iid = r.json()["id"]
    # duplicado -> 409
    assert client.post("/api/creditos/impuestos", headers=h, json={"codigo": "IVA27", "nombre": "x", "alicuota": 1}).status_code == 409
    # editar
    e = client.put(f"/api/creditos/impuestos/{iid}", headers=h, json={"codigo": "IVA27", "nombre": "IVA 27% (mod)", "tipo": "IVA", "alicuota": 27, "base": "TOTAL"})
    assert e.json()["base"] == "TOTAL"
    # baja / reactivar
    assert client.post(f"/api/creditos/impuestos/{iid}/baja", headers=h).json()["activo"] is False
    assert client.post(f"/api/creditos/impuestos/{iid}/reactivar", headers=h).json()["activo"] is True
    # filtro activos
    activos = client.get("/api/creditos/impuestos?estado=activos", headers=h).json()["items"]
    assert all(i["activo"] for i in activos)


def test_indices_sembrados_y_abm(client):
    h = _auth(client)
    cods = {i["codigo"] for i in client.get("/api/creditos/indices", headers=h).json()["items"]}
    assert {"BADLAR", "TPM", "UVA"} <= cods
    r = client.post("/api/creditos/indices", headers=h, json={"codigo": "cer", "nombre": "CER", "valor": 33})
    assert r.status_code == 201 and r.json()["codigo"] == "CER"
    iid = r.json()["id"]
    assert client.put(f"/api/creditos/indices/{iid}", headers=h, json={"codigo": "CER", "nombre": "CER", "valor": 35}).json()["valor"] == 35
    assert client.post(f"/api/creditos/indices/{iid}/baja", headers=h).json()["activo"] is False


def test_producto_tasa_variable_indice_margen(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Var"}).json()
    cfg = {**p["cfg"], "modalidad": "VARIABLE", "indice": "BADLAR", "margen": 8}
    r = client.put(f"/api/creditos/productos/{p['id']}/config", headers=h, json=cfg)
    assert r.status_code == 200
    assert r.json()["cfg"]["indice"] == "BADLAR" and r.json()["cfg"]["margen"] == 8
