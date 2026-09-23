"""Envío de eventos al módulo Auditoría.

El registro no puede frenar ni voltear una operación del usuario: los eventos van a una cola en
memoria y los manda una tarea aparte, en lotes. Si Auditoría no responde, se pierde el lote y queda
en el log del gateway (nunca se propaga el error al cliente).
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings

log = logging.getLogger("proxy.auditoria")

TOPE_COLA = 5000          # por si Auditoría se cae: no crecemos sin límite
TOPE_LOTE = 50
ESPERA = 1.0              # segundos que junta antes de mandar

_cola: asyncio.Queue | None = None
_worker: asyncio.Task | None = None


def habilitada() -> bool:
    return bool(settings.auditoria_habilitada and settings.auditoria_internal_api_key)


def registrar(evento: dict) -> None:
    """Encola un evento (no bloquea). Si la cola está llena, se descarta y se avisa en el log."""
    if not habilitada() or _cola is None:
        return
    try:
        _cola.put_nowait(evento)
    except asyncio.QueueFull:                       # pragma: no cover - sólo con Auditoría caída
        log.warning("Auditoría: cola llena, se descarta el evento %s %s", evento.get("metodo"), evento.get("ruta"))


async def iniciar() -> None:
    global _cola, _worker
    if not habilitada() or _worker is not None:
        return
    _cola = asyncio.Queue(maxsize=TOPE_COLA)
    _worker = asyncio.create_task(_enviar_siempre())


async def detener() -> None:
    global _worker
    if _worker:
        _worker.cancel()
        _worker = None


async def _juntar_lote() -> list[dict]:
    lote = [await _cola.get()]
    while len(lote) < TOPE_LOTE:
        try:
            lote.append(_cola.get_nowait())
        except asyncio.QueueEmpty:
            break
    return lote


async def _enviar_siempre() -> None:                # pragma: no cover - loop de fondo
    url = f"{settings.auditoria_service_url.rstrip('/')}/internal/auditoria/eventos"
    async with httpx.AsyncClient(timeout=10.0) as cliente:
        while True:
            try:
                lote = await _juntar_lote()
                await asyncio.sleep(ESPERA) if _cola.empty() and len(lote) < TOPE_LOTE else None
                r = await cliente.post(url, json={"eventos": lote},
                                       headers={"X-Api-Key": settings.auditoria_internal_api_key})
                if r.status_code >= 400:
                    log.warning("Auditoría rechazó %s evento(s): %s %s", len(lote), r.status_code, r.text[:200])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Auditoría no recibió %s evento(s): %s", len(lote) if "lote" in dir() else "?", e)
                await asyncio.sleep(5)
