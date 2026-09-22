"""Base de tests del gateway: JWT propio y un httpx falso (nunca se sale a la red)."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("JWT_SECRET", "secreto-de-test")

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import app
from app.middleware import auth as auth_mod


@pytest.fixture(autouse=True)
def cache_limpia():
    """La caché de permisos es global (TTLCache): se limpia entre tests."""
    auth_mod._permissions_cache.clear()
    yield
    auth_mod._permissions_cache.clear()


@pytest.fixture
def client():
    return TestClient(app)


def token_de(user_id: int = 7, username: str = "ana", minutos: int = 60, secreto: str | None = None) -> str:
    payload = {"sub": str(user_id), "username": username,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=minutos)}
    return jwt.encode(payload, secreto or settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth():
    """Headers de un usuario autenticado."""
    return lambda **kw: {"Authorization": f"Bearer {token_de(**kw)}"}


class RespuestaFalsa:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.content = content if content else (b"{}" if json_data is None else b"")
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._json


class ClienteFalso:
    """Reemplazo de httpx.AsyncClient: registra las llamadas y devuelve lo que se le indique."""

    llamadas: list = []
    respuesta_permisos = None
    respuesta_destino = None
    error = None

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        ClienteFalso.llamadas.append({"metodo": "GET", "url": url, "headers": kw.get("headers", {})})
        if ClienteFalso.error is not None:
            raise ClienteFalso.error
        return ClienteFalso.respuesta_permisos or RespuestaFalsa(200, {"modules": [], "actions": {}})

    async def request(self, method, url, headers=None, content=None, **kw):
        ClienteFalso.llamadas.append({"metodo": method, "url": url, "headers": headers or {}, "body": content})
        if ClienteFalso.error is not None:
            raise ClienteFalso.error
        return ClienteFalso.respuesta_destino or RespuestaFalsa(200, {"ok": True}, content=b'{"ok":true}')


@pytest.fixture
def httpx_falso(monkeypatch):
    """Parchea httpx.AsyncClient en el middleware y en el router. Devuelve la clase para configurarla."""
    ClienteFalso.llamadas = []
    ClienteFalso.respuesta_permisos = None
    ClienteFalso.respuesta_destino = None
    ClienteFalso.error = None
    monkeypatch.setattr(auth_mod.httpx, "AsyncClient", ClienteFalso)
    from app.routes import proxy as proxy_mod
    monkeypatch.setattr(proxy_mod.httpx, "AsyncClient", ClienteFalso)
    return ClienteFalso


@pytest.fixture
def permisos(httpx_falso):
    """Configura los permisos que devuelve security para el usuario."""
    def _set(actions: dict):
        httpx_falso.respuesta_permisos = RespuestaFalsa(200, {"modules": sorted(actions), "actions": actions})
        return httpx_falso
    return _set
