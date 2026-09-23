"""Módulo Auditoría: registro central de lo que hace cada usuario con la información del sistema."""
import logging

from fastapi import FastAPI

from app.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.routers import eventos, internal
from app.services import registro

log = logging.getLogger("auditoria")

app = FastAPI(title="Auditoría", version="1.0.0")
app.include_router(eventos.router, prefix="/api")
app.include_router(internal.router)


@app.on_event("startup")
def arranque() -> None:
    Base.metadata.create_all(bind=engine)     # en tests (SQLite) crea el esquema; en prod ya está por alembic
    if settings.purga_habilitada:
        _purgar()
        _programar_purga()


def _purgar() -> None:
    db = SessionLocal()
    try:
        n = registro.purgar(db)
        if n:
            log.info("Auditoría: se purgaron %s eventos con más de %s días.", n, settings.retencion_dias)
    except Exception:                          # pragma: no cover - la purga nunca voltea el servicio
        log.exception("Auditoría: falló la purga por retención")
    finally:
        db.close()


def _programar_purga() -> None:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:                        # pragma: no cover - en tests no hace falta el scheduler
        return
    sched = BackgroundScheduler(timezone=settings.scheduler_timezone)
    sched.add_job(_purgar, "cron", hour=3, minute=30, id="purga_auditoria", max_instances=1, coalesce=True)
    sched.start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "auditoria"}
