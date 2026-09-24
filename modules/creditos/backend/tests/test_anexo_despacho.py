"""Las solicitudes que otorga una resolución de Despacho (API interna).

El acto lo emite Despacho, pero la solicitud es de Créditos: acá viven las reglas de qué puede
entrar en un anexo y la garantía de que una solicitud no quede otorgada dos veces.
"""
from datetime import date

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import models_productos as m
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
def producto():
    """Un producto con su versión, que es lo que agrupa el anexo."""
    db = SessionLocal()
    p = db.query(m.PPProducto).first()
    assert p is not None, "el seed debe dejar al menos un producto"
    pid, nombre = p.id, p.nombre
    db.close()
    return SimpleNamespace(id=pid, nombre=nombre)


@pytest.fixture
def solicitudes(producto):
    """Solicitudes APROBADAS, que es lo que entra al anexo."""
    creadas = []
    db = SessionLocal()
    proximo = {"n": 0}

    def _crear(cantidad=2, estado="APROBADA", producto_id=None):
        hechas = []
        for i in range(cantidad):
            proximo["n"] += 1
            s = m.PPSolicitud(numero=f"ANX-{proximo['n']:05d}", estado=estado,
                              solicitante_tipo="NO_REGISTRADO",
                              cliente_datos={"apellido_nombre": f"PEREZ {i}",
                                             "cuil": f"2030504757{i}", "dni": "30504757"},
                              producto_id=producto_id or producto.id,
                              monto_solicitado=100000 + i)
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


def test_ofrece_las_aprobadas_del_producto(client, h, solicitudes, producto):
    solicitudes(2)
    r = client.get(f"{SOLICITUDES}?producto_id={producto.id}", headers=h)
    assert r.status_code == 200 and r.json()["cantidad"] == 2
    assert all(i["producto"] == producto.nombre for i in r.json()["items"])
    assert all(i["apellido_nombre"].startswith("PEREZ") for i in r.json()["items"])


def test_los_tipos_son_los_productos(client, h, producto):
    d = client.get("/internal/creditos/anexo/tipos", headers=h).json()
    assert {"tipo": producto.id, "nombre": producto.nombre} in d


def test_no_ofrece_las_que_no_estan_aprobadas(client, h, solicitudes):
    solicitudes(1, estado="EN_EVALUACION")
    solicitudes(1, estado="BORRADOR")
    aprobada = solicitudes(1)[0]
    d = client.get(SOLICITUDES, headers=h).json()
    assert [i["id"] for i in d["items"]] == [aprobada.id]


def test_no_se_otorga_algo_que_no_esta_aprobado(client, h, solicitudes):
    """Una resolución no puede alcanzar una solicitud todavía en evaluación."""
    s = solicitudes(1, estado="EN_EVALUACION")[0]
    r = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [s.id], "numero_resolucion": 45})
    assert r.status_code == 422 and "no están aprobadas" in r.json()["detail"]


def test_asignar_deja_el_numero_de_resolucion_en_la_solicitud(client, h, solicitudes):
    ss = solicitudes(2)
    a = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [s.id for s in ss],
                                              "numero_resolucion": 45,
                                              "fecha_resolucion": "2026-06-10"})
    assert a.status_code == 200 and a.json()["asignadas"] == 2

    db = SessionLocal()
    s = db.get(m.PPSolicitud, ss[0].id)
    # El lote ES el número de la resolución, como en el sistema anterior.
    assert (s.numero_resolucion, s.lote_resolucion, s.en_resolucion) == (45, 45, True)
    assert s.fecha_resolucion == date(2026, 6, 10)
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
                       json={"solicitud_ids": ["x"], "numero_resolucion": 1}).status_code == 401


def test_una_solicitud_inexistente_se_rechaza(client, h, solicitudes):
    ss = solicitudes(1)
    r = client.post(ASIGNAR, headers=h, json={"solicitud_ids": [ss[0].id, "no-existe"],
                                              "numero_resolucion": 45})
    assert r.status_code == 422 and "no existe" in r.json()["detail"]
