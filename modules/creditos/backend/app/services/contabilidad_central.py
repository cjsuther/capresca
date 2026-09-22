"""Envío de TRANSACCIONES a Contabilidad.

Este módulo no arma asientos ni conoce el plan de cuentas: manda lo que pasó (el evento y sus
importes) y Contabilidad decide cómo se registra, según la definición de ese tipo de transacción. Si
todavía no hay definición, la transacción queda allá pendiente de configuración: nada se pierde.

No frena ni voltea la operación del usuario: se encola y lo manda un hilo aparte.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import date

import httpx

log = logging.getLogger("contabilidad")

MODULO = "creditos"
URL = os.getenv("CONTABILIDAD_SERVICE_URL", "http://contabilidad:8014").rstrip("/") + "/internal/contabilidad/transacciones"
CLAVE = os.getenv("CONTABILIDAD_INTERNAL_API_KEY", "")

_cola: queue.Queue = queue.Queue(maxsize=2000)
_hilo: threading.Thread | None = None
_lock = threading.Lock()


def habilitada() -> bool:
    return bool(CLAVE)


def registrar(*, tipo: str, referencia: str, fecha: date, datos: dict, descripcion: str = "",
              usuario: str = "", moneda: str = "ARS") -> None:
    """Deja la transacción en la cola (no bloquea). Idempotente en Contabilidad por (módulo, tipo, referencia)."""
    if not habilitada():
        return
    _asegurar_hilo()
    try:
        _cola.put_nowait({"modulo": MODULO, "tipo": tipo, "referencia": str(referencia)[:80],
                          "fecha": fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha),
                          "moneda": moneda, "descripcion": descripcion[:200], "usuario": usuario,
                          "datos": {k: v for k, v in (datos or {}).items() if v is not None}})
    except queue.Full:                                   # pragma: no cover - sólo con Contabilidad caída
        log.warning("Contabilidad: cola llena, se descarta %s %s", tipo, referencia)


def _asegurar_hilo() -> None:
    global _hilo
    with _lock:
        if _hilo is None or not _hilo.is_alive():
            _hilo = threading.Thread(target=_enviar_siempre, name="contabilidad", daemon=True)
            _hilo.start()


def _enviar_siempre() -> None:                           # pragma: no cover - hilo de fondo
    while True:
        t = _cola.get()
        try:
            r = httpx.post(URL, json=t, headers={"X-Api-Key": CLAVE}, timeout=15.0)
            if r.status_code >= 400:
                log.warning("Contabilidad rechazó %s %s: %s %s", t["tipo"], t["referencia"],
                            r.status_code, r.text[:200])
        except Exception as e:
            log.warning("Contabilidad no recibió %s %s: %s", t["tipo"], t["referencia"], e)
