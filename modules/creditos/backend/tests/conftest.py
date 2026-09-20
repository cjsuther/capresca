"""Configuración de pytest: base de datos limpia y aislada por test.

Todos los módulos de test comparten un único engine (se crea al importar
`app.core.database`). Para evitar que el estado se filtre entre tests, este
fixture autouse recrea el esquema y resiembra los datos demo antes de cada test.
"""
import os

# Fijar el entorno ANTES de importar la app (el engine se crea al importarla).
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_test_ccypp.db"
os.environ["ENVIRONMENT"] = "development"

import pytest

from app.core.database import Base, engine, SessionLocal
from app.seed import seed
from tests import gateway_emulado  # noqa: F401  (login de prueba + headers X-User-* como el gateway)

# Acelerar los tests: bcrypt es costoso y aquí se resiembra por cada test.
# Se reemplaza el hashing por uno trivial (no se evalúa la fuerza del hash).
import app.seed as _seed_mod
import app.core.security as _sec_mod


def _fast_hash(pw: str) -> str:
    return "test$" + pw


def _fast_verify(pw: str, hashed: str) -> bool:
    return hashed == "test$" + pw


_sec_mod.hash_password = _fast_hash
_sec_mod.verify_password = _fast_verify
_seed_mod.hash_password = _fast_hash


# Módulos de test que NO usan la base de datos (motor de dominio puro).
_SIN_DB = ("test_motor_cuotas", "test_equivalencia_real", "test_equivalencia_mora")


@pytest.fixture(autouse=True)
def fresh_db(request):
    if request.module.__name__ in _SIN_DB:
        yield
        return
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
        # Parámetros de canal (H-185): obligatorios en la API, se siembran también en tests.
        from app.api.productos import seed_canales_parametros
        seed_canales_parametros(db)
    yield
    Base.metadata.drop_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    for f in ("_test_ccypp.db",):
        if os.path.exists(f):
            os.remove(f)
