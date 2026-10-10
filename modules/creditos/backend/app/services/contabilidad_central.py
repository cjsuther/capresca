"""Envío de TRANSACCIONES a Contabilidad, con outbox.

Este módulo no arma asientos ni conoce el plan de cuentas: manda lo que pasó (el evento y sus
importes) y Contabilidad decide cómo se registra, según la definición de ese tipo de transacción. Si
todavía no hay definición, la transacción queda allá pendiente de configuración: nada se pierde.

La transacción se guarda en `outbox_contable` dentro de la misma transacción de base que la
operación: si la operación se deshace, la transacción no sale; si Contabilidad está caída o el
servicio se reinicia, queda pendiente y un hilo la reenvía (con espera creciente) hasta que llega.
No frena ni voltea la operación del usuario.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app import models

log = logging.getLogger("contabilidad")

MODULO = "creditos"
BASE = os.getenv("CONTABILIDAD_SERVICE_URL", "http://contabilidad:8014").rstrip("/") + "/internal/contabilidad/transacciones"
CLAVE = os.getenv("CONTABILIDAD_INTERNAL_API_KEY", "")
INTERVALO = 5                 # segundos entre vueltas del hilo
ESPERA_MAXIMA = 3600          # tope de la espera entre reintentos de una misma transacción

_hilo: threading.Thread | None = None
_lock = threading.Lock()


def habilitada() -> bool:
    return bool(CLAVE)


def _fecha(f) -> str:
    return f.isoformat() if hasattr(f, "isoformat") else str(f)


def registrar(db: Session, *, tipo: str, referencia: str, fecha: date, datos: dict, descripcion: str = "",
              usuario: str = "", moneda: str = "ARS", asiento_id: int | None = None) -> None:
    """Deja la transacción en el outbox (sale cuando se confirme la operación)."""
    if not habilitada():
        return
    referencia = str(referencia)[:80]
    db.add(models.OutboxContable(
        accion="REGISTRAR", tipo=tipo, referencia=referencia, asiento_id=asiento_id,
        payload={"modulo": MODULO, "tipo": tipo, "referencia": referencia, "fecha": _fecha(fecha),
                 "moneda": moneda, "descripcion": descripcion[:200], "usuario": usuario,
                 "datos": {k: v for k, v in (datos or {}).items() if v is not None}}))
    _asegurar_hilo()


def anular(db: Session, *, tipo: str, referencia: str, fecha: date, motivo: str = "", usuario: str = "") -> None:
    """El evento se revirtió acá: Contabilidad anula su transacción (contra-asiento si ya estaba asentada)."""
    if not habilitada():
        return
    db.add(models.OutboxContable(
        accion="ANULAR", tipo=tipo, referencia=referencia,
        payload={"modulo": MODULO, "tipo": tipo, "referencia": referencia, "fecha": _fecha(fecha),
                 "motivo": motivo[:300], "usuario": usuario}))
    _asegurar_hilo()


def anular_de_asiento(db: Session, asiento_id: int, *, fecha: date, motivo: str = "", usuario: str = "") -> int:
    """Anula en Contabilidad las transacciones que salieron con ese asiento local. Devuelve cuántas."""
    filas = db.query(models.OutboxContable).filter_by(accion="REGISTRAR", asiento_id=asiento_id).all()
    for f in filas:
        anular(db, tipo=f.tipo, referencia=f.referencia, fecha=fecha, motivo=motivo, usuario=usuario)
    return len(filas)


def enviar_pendientes(db: Session, ahora: datetime | None = None, cliente=httpx) -> int:
    """Manda las pendientes que ya tocan, en orden de alta. Devuelve cuántas llegaron."""
    ahora = ahora or models._utc_ahora()
    filas = (db.query(models.OutboxContable)
             .filter(models.OutboxContable.estado == "PENDIENTE", models.OutboxContable.proximo_intento <= ahora)
             .order_by(models.OutboxContable.id).limit(100)
             .with_for_update(skip_locked=True).all())
    enviadas = 0
    for f in filas:
        url = BASE + ("/anular" if f.accion == "ANULAR" else "")
        try:
            r = cliente.post(url, json=f.payload, headers={"X-Api-Key": CLAVE}, timeout=15.0)
            error = "" if r.status_code < 400 else f"{r.status_code} {r.text[:250]}"
        except Exception as e:                                   # Contabilidad caída o sin red
            error = str(e)[:300]
        if error:
            f.intentos += 1
            f.ultimo_error = error[:300]
            f.proximo_intento = ahora + timedelta(seconds=min(ESPERA_MAXIMA, 10 * 2 ** min(f.intentos, 9)))
            log.warning("Contabilidad no recibió %s %s %s (intento %s): %s",
                        f.accion, f.tipo, f.referencia, f.intentos, error)
        else:
            f.estado, f.enviado_en, f.ultimo_error = "ENVIADA", ahora, ""
            enviadas += 1
    db.commit()
    return enviadas


def iniciar() -> None:
    """Arranca el hilo al levantar el servicio: así sale lo que quedó pendiente antes de un reinicio."""
    if habilitada():
        _asegurar_hilo()


def _asegurar_hilo() -> None:
    global _hilo
    with _lock:
        if _hilo is None or not _hilo.is_alive():
            _hilo = threading.Thread(target=_enviar_siempre, name="contabilidad", daemon=True)
            _hilo.start()


def _enviar_siempre() -> None:                           # pragma: no cover - hilo de fondo
    from app.core.database import SessionLocal
    while True:
        try:
            with SessionLocal() as db:
                enviar_pendientes(db)
        except Exception as e:
            log.warning("Contabilidad: falló la vuelta del outbox: %s", e)
        time.sleep(INTERVALO)
