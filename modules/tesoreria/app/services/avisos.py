"""Aviso del resultado de cada pago al módulo que originó el lote (callback con la clave interna).

Se avisa cada vez que un pago llega a un estado final que el origen necesita conocer: CONFIRMADO,
FALLIDO o EXCLUIDO (y RECHAZADO si se rechaza el lote entero). `Pago.notificado` guarda el último
estado avisado: si el origen no responde, se vuelve a intentar en la próxima actualización.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app import models
from app.config import settings

log = logging.getLogger("tesoreria.avisos")
A_AVISAR = {"CONFIRMADO", "FALLIDO", "EXCLUIDO", "RECHAZADO"}


def avisar(db: Session, lote: models.Lote) -> int:
    if not lote.callback_url:
        return 0
    pendientes = [p for p in lote.pagos if p.estado in A_AVISAR and p.notificado != p.estado]
    if not pendientes:
        return 0
    cuerpo = {"lote": lote.codigo, "origen": lote.origen, "referencia_origen": lote.referencia_origen,
              "simulado": lote.simulado,
              "pagos": [{"referencia_externa": p.referencia_externa, "estado": p.estado, "motivo": p.motivo,
                         "id_operacion_ib": p.id_operacion_ib, "monto": float(p.monto)} for p in pendientes]}
    try:
        r = httpx.post(lote.callback_url, json=cuerpo, headers={"X-Api-Key": settings.internal_api_key}, timeout=15.0)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("No se pudo avisar el resultado del lote %s a %s: %s", lote.codigo, lote.callback_url, e)
        return 0
    for p in pendientes:
        p.notificado = p.estado
    db.commit()
    return len(pendientes)
