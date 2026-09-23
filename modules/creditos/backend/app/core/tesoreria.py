"""Cliente de la API interna de Tesorería: manda los desembolsos como un lote de pagos.

Tesorería es idempotente por (origen, referencia) y no admite dos pagos vivos con la misma referencia
(el id del contrato), así que un reintento o un doble clic nunca genera dos transferencias.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings

TIMEOUT = 30.0


class TesoreriaNoDisponible(RuntimeError):
    """Tesorería no respondió o rechazó el lote entero: el contrato sigue A_LIQUIDAR, sin cambios."""


def enviar_lote(referencia: str, descripcion: str, pagos: list[dict], usuario: str) -> dict:
    """Devuelve {codigo, estado, pagos:[{referencia_externa, estado}], rechazados:[{referencia_externa, motivo}]}."""
    s = get_settings()
    cuerpo = {"origen": "CREDITOS", "referencia_origen": referencia, "descripcion": descripcion,
              "callback_url": s.tesoreria_callback_url, "usuario": usuario, "pagos": pagos}
    try:
        r = httpx.post(f"{s.tesoreria_service_url.rstrip('/')}/internal/tesoreria/lotes", json=cuerpo,
                       headers={"X-Api-Key": s.tesoreria_internal_api_key}, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise TesoreriaNoDisponible(f"Tesorería no responde: {e}") from e
    if r.status_code == 422:
        # Ningún pago válido: Tesorería dice por qué cada uno (CBU inválido, ya está en otro lote…).
        detalle = r.json().get("detail")
        if isinstance(detalle, dict) and "rechazados" in detalle:
            return {"codigo": None, "estado": None, "pagos": [], "rechazados": detalle["rechazados"]}
    if r.status_code >= 400:
        raise TesoreriaNoDisponible(f"Tesorería rechazó el lote ({r.status_code}): {r.text[:200]}")
    return r.json()
