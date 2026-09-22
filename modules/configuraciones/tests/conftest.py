"""Base de tests: SQLite en memoria y cliente HTTP contra la app real."""
import os

# La config (app.config.Settings) se lee al importar la app: las variables van antes. Se FIJAN (no
# setdefault): el contenedor de tests hereda las del compose y los tests usan las suyas.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría
# saldría a la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk_on(conn, _):   # SQLite no aplica ON DELETE CASCADE sin esto
    conn.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

TODOS = ("impuestos", "indices", "feriados", "workflow")


@pytest.fixture(autouse=True)
def db():
    """Esquema limpio por test; la app usa esta misma sesión."""
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


def gateway(*acciones: str, user_id: int = 7, username: str = "ana") -> dict:
    """Headers tal como los arma el gateway (acciones sin el prefijo del módulo)."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"configuraciones:{a}" for a in acciones)}


@pytest.fixture
def admin():
    """Lee y escribe todo."""
    return gateway(*(f"{x}:{y}" for x in TODOS for y in ("read", "write")))


@pytest.fixture
def lector():
    return gateway(*(f"{x}:read" for x in TODOS), user_id=8, username="luis")


@pytest.fixture
def interna():
    return {"X-Api-Key": "clave-de-test"}
