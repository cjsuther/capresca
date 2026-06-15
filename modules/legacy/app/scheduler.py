"""
Scheduler de sincronización legacy -> mirror (APScheduler, in-process).

Agrupa tablas por volatilidad con cadencias configurables. Cada corrida abre su
propia sesión, respeta el kill switch (INTEGRATION_ENABLED) y la disponibilidad
del share (si el SMB no está montado, no hace nada y no rompe).
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db.session import SessionLocal
from app.services import smb_health, sync_service

logger = logging.getLogger("legacy.scheduler")

# grupos de tablas por cadencia
GROUPS = {
    "caja": ["cajaliq", "cajapagos", "cajaforpag", "cajacreseg"],
    "creditos": ["maeclientes", "solicitud", "maecuotas", "lineacred"],
    "maestros": ["maeagencias", "maejuegos", "maestrodio", "organismos"],
}

_scheduler: BackgroundScheduler | None = None


def _run_group(group: str):
    if not settings.integration_enabled:
        logger.info("sync %s omitido: integración apagada", group)
        return
    if not smb_health.is_available():
        logger.warning("sync %s omitido: share SMB no disponible", group)
        return
    db = SessionLocal()
    try:
        for table in GROUPS[group]:
            try:
                sync_service.sync_table(db, table, origin_module="legacy-scheduler")
            except Exception:  # pragma: no cover - defensivo
                logger.exception("error sincronizando %s", table)
    finally:
        db.close()


def start():
    global _scheduler
    if not settings.sync_enabled:
        logger.info("scheduler de sync desactivado (SYNC_ENABLED=false)")
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    intervals = {
        "caja": settings.sync_caja_minutes,
        "creditos": settings.sync_creditos_minutes,
        "maestros": settings.sync_maestros_minutes,
    }
    for group, minutes in intervals.items():
        if minutes and minutes > 0:
            _scheduler.add_job(
                _run_group, "interval", minutes=minutes, args=[group],
                id=f"sync_{group}", max_instances=1, coalesce=True,
            )
            logger.info("job sync_%s cada %s min", group, minutes)
    _scheduler.start()


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
