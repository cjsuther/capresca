"""Las solicitudes que otorga una resolución de Despacho (API interna).

El acto lo emite Despacho, pero la solicitud es de Créditos: acá viven las reglas de qué puede
entrar en un anexo y la garantía de que una solicitud no quede otorgada dos veces.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models as m
from app.core.config import get_settings
from app.core.database import SessionLocal

CLAVE = "clave-despacho-test"
SOLICITUDES = "/internal/creditos/anexo/solicitudes"
ASIGNAR = "/internal/creditos/anexo/asignar"
QUITAR = "/internal/creditos/anexo/quitar"


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clave(monkeypatch):
    monkeypatch.setattr(get_settings(), "despacho_internal_api_key", CLAVE)


@pytest.fixture
def h():
    return {"X-Api-Key": CLAVE}


@pytest.fixture
def solicitudes():
    """Solicitudes aprobadas y cubicadas, que es lo que entra al anexo."""
    creadas = []
    db = SessionLocal()
    proximo = {"id": 90000}

    def _crear(cantidad=2, linea=8050, estado="A", cubica="C", **extra):
        hechas = []
        for i in range(cantidad):
            proximo["id"] += 1
            s = m.SolicitudCredito(id=proximo["id"], cuil=f"2030504757{i}",
                                   apellido_nombre=f"PEREZ {i}", dni="30504757",
                                   montosol=100000 + i, linea=linea, estado=estado,
                                   cubica=cubica, **extra)
            db.add(s)
            hechas.append(s)
        db.commit()
        for s in hechas:
            db.refresh(s)
        creadas.extend(hechas)
        return hechas

    yield _crear
    for s in creadas:
        db.delete(db.merge(s))
    db.commit()
    db.close()


def test_ofrece_las_aprobadas_y_cubicadas_del_rango_de_lineas(client, h, solicitudes):
    solicitudes(2, linea=8050)                       # AGAP
    solicitudes(1, linea=6800)                       # Productivos
    r = client.get(f"{SOLICITUDES}?linea_min=8050&linea_max=8051", headers=h)
    assert r.status_code == 200
    assert r.json()["cantidad"] == 2
    assert all(8050 <= i["linea"] <= 8051 for i in r.json()["items"])


def test_no_ofrece_las_que_no_estan_aprobadas_ni_cubicadas(client, h, solicitudes):
    solicitudes(1, estado="I")                       # todavía en trámite
    solicitudes(1, cubica="D")                       # sin fondos asignados
    aprobada = solicitudes(1)[0]
    d = client.get(SOLICITUDES, headers=h).json()
    assert [i["id"] for i in d["items"]] == [aprobada.id]


def test_asignar_deja_el_numero_de_resolucion_en_la_solicitud(client, h, solicitudes):
    ss = solicitudes(2)
    a = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [s.id for s in ss],
                                              "numero_resolucion": 45,
                                              "fecha_resolucion": "2026-06-10"})
    assert a.status_code == 200 and a.json()["asignadas"] == 2

    db = SessionLocal()
    s = db.get(m.SolicitudCredito, ss[0].id)
    # El lote ES el número de la resolución, como en el sistema anterior.
    assert (s.no_resol, s.lote, s.en_reso) == (45, 45, True)
    assert s.fecha_resol == date(2026, 6, 10)
    db.close()

    # Ya no es candidata, pero sí aparece al pedir su lote (para reimprimir el anexo).
    assert all(i["id"] != ss[0].id for i in client.get(SOLICITUDES, headers=h).json()["items"])
    d = client.get(f"{SOLICITUDES}?lote=45", headers=h).json()
    assert d["cantidad"] == 2 and d["items"][0]["numero_resolucion"] == 45


def test_una_solicitud_no_entra_en_dos_resoluciones(client, h, solicitudes):
    ss = solicitudes(1)
    client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id], "numero_resolucion": 45})
    otra = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id],
                                                 "numero_resolucion": 46})
    assert otra.status_code == 422 and "otra resolución" in otra.json()["detail"]

    # Reasignarla a la MISMA resolución no es un error: es corregir el anexo.
    igual = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id],
                                                  "numero_resolucion": 45})
    assert igual.status_code == 200


def test_quitar_la_devuelve_a_las_candidatas(client, h, solicitudes):
    ss = solicitudes(1)
    client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id], "numero_resolucion": 45})
    q = client.post(QUITAR, headers=h, json={"solicitud_ids": [ss[0].id]})
    assert q.status_code == 200 and q.json()["quitadas"] == 1
    assert any(i["id"] == ss[0].id for i in client.get(SOLICITUDES, headers=h).json()["items"])


def test_sin_la_clave_interna_no_se_entra(client, solicitudes):
    assert client.get(SOLICITUDES).status_code == 401
    assert client.get(SOLICITUDES, headers={"X-Api-Key": "otra"}).status_code == 401
    assert client.post(ASIGNAR, headers={"X-Api-Key": "otra"},
                       json={"solicitud_ids": [1], "numero_resolucion": 1}).status_code == 401


def test_una_solicitud_inexistente_se_rechaza(client, h, solicitudes):
    ss = solicitudes(1)
    r = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id, 999999],
                                              "numero_resolucion": 45})
    assert r.status_code == 422 and "no existe" in r.json()["detail"]
