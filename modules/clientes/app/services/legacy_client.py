"""
Cliente HTTP hacia el módulo `legacy` (integración VFP9).

Clientes lo usa para sembrar/contrastar agencias (maeagencias) y clientes de la
cartera de créditos (maeclientes) contra el mirror del legacy. Degradación
elegante: si el legacy está apagado/caído, devuelve vacío sin romper.
"""
import httpx

from app.config import settings

_BASE = settings.legacy_service_url
_HEADERS = {"X-Api-Key": settings.legacy_internal_api_key}


async def _get(path: str, params: dict | None = None, default=None):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{_BASE}{path}", params=params, headers=_HEADERS, timeout=8.0)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[legacy_client] GET {path} falló (degradado): {e}")
        return default


async def get_agencias() -> list[dict]:
    return await _get("/internal/legacy/agencias", default=[])


async def get_maeclientes(cuil: str | None = None) -> list[dict]:
    params = {"cuil": cuil} if cuil else None
    return await _get("/internal/legacy/maeclientes", params=params, default=[])
