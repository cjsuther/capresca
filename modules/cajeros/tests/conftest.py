"""Base de tests: SQLite temporal por test y clientes HTTP contra la app real."""
import os

# La config se lee al importar la app: el DATABASE_URL de test va antes.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("NOTIFICATIONS_SERVICE_URL", "http://notifications-de-test:8005")
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría
# saldría a la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Los modelos que no cuelgan de los routers montados igual tienen que estar
# registrados para que create_all arme todas las tablas.
from app import models as _models  # noqa: F401
from app.models.authorization_rule import AuthorizationRule  # noqa: F401
from app.models.transaction import Transaction, TransactionRuleTrigger  # noqa: F401
from app.routers import limits, operations, relations, requests
from app.services.notifications_client import notifications_client


# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid): los ids de las
# tablas con BigInteger quedarían en NULL. Sólo aplica al dialecto de tests.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# main.py sólo monta rules y transactions. Los routers de límites, relaciones, solicitudes y
# operaciones existen pero quedaron sin montar (ver informe): se prueban sobre esta app de test.
app_extra = FastAPI(title="Cajeros (routers no montados)")
PREFIX = "/api/cajeros"
app_extra.include_router(limits.router, prefix=PREFIX)
app_extra.include_router(operations.router, prefix=PREFIX)
app_extra.include_router(relations.router, prefix=PREFIX)
app_extra.include_router(requests.router, prefix=PREFIX)


@pytest.fixture(autouse=True)
def db():
    """Esquema limpio por test; las apps usan esta misma sesión."""
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    app_extra.dependency_overrides[get_db] = _get_db
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        app_extra.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def anyio_backend():
    """Los tests async corren sobre asyncio (el plugin de anyio viene con fastapi)."""
    return "asyncio"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def client_extra():
    """Cliente sobre los routers que main.py no monta."""
    return TestClient(app_extra)


@pytest.fixture
def h():
    """Headers que inyecta el gateway para el usuario 7 (el cajero de los tests)."""
    return {"X-User-Id": "7", "X-Username": "cajero7"}


@pytest.fixture
def h_auth():
    """Headers del autorizador (usuario 20)."""
    return {"X-User-Id": "20", "X-Username": "jefe20"}


@pytest.fixture(autouse=True)
def notificaciones(monkeypatch):
    """Nada de red: se registran las llamadas al cliente de notifications."""
    enviadas = {"notify": [], "notify_many": []}

    async def _notify(**kwargs):
        enviadas["notify"].append(kwargs)

    async def _notify_many(notifications):
        enviadas["notify_many"].append(notifications)

    monkeypatch.setattr(notifications_client, "notify", _notify)
    monkeypatch.setattr(notifications_client, "notify_many", _notify_many)
    return enviadas
