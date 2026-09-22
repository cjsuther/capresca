"""
Base de tests del módulo legacy.

La configuración se lee al importar la app, así que todas las variables de entorno
(incluidas las rutas del share y del sandbox) se fijan ANTES de importar `app.*`.
Nunca se toca un share SMB real: las DBF de prueba se generan en tmp_path.
"""
import os
import tempfile

# Raíces temporales de proceso: garantizan que ningún test escriba en /data.
_TMP_ROOT = tempfile.mkdtemp(prefix="legacy-tests-")

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("INTERNAL_API_KEY", "clave-interna-de-test")
os.environ.setdefault("NOTIFICATIONS_SERVICE_URL", "http://notifications-de-test:8005")
os.environ.setdefault("SMB_MOUNT_ROOT", os.path.join(_TMP_ROOT, "agjs"))
os.environ.setdefault("SANDBOX_WRITE_ROOT", os.path.join(_TMP_ROOT, "agjs_sandbox"))
os.environ.setdefault("INTEGRATION_ENABLED", "true")
os.environ.setdefault("WRITE_MODE", "outbox_only")
os.environ.setdefault("ALLOW_REAL_DRAIN", "false")
# El scheduler sólo arranca en el lifespan; igual lo dejamos apagado por defecto.
os.environ.setdefault("SYNC_ENABLED", "false")
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría
# saldría a la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

import dbf as dbflib  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import BigInteger, create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.notifications_client import notifications_client  # noqa: E402

API_KEY = "clave-interna-de-test"


# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid): los ids
# quedarían en NULL. Sólo aplica al dialecto de tests.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    return "INTEGER"


# Los modelos usan JSONB (Postgres); en SQLite se mapea al JSON genérico.
@compiles(JSONB, "sqlite")
def _jsonb_como_json(type_, compiler, **kw):
    return "JSON"


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


@pytest.fixture(autouse=True)
def config_por_defecto(monkeypatch):
    """Cada test arranca con la configuración por defecto del módulo (nada se filtra)."""
    monkeypatch.setattr(settings, "integration_enabled", True)
    monkeypatch.setattr(settings, "write_mode", "outbox_only")
    monkeypatch.setattr(settings, "allow_real_drain", False)
    monkeypatch.setattr(settings, "internal_api_key", API_KEY)


@pytest.fixture(autouse=True)
def notificaciones(monkeypatch):
    """Ningún test sale a la red: se captura lo que el módulo intenta notificar."""
    enviadas = []
    monkeypatch.setattr(notifications_client, "notify",
                        lambda **kw: enviadas.append(kw))
    return enviadas


@pytest.fixture
def client():
    # Sin `with`: no se dispara el lifespan y por lo tanto no arranca el scheduler.
    return TestClient(app)


@pytest.fixture
def auth():
    """Headers de los endpoints internos (contenedor-a-contenedor)."""
    return {"X-Api-Key": API_KEY}


# ── DBF de prueba ──────────────────────────────────────────────────────────────

# Estructuras mínimas que cubren los campos que leen sync_spec y dbf_writer.
ESTRUCTURAS = {
    "maeagencias": "COD_AGEN C(10); TITULAR C(40)",
    "maejuegos": "COD_JUEGO C(5); DESCRIP C(40); MODALIDAD C(3)",
    "cajaliq": ("COD_AGEN C(10); COD_JUEGO C(5); NO_SORTEO C(8); IMPORTE C(15); "
                "INTERESES C(15); PAGADO L; FECHA_PAGO C(10); NO_RECIBO C(10)"),
    "cajapagos": ("NO_RECIBO C(10); COD_AGEN C(10); FECHA_PAGO C(10); ORIGEN C(20); "
                  "TOTAL C(15); BONOS C(15); PESOS C(15); CAJERO C(20)"),
    "cajaforpag": ("NO_RECIBO C(10); SNO_RECIBO C(5); MONEDA C(5); ORIGEN C(20); "
                   "FECHA_PAGO C(10); ANULADO L"),
    "cajacreseg": ("NRECIBO C(10); RECOFI C(10); ORIGEN C(20); FECHA_PAGO C(10); "
                   "VIA_PAGO C(20); USU_PAGO C(20)"),
    "maeclientes": "CUIL C(15); NOMBRE C(40); DOMICILIO C(40)",
    "maecuotas": "NO_CREDITO C(10); NO_CUOTA C(5); ESTADO C(2); FECHA_VTO C(10); TOTAL_VDO C(15)",
}

SUBDIR = {
    "maeagencias": "juegos", "maejuegos": "juegos",
    "cajaliq": "caja", "cajapagos": "caja", "cajaforpag": "caja", "cajacreseg": "caja",
    "maeclientes": "creditos", "maecuotas": "creditos",
}


def _escribir_dbf(raiz, tabla, filas):
    """Crea (o reescribe) la DBF `tabla` bajo `raiz/<subdir>/` con las filas dadas."""
    destino = os.path.join(str(raiz), SUBDIR[tabla])
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, f"{tabla}.dbf")
    if os.path.exists(ruta):
        os.remove(ruta)
    t = dbflib.Table(ruta, ESTRUCTURAS[tabla], codepage="cp1252")
    t.open(dbflib.READ_WRITE)
    try:
        for fila in filas:
            t.append(fila)
    finally:
        t.close()
    return ruta


def _leer_dbf(ruta):
    """Devuelve las filas de una DBF como dicts con strings stripeados."""
    t = dbflib.Table(ruta)
    t.open(dbflib.READ_ONLY)
    try:
        return [
            {n.upper(): (v.strip() if isinstance(v, str) else v)
             for n, v in zip(t.field_names, tuple(rec))}
            for rec in t
        ]
    finally:
        t.close()


@pytest.fixture
def escribir_dbf():
    """Helper para fabricar DBF de prueba: escribir_dbf(raiz, tabla, filas) -> ruta."""
    return _escribir_dbf


@pytest.fixture
def leer_dbf():
    """Helper para releer una DBF y verificar lo que escribió el módulo."""
    return _leer_dbf


@pytest.fixture
def share(tmp_path, monkeypatch):
    """Share legacy simulado (read-only en producción): apunta settings.smb_mount_root acá."""
    raiz = tmp_path / "agjs"
    raiz.mkdir()
    monkeypatch.setattr(settings, "smb_mount_root", str(raiz))
    return raiz


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Copia sandbox donde SÍ se puede escribir (nunca el share productivo)."""
    raiz = tmp_path / "agjs_sandbox"
    raiz.mkdir()
    monkeypatch.setattr(settings, "sandbox_write_root", str(raiz))
    return raiz
