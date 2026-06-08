"""
Router de administración / diagnóstico (expuesto por el proxy en /api/legacy).
Alimenta el frontend del módulo: registro de interacciones y panel de estado.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.config import settings
from app.legacy_catalog import DATABASES
from app.models.interaction_log import LegacyInteractionLog
from app.models.sync_state import LegacySyncState
from app.models.outbox import LegacyOutbox
from app.schemas.legacy import (
    InteractionPage,
    InteractionOut,
    StatusOut,
    SyncStateOut,
    OutboxPage,
    OutboxOut,
)
from app.services import smb_health, outbox_service

router = APIRouter()


@router.get("/interactions", response_model=InteractionPage)
def list_interactions(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    database: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    table: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Ledger de interacciones IN/OUT, filtrable por fecha y base de datos (entre otros)."""
    if database and database not in DATABASES:
        raise HTTPException(status_code=400, detail=f"Base de datos inválida: {database}")
    if direction and direction not in ("IN", "OUT"):
        raise HTTPException(status_code=400, detail="direction debe ser IN u OUT")

    q = db.query(LegacyInteractionLog)
    if date_from:
        q = q.filter(LegacyInteractionLog.occurred_date >= date_from)
    if date_to:
        q = q.filter(LegacyInteractionLog.occurred_date <= date_to)
    if database:
        q = q.filter(LegacyInteractionLog.database == database)
    if direction:
        q = q.filter(LegacyInteractionLog.direction == direction)
    if table:
        q = q.filter(LegacyInteractionLog.table_name == table)
    if status:
        q = q.filter(LegacyInteractionLog.status == status)

    total = q.count()
    items = (
        q.order_by(LegacyInteractionLog.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return InteractionPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[InteractionOut.model_validate(i) for i in items],
    )


@router.get("/interactions/{interaction_id}", response_model=InteractionOut)
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    entry = db.query(LegacyInteractionLog).filter(LegacyInteractionLog.id == interaction_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Interacción no encontrada")
    return InteractionOut.model_validate(entry)


@router.get("/status", response_model=StatusOut)
def get_status(db: Session = Depends(get_db)):
    """Panel operativo: kill switch, salud SMB, estado de sync por tabla, outbox pendiente."""
    sync_rows = db.query(LegacySyncState).order_by(LegacySyncState.table_name).all()
    outbox_pending = (
        db.query(func.count(LegacyOutbox.id))
        .filter(LegacyOutbox.status.in_(["PENDING", "DRAINING"]))
        .scalar()
    )
    return StatusOut(
        integration_enabled=settings.integration_enabled,
        write_mode=settings.write_mode,
        smb=smb_health.check_mount(),
        sync_state=[SyncStateOut.model_validate(r) for r in sync_rows],
        outbox_pending=int(outbox_pending or 0),
    )


@router.get("/databases")
def list_databases():
    """Lista de bases de datos lógicas del legacy (para poblar el filtro del frontend)."""
    return {"databases": list(DATABASES)}


@router.get("/outbox", response_model=OutboxPage)
def list_outbox(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Cola de escrituras pendientes/aplicadas hacia el legacy."""
    q = db.query(LegacyOutbox)
    if status:
        q = q.filter(LegacyOutbox.status == status)
    total = q.count()
    items = (
        q.order_by(LegacyOutbox.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return OutboxPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[OutboxOut.model_validate(i) for i in items],
    )


@router.post("/outbox/drain")
def drain_outbox(db: Session = Depends(get_db)):
    """
    Drena el outbox. En la Fase 3 corre en DRY-RUN: registra en el ledger qué
    aplicaría cada operación SIN tocar las DBF y deja el outbox en PENDING.
    El drenado real (escritura en DBF + REINDEX) se habilita en la Fase 4.
    """
    if settings.write_mode != "outbox_only":
        raise HTTPException(status_code=409, detail=f"write_mode no soportado: {settings.write_mode}")
    return outbox_service.drain_dry_run(db)


@router.post("/sync/{tabla}")
def trigger_sync(tabla: str):
    """Fuerza la sincronización de una tabla legacy hacia el mirror. (Se implementa en la Fase 1.)"""
    raise HTTPException(
        status_code=501,
        detail="La sincronización on-demand se implementa en la Fase 1 (lectura/mirror).",
    )
