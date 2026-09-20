"""Maestro de clientes: alta con CUIL único (la DB es árbitro) + idempotencia (H-154)."""
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


def test_alta_cliente_cuil_unico_y_dv(client):
    """CUIL único (constraint = árbitro): dos altas con el mismo CUIL y distinto código → 409, no
    duplicado. CUIL con dígito verificador inválido → 422."""
    h = _auth(client)
    base = {"id_cliente": "T001", "cuil": "20111111112", "apellido_nombre": "TEST UNO"}
    assert client.post("/api/creditos/clientes", headers=h, json=base).status_code == 201
    # mismo CUIL, distinto código → 409 (no crea duplicado)
    assert client.post("/api/creditos/clientes", headers=h, json={**base, "id_cliente": "T002"}).status_code == 409
    # CUIL con DV inválido → 422
    assert client.post("/api/creditos/clientes", headers=h,
                       json={**base, "id_cliente": "T003", "cuil": "27234567818"}).status_code == 422
    # sólo quedó 1 con ese CUIL
    items = client.get("/api/creditos/clientes?q=20111111112", headers=h).json()["items"]
    assert len([c for c in items if c["cuil"] == "20111111112"]) == 1


def test_id_cliente_autogenerado(client):
    """H-169: el id_cliente del maestro se AUTOGENERA (CL-<pk>), no es el CUIL ni un N° de solicitud.
    Si el alta no manda código, el backend lo genera a partir del PK; un código explícito (ETL) se respeta."""
    h = _auth(client)
    r = client.post("/api/creditos/clientes", headers=h,
                    json={"cuil": "20111111112", "apellido_nombre": "SIN CODIGO"})
    assert r.status_code == 201
    c = r.json()
    assert c["id_cliente"] == f"CL-{c['id']:06d}"        # autogenerado del PK
    assert c["id_cliente"] != c["cuil"] and not c["id_cliente"].startswith("SOL-")
    # un código explícito (migración/ETL) se respeta tal cual
    r2 = client.post("/api/creditos/clientes", headers=h,
                     json={"id_cliente": "9988776655", "cuil": "20222222223", "apellido_nombre": "LEGACY"})
    assert r2.status_code == 201 and r2.json()["id_cliente"] == "9988776655"


def test_escritura_cliente_exige_permiso_backend(client):
    """H-156/H-205: el nivel por área se enforca también en el BACKEND (defensa en profundidad detrás del
    gateway). Con sólo `clientes:read` no se crea/edita (403); con `clientes:write` sí."""
    gw = lambda *perms: {"X-User-Id": "901", "X-Username": "pz.clientes", "X-User-Permissions": ",".join(perms)}
    body = {"id_cliente": "RB1", "cuil": "20111111112", "apellido_nombre": "RBAC"}
    assert client.post("/api/creditos/clientes", headers=gw("creditos:clientes:read"), json=body).status_code == 403
    assert client.post("/api/creditos/clientes", headers=gw("creditos:clientes:read", "creditos:clientes:write"),
                       json=body).status_code == 201


def test_alta_cliente_idempotente(client):
    """Idempotency-Key: reintento con la misma clave no crea dos clientes (devuelve el mismo)."""
    h = {**_auth(client), "Idempotency-Key": "cliente-k1"}
    body = {"id_cliente": "IDEM1", "cuil": "20111111112", "apellido_nombre": "IDEM"}
    r1 = client.post("/api/creditos/clientes", headers=h, json=body)
    r2 = client.post("/api/creditos/clientes", headers=h, json=body)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]        # mismo cliente, no duplicado
