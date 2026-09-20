"""Módulo Utilidades / Tablas: ABMs de tablas maestras."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_alta_y_edicion_de_linea(client):
    h = _auth(client)
    nueva = {
        "nombre": "Turismo Santa María", "cartera": 9, "tipo_calculo": 1,
        "tna": "36", "por_afecta": "25", "plazo_max": 24, "monto_max": "800000",
    }
    r = client.post("/api/creditos/admin/lineas", headers=h, json=nueva)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]

    # editar la TNA
    nueva["tna"] = "40"
    r = client.put(f"/api/creditos/admin/lineas/{lid}", headers=h, json=nueva)
    assert r.status_code == 200
    assert r.json()["tna"] == "40.000"

    # aparece en el listado operativo de líneas activas
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    assert any(l["id"] == lid for l in lineas)


def test_abm_organismo_y_parametro(client):
    h = _auth(client)
    o = client.post("/api/creditos/admin/organismos", headers=h,
                    json={"codigo": "POLICIA", "nombre": "Policía de la Provincia"})
    assert o.status_code == 201

    # upsert de parámetro (crea y luego actualiza)
    p1 = client.post("/api/creditos/admin/parametros", headers=h,
                     json={"clave": "IVA_GENERAL", "valor": "21", "descripcion": "Alícuota IVA"})
    assert p1.status_code == 201
    p2 = client.post("/api/creditos/admin/parametros", headers=h,
                     json={"clave": "IVA_GENERAL", "valor": "10.5"})
    assert p2.json()["valor"] == "10.5"
    # sigue habiendo un solo parámetro con esa clave
    todos = client.get("/api/creditos/admin/parametros", headers=h).json()
    assert sum(1 for x in todos if x["clave"] == "IVA_GENERAL") == 1


def test_abm_proveedores(client):
    h = _auth(client)
    r = client.post("/api/creditos/admin/proveedores", headers=h, json={
        "razon_social": "LIBRERIA CENTRAL SRL", "cuit": "30712345678",
        "contacto": "JUAN PEREZ", "localidad": "S.F.V. CATAMARCA", "tipo_iva": "RI"})
    assert r.status_code == 201
    pid = r.json()["id"]
    lista = client.get("/api/creditos/admin/proveedores", headers=h).json()
    assert any(p["id"] == pid and p["razon_social"] == "LIBRERIA CENTRAL SRL" for p in lista)
    # búsqueda por CUIT
    r2 = client.get("/api/creditos/admin/proveedores?q=30712345678", headers=h).json()
    assert len(r2) == 1
