"""El gateway registra en Auditoría toda operación que modifica datos (y los intentos rechazados)."""
import asyncio

import pytest

from app.config import settings
from app.services import auditoria


@pytest.fixture
def cola(monkeypatch):
    """Cola real, sin la tarea que envía: se inspecciona lo que el gateway encoló."""
    monkeypatch.setattr(settings, "auditoria_internal_api_key", "clave")
    monkeypatch.setattr(settings, "auditoria_habilitada", True)
    q = asyncio.Queue()
    monkeypatch.setattr(auditoria, "_cola", q)
    return q


def eventos(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_sin_clave_configurada_no_registra_nada(monkeypatch, cola):
    monkeypatch.setattr(settings, "auditoria_internal_api_key", "")
    assert auditoria.habilitada() is False
    auditoria.registrar({"ruta": "/api/x"})          # no explota ni encola
    assert eventos(cola) == []


def test_una_escritura_deja_su_evento(client, cola, auth, permisos):
    permisos({"security": ["users:read", "users:write"]})
    client.post("/api/security/users", headers=auth(username="admin"), json={"username": "x"})
    e = eventos(cola)[0]
    assert e["modulo"] == "security" and e["metodo"] == "POST" and e["ruta"] == "/api/security/users"
    assert e["origen"] == "GATEWAY" and e["estado_http"] == 200 and e["usuario"] == "admin"
    assert e["usuario_id"] == 7 and e["request_id"]


def test_las_lecturas_no_se_auditan(client, cola, auth, permisos):
    permisos({"security": ["users:read"]})
    client.get("/api/security/users", headers=auth())
    assert eventos(cola) == []


def test_el_login_registra_el_acceso_sin_la_clave(client, cola, httpx_falso):
    client.post("/api/auth/login", json={"username": "ana", "password": "secreta"})
    e = eventos(cola)[0]
    assert e["operacion"] == "ACCESO" and e["usuario"] == "ana" and e["modulo"] == "security"
    assert "secreta" not in str(e)


def test_un_intento_sin_permiso_tambien_queda_registrado(client, cola, auth, permisos):
    permisos({"clientes": ["clients:read"]})
    r = client.post("/api/security/users", headers=auth(username="beto"), json={})
    assert r.status_code == 403
    e = eventos(cola)[0]
    assert e["exito"] is False and e["estado_http"] == 403 and e["usuario"] == "beto"
    assert "denegado" in e["descripcion"] and "security:users:write" in e["descripcion"]


def test_el_modulo_recibe_el_id_de_la_operacion_para_cruzarla(client, cola, auth, permisos):
    """El módulo recibe X-Request-Id y lo devuelve con el detalle: así se une gateway ↔ módulo."""
    falso = permisos({"security": ["users:read", "users:write"]})
    client.post("/api/security/users", headers=auth(), json={"username": "x"})
    reenvio = [ll for ll in falso.llamadas if ll["metodo"] == "POST"][-1]
    assert reenvio["headers"]["X-Request-Id"] == eventos(cola)[0]["request_id"]


def test_si_el_modulo_no_responde_igual_queda_el_intento(client, cola, auth, permisos):
    import httpx
    falso = permisos({"security": ["users:read", "users:write"]})
    client.get("/api/security/users", headers=auth())     # deja los permisos en caché
    eventos(cola)
    falso.error = httpx.ConnectError("caído")             # ahora se cae el módulo destino

    r = client.post("/api/security/users", headers=auth(), json={})

    assert r.status_code == 502
    assert eventos(cola)[0]["estado_http"] == 502
