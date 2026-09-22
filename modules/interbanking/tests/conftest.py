"""Base de tests: SQLite temporal por test, cliente HTTP contra la app real y
una "red falsa" que reemplaza a httpx (ninguna llamada sale a Internet).
"""
import os

# La config se lee al importar la app: las variables de entorno van antes.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
# Dominios admitidos para las URLs del proveedor (en producción: interbanking.com.ar).
os.environ.setdefault("ALLOWED_PROVIDER_DOMAINS", "interbanking.local,ib.test,interbanking.com.ar")
os.environ.setdefault("INTERBANKING_BASE_URL", "https://api.test.interbanking.local")
os.environ.setdefault("INTERBANKING_AUTH_URL", "https://preauth.test.interbanking.local")
# Cualquier string sirve: config.get_fernet() deriva los 32 bytes con sha256.
os.environ.setdefault("ENCRYPTION_KEY", "clave-de-test-interbanking")
os.environ.setdefault("NOTIFICATIONS_SERVICE_URL", "http://notifications-test:8005")
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría
# saldría a la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, Date, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import DATETIME as SQLITE_DATETIME
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.expression import Cast

import app.models  # noqa: F401  (registra todas las tablas en el metadata)
from app.config import encrypt_secret
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.credentials import InterbankingCredential
from app.services import mock_transfers
from app.services.notifications_client import notifications_client


# ─── Adaptadores de tipos Postgres → SQLite (sólo para tests, no tocan modelos) ───

@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    """En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid)."""
    return "INTEGER"


@compiles(JSONB, "sqlite")
def _jsonb_como_json(type_, compiler, **kw):
    """JSONB no existe en SQLite; JSON alcanza (serializa/deserializa igual)."""
    return "JSON"


@compiles(Cast, "sqlite")
def _cast_a_date_como_postgres(element, compiler, **kw):
    """`cast(col, Date)` en SQLite tiene afinidad NUMERIC y devolvería 2026 en vez de
    la fecha. `date(col)` reproduce la semántica de Postgres que usa el código."""
    if isinstance(element.type, Date):
        return "date(%s)" % compiler.process(element.clause, **kw)
    return compiler.visit_cast(element, **kw)


_bind_datetime_original = SQLITE_DATETIME.bind_processor


def _bind_datetime_tolerante(self, dialect):
    """Los filtros de auditoría comparan la columna contra un string 'yyyy-mm-dd'.
    Postgres castea ese texto a timestamp; SQLite rechaza cualquier valor que no sea
    datetime, así que lo dejamos pasar (el formato guardado ordena lexicográficamente).
    """
    procesar = _bind_datetime_original(self, dialect)
    return lambda valor: valor if isinstance(valor, str) else procesar(valor)


SQLITE_DATETIME.bind_processor = _bind_datetime_tolerante

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
    return {"X-User-Id": "7", "X-Username": "cris"}


# ─────────────────────────── Red falsa (httpx mockeado) ───────────────────────────

def _respuesta(status: int, body=None, texto=None) -> httpx.Response:
    pedido = httpx.Request("GET", "https://mock.interbanking.local")
    if texto is not None:
        return httpx.Response(status, text=texto, request=pedido)
    return httpx.Response(status, json=body if body is not None else {}, request=pedido)


class RedFalsa:
    """Reemplaza `httpx.post`/`httpx.request`: ninguna llamada sale a la red.

    `ruta(fragmento, ...)` registra la respuesta de las URLs que lo contienen;
    una URL sin ruta registrada hace fallar el test.
    """

    def __init__(self):
        self.llamadas: list[dict] = []
        self._rutas: list[tuple] = []

    def ruta(self, fragmento, body=None, status=200, texto=None, error=None):
        self._rutas.append((fragmento, body, status, texto, error))
        return self

    def limpiar_rutas(self):
        self._rutas.clear()
        return self

    def token(self, **kw):
        """Ruta del endpoint OAuth de Interbanking."""
        kw.setdefault("body", {"access_token": "tok-" + "a" * 30,
                               "token_type": "Bearer", "expires_in": 3600})
        return self.ruta("/cas/oidc/accessToken", **kw)

    def __call__(self, method, url, **kw):
        self.llamadas.append({"method": method, "url": str(url), **kw})
        for fragmento, body, status, texto, error in self._rutas:
            if fragmento in str(url):
                if error is not None:
                    raise error
                return _respuesta(status, body, texto)
        raise AssertionError(f"Llamada HTTP sin mockear: {method} {url}")

    def llamadas_a(self, fragmento) -> list[dict]:
        return [ll for ll in self.llamadas if fragmento in ll["url"]]

    @property
    def ultima(self) -> dict:
        return self.llamadas[-1]


@pytest.fixture(autouse=True)
def red(monkeypatch):
    r = RedFalsa()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: r("POST", url, **kw))
    monkeypatch.setattr(httpx, "request", lambda method, url, **kw: r(method, url, **kw))
    return r


@pytest.fixture(autouse=True)
def notificaciones(monkeypatch):
    """Captura los avisos al módulo de notificaciones sin salir a la red."""
    enviadas: list[dict] = []
    monkeypatch.setattr(notifications_client, "notify", lambda **kw: enviadas.append(kw))
    return enviadas


@pytest.fixture(autouse=True)
def _mock_transfers_limpio():
    """La tabla en memoria de mock_transfers es global: se limpia entre tests."""
    mock_transfers._MOCK_DB.clear()
    mock_transfers._NEXT_ID = 100000
    yield
    mock_transfers._MOCK_DB.clear()


@pytest.fixture
def cred(db):
    """Credencial activa con ambos secretos cargados (cifrados)."""
    c = InterbankingCredential(
        name="Capresca",
        base_url="https://api.ib.test",
        auth_url="https://auth.ib.test",
        client_id="cli-123",
        client_secret_encrypted=encrypt_secret("secreto-cc"),
        username="usuario.ib",
        password_encrypted=encrypt_secret("pass-ib"),
        service_url="https://api.ib.test/svc",
        customer_id="CUST-1",
        consolidation_account_number="46600513539",
        consolidation_account_type="CC",
        consolidation_bank_number="011",
        consolidation_currency="ARS",
        payment_account_number="99900011122",
        payment_account_type="CC",
        payment_bank_number="011",
        payment_currency="ARS",
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def sin_mock(monkeypatch):
    """Apaga el modo mock de transferencias para ejercitar las llamadas reales."""
    from app.config import settings
    monkeypatch.setattr(settings, "interbanking_mock_transfers", False)
    return settings
