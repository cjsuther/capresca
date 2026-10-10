"""Seguridad de config (H-112): en producción la app no arranca con el JWT_SECRET default del código."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./_cfg.db")

import pytest


def test_produccion_rechaza_secreto_default():
    from app.core.config import Settings, JWT_SECRET_INSEGURO
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret=JWT_SECRET_INSEGURO, _env_file=None)


def test_produccion_con_secreto_propio_ok():
    from app.core.config import Settings
    s = Settings(environment="production", jwt_secret="un-secreto-propio-largo-de-mas-de-32-caracteres",
                 _env_file=None)
    assert s.jwt_secret.startswith("un-secreto-propio")


def test_produccion_con_secreto_corto_o_vacio_no_arranca():
    """Variable sin definir en el compose = secreto vacío: se podrían forjar tokens del portal."""
    import pytest
    from app.core.config import Settings
    for secreto in ("", "corto"):
        with pytest.raises(ValueError):
            Settings(environment="production", jwt_secret=secreto, _env_file=None)


def test_development_permite_default():
    from app.core.config import Settings, JWT_SECRET_INSEGURO
    s = Settings(environment="development", jwt_secret=JWT_SECRET_INSEGURO, _env_file=None)
    assert s.environment == "development"
