"""Base de tests: SQLite en memoria, plan sembrado y cliente HTTP contra la app real."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.seed import sembrar

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    s = TestSession()
    sembrar(s)

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
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"contabilidad:{p}" for p in permisos)}


@pytest.fixture
def contador():
    """Contable con todos los permisos del módulo."""
    return gateway("contador", "asientos:read", "asientos:write", "definiciones:write", "ejercicios:write")


@pytest.fixture
def solo_lectura():
    return gateway("auditor", "asientos:read")


# ── Datos de prueba ──────────────────────────────────────────────────────────────────────────────
def transaccion(**kw):
    from datetime import date
    base = {"modulo": "creditos", "tipo": "DESEMBOLSO", "referencia": "CTO-1",
            "fecha": date.today().isoformat(), "descripcion": "Desembolso del contrato CTO-1",
            "datos": {"capital": 100000, "gastos": 2000, "iva": 420}}
    base.update(kw)
    return base


DEFINICION_DESEMBOLSO = {
    "modulo": "creditos", "tipo": "DESEMBOLSO", "nombre": "Desembolso de crédito", "diario_codigo": "BANCO",
    "leyenda": "Desembolso {referencia}",
    "lineas": [
        {"cuenta": "1.1.04", "dc": "DEBE", "importe": "capital + gastos", "detalle": "Préstamo otorgado"},
        {"cuenta": "1.1.02", "dc": "HABER", "importe": "capital", "detalle": "Transferencia al cliente"},
        {"cuenta": "4.1.03", "dc": "HABER", "importe": "gastos", "detalle": "Cargo de otorgamiento"},
    ],
}
