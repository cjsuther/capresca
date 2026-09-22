"""Impuestos e índices: los administra el módulo Configuraciones; Créditos los lee para armar productos."""
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


def test_impuestos_vienen_de_configuraciones(client, config_falsa):
    h = _auth(client)
    r = client.get("/api/creditos/impuestos", headers=h)
    assert r.status_code == 200
    assert [i["codigo"] for i in r.json()["items"]] == ["IIBB-CAT", "IVA105", "IVA21", "SELLOS"]
    config_falsa.impuestos[0]["activo"] = False
    config_falsa._cambio()
    activos = client.get("/api/creditos/impuestos?estado=activos", headers=h).json()["items"]
    assert "IIBB-CAT" not in {i["codigo"] for i in activos}
    assert "/impuestos" in config_falsa.pedidos


def test_indices_vienen_de_configuraciones(client):
    h = _auth(client)
    cods = {i["codigo"] for i in client.get("/api/creditos/indices", headers=h).json()["items"]}
    assert cods == {"BADLAR", "TPM", "UVA"}


def test_el_abm_ya_no_esta_en_creditos(client):
    """Alta, edición y bajas se hacen en Configuraciones: Créditos no expone escrituras."""
    h = _auth(client)
    assert client.post("/api/creditos/impuestos", headers=h, json={"codigo": "X", "nombre": "X"}).status_code == 405
    assert client.post("/api/creditos/indices", headers=h, json={"codigo": "X", "nombre": "X"}).status_code == 405
    assert client.post("/api/creditos/impuestos/1/baja", headers=h).status_code == 404


def test_catalogos_se_cachean(client, config_falsa):
    """El armado de productos no le pega a Configuraciones en cada pedido (caché corta)."""
    h = _auth(client)
    for _ in range(3):
        client.get("/api/creditos/impuestos", headers=h)
    assert config_falsa.pedidos.count("/impuestos") == 1


def test_producto_tasa_variable_indice_margen(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Var"}).json()
    cfg = {**p["cfg"], "modalidad": "VARIABLE", "indice": "BADLAR", "margen": 8}
    r = client.put(f"/api/creditos/productos/{p['id']}/config", headers=h, json=cfg)
    assert r.status_code == 200
    assert r.json()["cfg"]["indice"] == "BADLAR" and r.json()["cfg"]["margen"] == 8
