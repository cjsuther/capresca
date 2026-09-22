"""Base de tests: SQLite en memoria por test y cliente HTTP contra la app real."""
import os

# La config (app/config.py) se lee al importar la app: las variables van antes.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "secreto-de-test")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_HOURS", "8")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.module import Module
from app.models.permission import Permission, UserPermission
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import hash_password

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


# ── Fábricas ─────────────────────────────────────────────────────────


@pytest.fixture
def crear_usuario(db):
    def _crear(username="jperez", password="Secreta123!", email=None,
               full_name="Juan Pérez", is_active=True):
        user = User(
            username=username,
            email=email or f"{username}@sistema.local",
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _crear


@pytest.fixture
def crear_modulo(db):
    def _crear(code="cajeros", name="Cajeros", is_active=True):
        mod = Module(code=code, name=name, description=None, icon=None, is_active=is_active)
        db.add(mod)
        db.commit()
        db.refresh(mod)
        return mod

    return _crear


@pytest.fixture
def crear_permiso(db):
    def _crear(module, code="transactions:read", description="Ver transacciones"):
        perm = Permission(module_id=module.id, code=code, description=description)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm

    return _crear


@pytest.fixture
def crear_rol(db):
    def _crear(name="cajero", permisos=(), is_active=True, description="Rol de prueba"):
        rol = Role(name=name, description=description, is_active=is_active)
        rol.permissions = list(permisos)
        db.add(rol)
        db.commit()
        db.refresh(rol)
        return rol

    return _crear


@pytest.fixture
def override_directo(db):
    """Alta de un permiso directo sobre el usuario (granted=True concede, False deniega)."""

    def _crear(user, permission, granted=True):
        up = UserPermission(user_id=user.id, permission_id=permission.id, granted=granted)
        db.add(up)
        db.commit()
        return up

    return _crear
