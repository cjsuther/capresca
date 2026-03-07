"""
Middleware de autenticación y autorización del API Gateway.

Flujo:
  1. Extraer JWT del header Authorization
  2. Validar firma localmente (sin llamar al módulo security)
  3. Obtener permisos del usuario (con caché de 60 s)
  4. Verificar que el usuario tiene el permiso requerido para la ruta
  5. Reenviar la solicitud al microservicio correspondiente
"""
import time
import logging
from typing import Optional

import httpx
from cachetools import TTLCache
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routes.mapping import get_service_url, get_required_permission

logger = logging.getLogger("proxy.auth")

# Caché de permisos: key=user_id, value=permissions_dict, TTL=60s
_permissions_cache: TTLCache = TTLCache(maxsize=1000, ttl=settings.permissions_cache_ttl)

# Rutas que no requieren autenticación
PUBLIC_PATHS = {"/api/auth/login", "/api/auth/refresh", "/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ── Rutas públicas ────────────────────────────────────────
        if path in PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # ── Validar JWT ───────────────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Token requerido"})

        token = auth_header.split(" ", 1)[1]
        payload = self._decode_token(token)
        if payload is None:
            return JSONResponse(status_code=401, content={"detail": "Token inválido o expirado"})

        user_id: int = int(payload["sub"])

        # ── Obtener permisos del usuario (con caché) ──────────────
        permissions = await self._get_permissions(user_id)
        if permissions is None:
            return JSONResponse(status_code=503, content={"detail": "Servicio de seguridad no disponible"})

        # ── Verificar permiso requerido para la ruta ──────────────
        required = get_required_permission(request.method, path)
        if required and not self._has_permission(permissions, required):
            logger.warning("Acceso denegado user_id=%s ruta=%s permiso=%s", user_id, path, required)
            return JSONResponse(status_code=403, content={"detail": "Acceso denegado", "required": required})

        # ── Inyectar user_id en headers para los microservicios ───
        headers = dict(request.headers)
        headers["X-User-Id"] = str(user_id)
        headers["X-Username"] = payload.get("username", "")

        # Continuar al router de proxy (lo maneja routes/proxy.py)
        request.state.user_id = user_id
        request.state.username = payload.get("username", "")
        request.state.permissions = permissions
        return await call_next(request)

    def _decode_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except JWTError:
            return None

    async def _get_permissions(self, user_id: int) -> Optional[dict]:
        if user_id in _permissions_cache:
            return _permissions_cache[user_id]

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.security_service_url}/internal/permissions/{user_id}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    _permissions_cache[user_id] = data
                    return data
        except httpx.RequestError as e:
            logger.error("Error consultando permisos: %s", e)

        return None

    @staticmethod
    def _has_permission(permissions: dict, required: str) -> bool:
        """
        required tiene formato 'module:action' ej: 'cajeros:requests:read'
        permissions["actions"] es { "cajeros": ["requests:read", ...] }
        """
        parts = required.split(":", 1)
        if len(parts) != 2:
            return False
        module, action = parts
        return action in permissions.get("actions", {}).get(module, [])
