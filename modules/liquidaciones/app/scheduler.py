"""
Scheduler de ingesta de liquidaciones (APScheduler, in-process).

Cada mañana (cron `inbox_cron_hour:inbox_cron_minute`) escanea `inbox_dir` en busca
de ZIPs de liquidación nuevos, los procesa (arma el estado de cada agencia y los
envía a Conciliación) y los mueve a `processed/` (o `error/` si el lote falla), para
que nunca se reprocesen. También escanea una vez al arrancar si `inbox_scan_on_startup`.
"""
import logging
import os
import shutil

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db.session import SessionLocal
from app.services.processing import process_from_path

logger = logging.getLogger("liquidaciones.scheduler")

_scheduler: BackgroundScheduler | None = None


def _dirs():
    base = settings.inbox_dir
    processed = os.path.join(base, "processed")
    error = os.path.join(base, "error")
    os.makedirs(base, exist_ok=True)
    os.makedirs(processed, exist_ok=True)
    os.makedirs(error, exist_ok=True)
    return base, processed, error


def scan_inbox() -> None:
    base, processed, error = _dirs()
    try:
        entries = sorted(f for f in os.listdir(base) if f.lower().endswith(".zip"))
    except FileNotFoundError:
        return
    if not entries:
        logger.info("Inbox vacío (%s)", base)
        return
    for name in entries:
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            continue
        db = SessionLocal()
        try:
            batch = process_from_path(db, path, settings.inbox_default_user_id)
            dest = error if getattr(batch, "status", "ERROR") == "ERROR" else processed
            shutil.move(path, os.path.join(dest, name))
            logger.info("Procesado %s -> batch %s (%s)", name, getattr(batch, "id", "?"), getattr(batch, "status", "?"))
        except Exception:
            logger.exception("Falló el procesamiento de %s; se mueve a error/", name)
            try:
                shutil.move(path, os.path.join(error, name))
            except Exception:
                logger.exception("No se pudo mover %s a error/", name)
        finally:
            db.close()


def start() -> None:
    global _scheduler
    if not settings.inbox_enabled:
        logger.info("Ingesta automática deshabilitada (INBOX_ENABLED=false)")
        return
    _dirs()
    if settings.inbox_scan_on_startup:
        try:
            scan_inbox()
        except Exception:
            logger.exception("Fallo el escaneo de inbox al arrancar")
    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(
        scan_inbox,
        "cron",
        hour=settings.inbox_cron_hour,
        minute=settings.inbox_cron_minute,
        id="inbox_scan",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler liquidaciones iniciado (cron %02d:%02d, dir=%s)",
                settings.inbox_cron_hour, settings.inbox_cron_minute, settings.inbox_dir)


def stop() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
