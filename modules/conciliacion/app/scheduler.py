"""
Scheduler de conciliación (APScheduler, in-process).

Cada `auto_match_interval_minutes` corre el cruce automático de transferencias para
el día de hoy (y `auto_match_lookback_days` días hacia atrás, para tomar
transferencias tardías). El cruce:
  - trae los depósitos de la cuenta configurada en Interbanking,
  - los asigna por CUIT/CBU a cada agencia,
  - recalcula el saldo y auto-consolida las que quedan en cero.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db.session import SessionLocal
from app.services import matching_service, payments_service

logger = logging.getLogger("conciliacion.scheduler")

_scheduler: BackgroundScheduler | None = None


def _run_auto_match() -> None:
    db = SessionLocal()
    try:
        hoy = datetime.now().date()
        for delta in range(0, settings.auto_match_lookback_days + 1):
            fecha = hoy - timedelta(days=delta)
            try:
                asyncio.run(matching_service.load_date(db, fecha))
                logger.info("Cruce automático OK para %s", fecha)
            except Exception:
                logger.exception("Cruce automático falló para %s", fecha)
            # Pagos salientes a agencias con saldo a favor (respeta kill-switch + dry-run)
            try:
                asyncio.run(payments_service.run_payments(db, fecha))
            except Exception:
                logger.exception("Motor de pagos falló para %s", fecha)
    finally:
        db.close()


def start() -> None:
    global _scheduler
    if not settings.auto_match_enabled:
        logger.info("Cruce automático deshabilitado (AUTO_MATCH_ENABLED=false)")
        return
    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(
        _run_auto_match,
        "interval",
        minutes=settings.auto_match_interval_minutes,
        id="auto_match",
        next_run_time=datetime.now(),  # corre una vez al arrancar
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler conciliación iniciado (cada %s min)", settings.auto_match_interval_minutes)


def stop() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
