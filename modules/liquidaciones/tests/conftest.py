"""Base de tests: SQLite en memoria, app real y servicios externos stubbeados."""
import os
import pathlib

# La config se lee al importar la app: todo el entorno va antes del primer import de `app`.
# Se pisa (no setdefault) porque el contenedor trae los valores reales del compose.
os.environ.update({
    # Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría saldría
    # a la red en cada flush.
    "AUDITORIA_INTERNAL_API_KEY": "",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "INTERNAL_API_KEY": "clave-de-test",
    "CONCILIACION_SERVICE_URL": "http://conciliacion-test:8006",
    "CLIENTES_SERVICE_URL": "http://clientes-test:8003",
    "NOTIFICATIONS_SERVICE_URL": "http://notifications-test:8005",
    "LEGACY_SERVICE_URL": "http://legacy-test:8009",
    "LEGACY_INTERNAL_API_KEY": "clave-legacy-test",
    # El scheduler de ingesta no debe arrancar ni tocar el filesystem real.
    "INBOX_ENABLED": "false",
    "INBOX_SCAN_ON_STARTUP": "false",
    "INBOX_DIR": "/tmp/liquidaciones-inbox-test",
})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services import processing

# Los modelos se registran en Base al importarlos: sin esto create_all no ve las tablas.
from app.models import archivo, batch, detalle_raw, procesada, resumen_raw, validacion  # noqa: F401


# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid): los ids
# quedarían en NULL. Sólo aplica al dialecto de tests.
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


class ServiciosFalsos:
    """Doble de los módulos externos: nada sale a la red durante los tests."""

    def __init__(self):
        self.agencias = {"000123", "000456"}
        self.error_clientes = None
        self.error_conciliacion = None
        self.envios = []
        self.notificaciones = []

    def clientes(self):
        if self.error_clientes:
            raise self.error_clientes
        return set(self.agencias)

    def conciliacion(self, db, lote):
        if self.error_conciliacion:
            raise self.error_conciliacion
        self.envios.append(lote.id)

    def notify(self, **kwargs):
        self.notificaciones.append(kwargs)


@pytest.fixture(autouse=True)
def servicios(monkeypatch):
    """Reemplaza clientes/conciliación/notificaciones en el pipeline de procesamiento."""
    falsos = ServiciosFalsos()
    monkeypatch.setattr(processing, "get_registered_agency_numbers", falsos.clientes)
    monkeypatch.setattr(processing, "send_to_conciliacion", falsos.conciliacion)
    monkeypatch.setattr(processing.notifications_client, "notify", falsos.notify)
    return falsos


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def h():
    """Headers que inyecta el gateway para el usuario 7."""
    return {"X-User-Id": "7"}


@pytest.fixture
def hk():
    """Header de autenticación de los endpoints internos."""
    return {"X-Api-Key": "clave-de-test"}


@pytest.fixture
def api_key(hk):
    return hk


@pytest.fixture
def inbox():
    """Directorio de entrada (INBOX_DIR): el único lugar del que /process acepta leer."""
    import shutil
    from app.config import settings
    ruta = pathlib.Path(settings.inbox_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    yield ruta
    shutil.rmtree(ruta, ignore_errors=True)
