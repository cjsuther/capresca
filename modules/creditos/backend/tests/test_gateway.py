"""Integración con Portezuelo: identidad y permisos que inyecta el gateway (H-205)."""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.core.database import SessionLocal


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:   # corre el lifespan (siembra productos y workflow)
        yield c


def _gw(username: str, *perms: str, user_id: int = 900) -> dict:
    """Headers tal como los arma el gateway (routes/proxy.py)."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(perms)}


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_gateway_crea_usuario_local_y_toma_sus_permisos(client):
    h = _gw("pz.operador", "creditos:creditos:write", "creditos:aprobaciones:aprobar", "cajeros:rules:read")
    for _ in range(2):   # el segundo acceso reusa el Usuario local
        r = client.get("/api/creditos/productos", headers=h)
        assert r.status_code == 200, r.text
        # los permisos de otros módulos (cajeros:*) no cuentan
        assert r.json()["permisos"] == {"edita": True, "aprueba": True}
    with SessionLocal() as db:
        u = db.query(models.Usuario).filter_by(username="pz.operador").all()
        assert len(u) == 1 and u[0].perfil == "SSO"   # se crea una sola vez


def test_gateway_sin_identidad_es_401(client):
    assert client.get("/api/creditos/productos").status_code == 401
    assert client.get("/api/creditos/contratos/tablero").status_code == 401
    # Un id no numérico no es una identidad válida del gateway.
    assert client.get("/api/creditos/productos", headers=_gw("x", user_id=0) | {"X-User-Id": "abc"}).status_code == 401


def test_capacidades_de_creditos_salen_de_los_permisos(client):
    solo_lectura = _gw("pz.lector", "creditos:creditos:read")
    assert client.get("/api/creditos/productos", headers=solo_lectura).json()["permisos"] == {"edita": False, "aprueba": False}
    editor = _gw("pz.editor", "creditos:creditos:write", "creditos:creditos:read")
    assert client.get("/api/creditos/productos", headers=editor).json()["permisos"] == {"edita": True, "aprueba": False}
    supervisor = _gw("pz.super", "creditos:creditos:read", "creditos:aprobaciones:supervisar")
    assert client.get("/api/creditos/productos", headers=supervisor).json()["permisos"] == {"edita": False, "aprueba": True}


def test_la_configuracion_del_workflow_no_vive_en_creditos(client):
    """Las reglas se administran en el módulo Configuraciones (con su permiso `workflow:write`)."""
    admin = _auth(client)
    assert client.get("/api/creditos/workflow", headers=admin).status_code == 404
    assert client.put("/api/creditos/workflow/LINEA", headers=admin, json={"activo": True}).status_code == 404


def test_rechazar_pendiente_exige_aprobador(client):
    """H-205: sin regla activa, rechazar un pendiente exige el permiso de aprobación."""
    admin = _auth(client)
    from tests.config_falsa import CONFIG
    CONFIG.activar("DESEMBOLSO")
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=admin).json()["items"] if p["codigo"] == "LP-PERS-01")
    cid = client.post("/api/creditos/contratos/originar", headers=admin, json={
        "producto_id": pers["id"], "cliente_nombre": "RECHAZO-GATE", "monto": 500_000, "plazo": 12,
        "desembolsar": False}).json()["id"]
    pid = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=admin).json()["pendienteId"]
    CONFIG.activar("DESEMBOLSO", False)

    sin_aprobacion = _gw("pz.editor", "creditos:creditos:write", "creditos:creditos:read")
    r = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/rechazar", headers=sin_aprobacion, json={"motivo": "x"})
    assert r.status_code == 403, r.text
    aprobador = _gw("pz.aprobador", "creditos:creditos:read", "creditos:aprobaciones:aprobar")
    r = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/rechazar", headers=aprobador, json={"motivo": "x"})
    assert r.status_code == 200 and r.json()["rechazado"] is True
