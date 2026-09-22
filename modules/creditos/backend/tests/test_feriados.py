"""Feriados: el calendario lo administra el módulo Configuraciones; el motor de cuotas lo lee de ahí."""
from datetime import date

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


def test_el_abm_de_feriados_ya_no_esta_en_creditos(client):
    h = _auth(client)
    assert client.get("/api/creditos/feriados?pais=AR", headers=h).status_code == 404
    assert client.post("/api/creditos/feriados", headers=h,
                       json={"fecha": "2030-06-17", "nombre": "x"}).status_code == 404


def test_el_motor_usa_el_calendario_de_configuraciones(client, config_falsa):
    """Un feriado cargado en Configuraciones (uno movible, que el motor no conoce de memoria) corre el
    vencimiento al día hábil siguiente."""
    _auth(client)
    from app.api.productos import _feriados_engine
    from app.core.database import SessionLocal
    from app.services.productos_calc import cronograma
    anio = date.today().year + 1
    puente = date(anio, 6, 10)
    while puente.weekday() >= 4:          # un lunes a jueves, para que el siguiente sea hábil
        puente = date(anio, 6, puente.day + 1)
    config_falsa.agregar_feriado(puente)
    with SessionLocal() as db:
        fset = _feriados_engine(db)
    assert puente in fset
    f = cronograma("FRANCES", 100000, 1, 52, fecha_valor=date(anio, 5, puente.day), dia_pago=puente.day,
                   primer_venc_dias=31, ajuste_fin_semana="SIGUIENTE_HABIL", feriados=fset)
    assert str(f[0]["fecha_vencimiento"]) == date(anio, 6, puente.day + 1).isoformat()


def test_el_calendario_se_pide_una_vez_y_no_por_cada_simulacion(client, config_falsa):
    _auth(client)
    from app.api.productos import _feriados_engine
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        for _ in range(5):
            _feriados_engine(db)
    assert config_falsa.pedidos.count("/feriados") == 1
