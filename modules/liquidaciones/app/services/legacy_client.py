"""
Cliente HTTP hacia el módulo `legacy` (integración VFP9).

Liquidaciones lo puede usar para obtener liquidaciones (cajaliq) y juegos
(maejuegos) vivos del mirror del legacy, como complemento del flujo por ZIP.
Degradación elegante: si el legacy está apagado/caído, devuelve vacío y se sigue
operando con el flujo de archivos.
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


async def get_juegos() -> list[dict]:
    return await _get("/internal/legacy/juegos", default=[])


async def get_cajaliq(agencia: str | None = None, pagado: bool | None = None) -> list[dict]:
    params = {}
    if agencia is not None:
        params["agencia"] = agencia
    if pagado is not None:
        params["pagado"] = str(pagado).lower()
    return await _get("/internal/legacy/cajaliq", params=params or None, default=[])
