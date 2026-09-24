"""Base de tests de Despacho: SQLite en memoria y la identidad que inyecta el gateway."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría saldría a
# la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine("sqlite+pysqlite:///:memory:",
                       connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk_on(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def gateway(*acciones, user_id=7, username="despacho"):
    """Las cabeceras que inyecta el gateway después de resolver los permisos."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"despacho:{a}" for a in acciones)}


TODO = ("resoluciones:read", "resoluciones:write", "resoluciones:firmar",
        "modelos:write", "expedientes:write", "importar")


@pytest.fixture
def h():
    """Un usuario de Despacho con todos los permisos del módulo."""
    return gateway(*TODO)


@pytest.fixture
def solo_lectura():
    return gateway("resoluciones:read")


@pytest.fixture
def modelo(client, h):
    """Un modelo de resolución, que es lo que alimenta el combo 'Modelo a utilizar'."""
    def _crear(descripcion="TRANSFERENCIA", tipo="RES", plantilla="<p>VISTO: …</p>"):
        r = client.post("/api/despacho/modelos", headers=h,
                        json={"descripcion": descripcion, "tipo": tipo, "plantilla": plantilla})
        assert r.status_code == 201, r.text
        return r.json()
    return _crear


@pytest.fixture
def resolucion(client, h):
    """Una resolución en borrador."""
    def _crear(**extra):
        datos = {"tipo": "RES", "asunto": "Otorgamiento de créditos", "organo": "DIRECTORIO"}
        datos.update(extra)
        r = client.post("/api/despacho/resoluciones", headers=h, json=datos)
        assert r.status_code == 201, r.text
        return r.json()
    return _crear
