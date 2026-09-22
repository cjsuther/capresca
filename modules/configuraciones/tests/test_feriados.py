"""Calendario de feriados."""
from datetime import date

import pytest

from app.services import feriados as svc


@pytest.fixture
def sin_fuente_oficial(monkeypatch):
    monkeypatch.setattr("app.routers.feriados.desde_nager", lambda pais, anio: None)


def test_pascua_y_feriados_moviles_ar():
    assert svc.pascua(2026) == date(2026, 4, 5)
    fechas = {f: n for f, n, _ in svc.ar_calculados(2026)}
    assert fechas[date(2026, 4, 3)] == "Viernes Santo"
    assert fechas[date(2026, 2, 16)] == "Carnaval (lunes)" and fechas[date(2026, 2, 17)] == "Carnaval (martes)"
    assert len(fechas) == 11


def test_alta_listado_por_anio_y_duplicado(client, admin):
    r = client.post("/api/configuraciones/feriados", headers=admin,
                    json={"fecha": "2026-06-17", "nombre": " Güemes ", "tipo": "TRASLADABLE"})
    assert r.status_code == 201 and r.json()["nombre"] == "Güemes" and r.json()["origen"] == "MANUAL"
    client.post("/api/configuraciones/feriados", headers=admin, json={"fecha": "2027-01-01", "nombre": "Año nuevo"})
    d = client.get("/api/configuraciones/feriados?pais=AR&anio=2026", headers=admin).json()
    assert [f["fecha"] for f in d["items"]] == ["2026-06-17"] and d["anios"] == [2026, 2027]
    assert client.post("/api/configuraciones/feriados", headers=admin,
                       json={"fecha": "2026-06-17", "nombre": "otro"}).status_code == 409


def test_validaciones(client, admin):
    assert client.post("/api/configuraciones/feriados", headers=admin,
                       json={"pais": "ZZ", "fecha": "2026-06-17", "nombre": "x"}).status_code == 422
    assert client.post("/api/configuraciones/feriados", headers=admin,
                       json={"fecha": "2026-06-17", "nombre": "x", "tipo": "RARO"}).status_code == 422


def test_editar_y_borrar(client, admin):
    f = client.post("/api/configuraciones/feriados", headers=admin, json={"fecha": "2026-06-17", "nombre": "Güemes"}).json()
    otro = client.post("/api/configuraciones/feriados", headers=admin, json={"fecha": "2026-06-20", "nombre": "Belgrano"}).json()
    assert client.put(f"/api/configuraciones/feriados/{otro['id']}", headers=admin,
                      json={"fecha": "2026-06-17", "nombre": "choca"}).status_code == 409
    r = client.put(f"/api/configuraciones/feriados/{f['id']}", headers=admin,
                   json={"fecha": "2026-06-15", "nombre": "Güemes (trasladado)", "activo": False})
    assert r.json()["fecha"] == "2026-06-15" and r.json()["activo"] is False
    assert client.delete(f"/api/configuraciones/feriados/{f['id']}", headers=admin).json() == {"ok": True}
    assert client.delete(f"/api/configuraciones/feriados/{f['id']}", headers=admin).status_code == 404


def test_importar_ar_sin_fuente_oficial_usa_el_calculo_y_es_idempotente(client, admin, sin_fuente_oficial):
    r = client.post("/api/configuraciones/feriados/importar", headers=admin, json={"pais": "AR", "anio": 2026}).json()
    assert r["importados"] == 11 and r["fuente"].startswith("cálculo local")
    r = client.post("/api/configuraciones/feriados/importar", headers=admin, json={"pais": "AR", "anio": 2026}).json()
    assert r["importados"] == 0


def test_importar_no_revive_un_feriado_dado_de_baja(client, admin, sin_fuente_oficial):
    f = client.post("/api/configuraciones/feriados", headers=admin,
                    json={"fecha": "2026-12-08", "nombre": "Inmaculada", "activo": False}).json()
    client.post("/api/configuraciones/feriados/importar", headers=admin, json={"pais": "AR", "anio": 2026})
    items = client.get("/api/configuraciones/feriados?anio=2026", headers=admin).json()["items"]
    assert next(x for x in items if x["id"] == f["id"])["activo"] is False


def test_importar_otro_pais_sin_fuente_es_502(client, admin, sin_fuente_oficial):
    assert client.post("/api/configuraciones/feriados/importar", headers=admin,
                       json={"pais": "UY", "anio": 2026}).status_code == 502


def test_importar_desde_la_fuente_oficial(client, admin, monkeypatch):
    monkeypatch.setattr("app.routers.feriados.desde_nager",
                        lambda pais, anio: [(date(anio, 7, 18), "Jura de la Constitución", "INAMOVIBLE")])
    r = client.post("/api/configuraciones/feriados/importar", headers=admin, json={"pais": "UY", "anio": 2026}).json()
    assert r["importados"] == 1 and r["fuente"].startswith("OFICIAL")


def test_escribir_sin_permiso_es_403(client, lector):
    assert client.post("/api/configuraciones/feriados", headers=lector,
                       json={"fecha": "2026-06-17", "nombre": "x"}).status_code == 403
    assert client.post("/api/configuraciones/feriados/importar", headers=lector,
                       json={"anio": 2026}).status_code == 403
    assert client.get("/api/configuraciones/feriados/paises", headers=lector).json()["items"][0]["codigo"] == "AR"
