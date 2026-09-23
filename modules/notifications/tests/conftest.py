"""Base de tests: SQLite temporal por test y cliente HTTP contra la app real."""
import os

# La config se lee al importar la app: el DATABASE_URL de test va antes.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría
# saldría a la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid): los ids de las
# tablas con BigInteger quedarían en NULL. Sólo aplica al dialecto de tests.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


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


@pytest.fixture
def h():
    """Headers que inyecta el gateway para el usuario 7."""
    return {"X-User-Id": "7"}
