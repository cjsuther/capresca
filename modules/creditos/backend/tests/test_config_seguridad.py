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
    s = Settings(environment="production", jwt_secret="un-secreto-propio-largo-123", _env_file=None)
    assert s.jwt_secret == "un-secreto-propio-largo-123"


def test_development_permite_default():
    from app.core.config import Settings, JWT_SECRET_INSEGURO
    s = Settings(environment="development", jwt_secret=JWT_SECRET_INSEGURO, _env_file=None)
    assert s.environment == "development"
