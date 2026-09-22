"""Base de tests: SQLite en memoria y cliente HTTP contra la app real."""
import os

# La config (app.config.Settings) se lee al importar la app: las variables van antes.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("LEGACY_SERVICE_URL", "http://legacy-test:8009")
os.environ.setdefault("LEGACY_INTERNAL_API_KEY", "clave-de-test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid).
# Sólo aplica al dialecto de tests.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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


# ── Helpers de alta ─────────────────────────────────────────────
@pytest.fixture
def crear_ph(client, h):
    """Crea una persona física y devuelve el JSON del cliente."""
    def _crear(nombre="Juan", apellido="Pérez", documento="20304050", **extra):
        payload = {
            "email": extra.pop("email", f"{nombre.lower()}@example.com"),
            "phone": extra.pop("phone", None),
            "city": extra.pop("city", "Mendoza"),
            "profile": {
                "first_name": nombre,
                "last_name": apellido,
                "document_type": "DNI",
                "document_number": documento,
            },
        }
        payload.update(extra)
        r = client.post("/api/clientes/human", json=payload, headers=h)
        assert r.status_code == 201, r.text
        return r.json()

    return _crear


@pytest.fixture
def crear_pj(client, h):
    """Crea una persona jurídica y devuelve el JSON del cliente."""
    def _crear(razon_social="Agencia Sur S.A.", cuit="30-71234567-8", agencia=None, **extra):
        payload = {
            "email": extra.pop("email", "contacto@agenciasur.com"),
            "city": extra.pop("city", "San Rafael"),
            "profile": {
                "legal_name": razon_social,
                "trade_name": extra.pop("trade_name", "Agencia Sur"),
                "tax_id": cuit,
                "tax_id_type": "CUIT",
                "agency_number": agencia,
            },
        }
        payload.update(extra)
        r = client.post("/api/clientes/legal", json=payload, headers=h)
        assert r.status_code == 201, r.text
        return r.json()

    return _crear
