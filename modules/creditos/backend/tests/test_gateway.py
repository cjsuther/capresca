"""Integración con Portezuelo: identidad y permisos por área que inyecta el gateway (H-205)."""
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


def test_gateway_crea_usuario_local_y_expone_areas(client):
    h = _gw("pz.operador", "creditos:caja:read", "creditos:creditos:write",
            "creditos:aprobaciones:aprobar", "cajeros:rules:read")
    for _ in range(2):   # el segundo acceso reusa el Usuario local
        r = client.get("/api/creditos/auth/mis-permisos", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["usuario"] == "pz.operador"
        assert d["areas"] == {"caja": "CONSULTA", "creditos": "ESCRITURA"}   # los de otros módulos se ignoran
        assert d["roles"] == ["APROBAR"]
    with SessionLocal() as db:
        u = db.query(models.Usuario).filter_by(username="pz.operador").all()
        assert len(u) == 1 and u[0].perfil == "SSO"   # se crea una sola vez


def test_gateway_sin_identidad_es_401(client):
    assert client.get("/api/creditos/auth/mis-permisos").status_code == 401
    assert client.get("/api/creditos/contratos/tablero").status_code == 401
    # Un id no numérico no es una identidad válida del gateway.
    assert client.get("/api/creditos/auth/mis-permisos", headers=_gw("x", user_id=0) | {"X-User-Id": "abc"}).status_code == 401


def test_capacidades_de_creditos_salen_de_los_permisos(client):
    solo_lectura = _gw("pz.lector", "creditos:creditos:read")
    assert client.get("/api/creditos/productos", headers=solo_lectura).json()["permisos"] == {"edita": False, "aprueba": False}
    editor = _gw("pz.editor", "creditos:creditos:write", "creditos:creditos:read")
    assert client.get("/api/creditos/productos", headers=editor).json()["permisos"] == {"edita": True, "aprueba": False}
    supervisor = _gw("pz.super", "creditos:creditos:read", "creditos:aprobaciones:supervisar")
    assert client.get("/api/creditos/productos", headers=supervisor).json()["permisos"] == {"edita": False, "aprueba": True}


def test_workflow_roles_de_aprobacion(client):
    admin = _auth(client)
    wf = client.get("/api/creditos/workflow", headers=admin).json()
    assert wf["perfiles"] == ["APROBAR", "SUPERVISAR"] and wf["puedeEditar"] is True
    nivel = next(r for r in wf["reglas"] if r["objeto"] == "LINEA")["niveles"][0]
    assert nivel["rol"] == "APROBAR"
    # Un perfil VFP ya no es un rol válido para un nivel.
    r = client.put(f"/api/creditos/workflow/niveles/{nivel['id']}", headers=admin,
                   json={"nombre": "Aprobación", "rol": "ADMG", "cuatroOjos": True})
    assert r.status_code == 422
    # Configurar el workflow exige escritura de Seguridad.
    lector = _gw("pz.lector", "creditos:seguridad:read")
    assert client.get("/api/creditos/workflow", headers=lector).json()["puedeEditar"] is False
    assert client.put("/api/creditos/workflow/LINEA", headers=lector, json={"activo": True}).status_code == 403


def test_rechazar_pendiente_exige_aprobador(client):
    """H-205: sin regla activa, rechazar un pendiente exige el permiso de aprobación."""
    admin = _auth(client)
    client.put("/api/creditos/workflow/DESEMBOLSO", headers=admin, json={"activo": True})
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=admin).json()["items"] if p["codigo"] == "LP-PERS-01")
    cid = client.post("/api/creditos/contratos/originar", headers=admin, json={
        "producto_id": pers["id"], "cliente_nombre": "RECHAZO-GATE", "monto": 500_000, "plazo": 12,
        "desembolsar": False}).json()["id"]
    pid = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=admin).json()["pendienteId"]
    client.put("/api/creditos/workflow/DESEMBOLSO", headers=admin, json={"activo": False})

    sin_aprobacion = _gw("pz.editor", "creditos:creditos:write", "creditos:creditos:read")
    r = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/rechazar", headers=sin_aprobacion, json={"motivo": "x"})
    assert r.status_code == 403, r.text
    aprobador = _gw("pz.aprobador", "creditos:creditos:read", "creditos:aprobaciones:aprobar")
    r = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/rechazar", headers=aprobador, json={"motivo": "x"})
    assert r.status_code == 200 and r.json()["rechazado"] is True
