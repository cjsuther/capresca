"""Base de tests: SQLite en memoria y cliente HTTP contra la app real."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
os.environ["PURGA_HABILITADA"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    s = TestSession()

    def _get_db():
        yield s

    app.dependency_overrides[get_db] = _get_db
    try:
        yield s
    finally:
        s.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def interna():
    return {"X-Api-Key": "clave-de-test"}


def gateway(username="ana", *permisos, user_id=7):
    """Headers que inyecta el gateway para un usuario con esos permisos del módulo."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"auditoria:{p}" for p in permisos)}


@pytest.fixture
def auditor():
    return gateway("auditor", "eventos:read")
