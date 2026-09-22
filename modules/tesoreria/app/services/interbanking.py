"""Envío de transferencias y consulta de su estado en el módulo Interbanking (API interna).

`EnvioIncierto` distingue el caso peligroso: la llamada se cortó (timeout, conexión caída) y no sabemos
si el banco ejecutó la transferencia. Ese pago NO se reintenta automáticamente.
"""
from __future__ import annotations

import httpx

from app.config import settings

TIMEOUT = 30.0

# Estados de Interbanking → estado del pago en Tesorería.
CONFIRMADOS = {"ACREDITADA", "ACREDITADO", "EJECUTADA", "EJECUTADO", "CONFIRMADA", "PROCESADA", "FINALIZADA"}
FALLIDOS = {"RECHAZADA", "RECHAZADO", "ERROR", "ANULADA", "CANCELADA", "FALLIDA", "DEVUELTA"}


class EnvioRechazado(Exception):
    """Interbanking respondió que no pudo hacer la transferencia (definitivo: se puede reintentar)."""


class EnvioIncierto(Exception):
    """No hubo respuesta: la transferencia pudo haber salido o no."""


def _url(path: str) -> str:
    return f"{settings.interbanking_service_url.rstrip('/')}{path}"


def cuentas() -> dict:
    """Cuentas desde las que se puede pagar, para elegir el origen del lote."""
    try:
        r = httpx.get(_url("/internal/interbanking/payment-accounts"), timeout=TIMEOUT)
        r.raise_for_status()
    except httpx.HTTPError as e:
        return {"items": [], "error": f"No se pudo consultar Interbanking: {e}"[:200]}
    return r.json()


def enviar(cbu: str, monto: float, concepto: str, cuenta: dict | None = None) -> dict:
    """Crea la transferencia desde `cuenta` (o la configurada). Devuelve {id, status, id_operacion_ib}."""
    cuerpo = {"cbu_destino": cbu, "monto": monto, "moneda": "ARS", "concepto": concepto}
    if cuenta and cuenta.get("account_number"):
        cuerpo |= {"cuenta_origen": cuenta["account_number"], "cuenta_origen_tipo": cuenta.get("account_type") or "CC",
                   "cuenta_origen_banco": cuenta.get("bank_number") or "011"}
    try:
        r = httpx.post(_url("/internal/interbanking/payments"), json=cuerpo, timeout=TIMEOUT)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
        raise EnvioIncierto(f"Sin respuesta de Interbanking: {e}") from e
    if r.status_code >= 500:
        # Un 5xx puede ocurrir después de haber enviado la orden al banco: no se asume que falló.
        raise EnvioIncierto(f"Interbanking respondió {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        detalle = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise EnvioRechazado(str(detalle)[:280])
    return r.json()


def estado(transfer_id: int) -> str:
    """Estado actual de la transferencia en Interbanking (texto del banco)."""
    r = httpx.get(_url(f"/internal/interbanking/payments/{transfer_id}"), timeout=TIMEOUT)
    r.raise_for_status()
    return str(r.json().get("status") or "").upper()


def clasificar(estado_banco: str) -> str:
    """ENVIADO (todavía en curso) | CONFIRMADO | FALLIDO."""
    e = (estado_banco or "").upper()
    if e in CONFIRMADOS:
        return "CONFIRMADO"
    if e in FALLIDOS:
        return "FALLIDO"
    return "ENVIADO"
