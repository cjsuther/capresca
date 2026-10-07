"""Créditos (API interna): los lotes de solicitudes que pagan las órdenes de pago.

Créditos es el dueño de los lotes: dice qué resoluciones / disposiciones tienen lotes para pagar, los
reserva para una orden (los deja PARA_LIQUIDAR y devuelve una transferencia por crédito) y los libera si
la orden se anula. Sus rechazos (409/422) llegan tal cual a la pantalla; si no responde, 503.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.config import settings

TIMEOUT = 60.0      # reservar origina los créditos de todos los lotes


def _llamar(metodo: str, path: str, **kw) -> dict:
    url = f"{settings.creditos_service_url.rstrip('/')}/internal/creditos/ordenes-pago{path}"
    try:
        r = httpx.request(metodo, url, headers={"X-Api-Key": settings.internal_api_key}, timeout=TIMEOUT, **kw)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"Créditos no responde: {e}")
    if r.status_code in (404, 409, 422):
        try:
            detalle = r.json().get("detail")
        except ValueError:
            detalle = r.text
        raise HTTPException(r.status_code, detalle or "Créditos rechazó el pedido.")
    if r.status_code >= 400:
        raise HTTPException(503, f"Créditos respondió {r.status_code}.")
    return r.json()


def disponibles() -> dict:
    return _llamar("GET", "/disponibles")


def reservar(orden_id: int, codigo: str, usuario: str, actos: list[str]) -> dict:
    return _llamar("POST", "/reservar", json={"orden_id": orden_id, "codigo": codigo, "usuario": usuario,
                                              "actos": actos})


def liberar(orden_id: int) -> dict:
    return _llamar("POST", "/liberar", json={"orden_id": orden_id})


def callback_url() -> str:
    return f"{settings.creditos_service_url.rstrip('/')}/internal/creditos/tesoreria/resultado"
