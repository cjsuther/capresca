"""
Cliente HTTP hacia el módulo `legacy` (integración VFP9).

Degradación elegante: timeouts cortos + try/except → fallback a vacío/None, de
modo que si el módulo legacy está apagado o caído, la conciliación sigue
funcionando con sus propios datos (el legacy es opcional).

Lecturas: sirven del mirror del módulo legacy (funcionan aun con la integración
apagada). Escrituras: encolan en el outbox del legacy (202); nunca tocan las DBF
en caliente.
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


async def get_pagos(fecha: str | None = None, agencia: str | None = None) -> list[dict]:
    params = {k: v for k, v in {"fecha": fecha, "agencia": agencia}.items() if v}
    return await _get("/internal/legacy/pagos", params=params, default=[])


async def get_formas_pago(no_recibo: int) -> list[dict]:
    return await _get("/internal/legacy/formas-pago", params={"no_recibo": no_recibo}, default=[])


async def get_creditos_seguros(fecha: str | None = None) -> list[dict]:
    params = {"fecha": fecha} if fecha else None
    return await _get("/internal/legacy/creditos-seguros", params=params, default=[])


async def enqueue_aplicar_pago(payload: dict, *, user_id: int | None = None) -> dict | None:
    """Encola la aplicación de un pago en el legacy (outbox). Devuelve {outbox_id,...} o None."""
    return await _post("/internal/legacy/pagos", payload, user_id=user_id)


async def enqueue_anular_pago(no_recibo: int, motivo: str | None = None, *, user_id: int | None = None) -> dict | None:
    return await _post(f"/internal/legacy/pagos/{no_recibo}/anular", {"motivo": motivo}, user_id=user_id)


async def _post(path: str, json: dict, *, user_id: int | None = None) -> dict | None:
    headers = dict(_HEADERS)
    headers["X-Origin-Module"] = "conciliacion"
    if user_id is not None:
        headers["X-User-Id"] = str(user_id)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{_BASE}{path}", json=json, headers=headers, timeout=8.0)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[legacy_client] POST {path} falló (degradado): {e}")
        return None
