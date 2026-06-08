"""
Servicio del outbox: encolado idempotente de escrituras y drenado.

Fase 3: el drenado corre en DRY-RUN — NO toca las DBF. Registra en el ledger
(interaction_log) qué haría cada operación y deja el outbox en PENDING.
Fase 4 implementará el drenado real (dbf_writer, ventana exclusiva, REINDEX).
"""
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.outbox import LegacyOutbox
from app.services.interaction_logger import log_interaction

# operación -> (database, tabla principal afectada) para el ledger
OPERATION_TARGET = {
    "aplicar_pago": ("caja", "cajapagos"),
    "anular_pago": ("caja", "cajapagos"),
    "consolidar_creditos": ("creditos", "maecuotas"),
}


def enqueue(
    db: Session,
    *,
    operation: str,
    database: str,
    idempotency_key: str,
    payload: dict,
    origin_module: str | None = None,
    origin_user_id: int | None = None,
) -> tuple[LegacyOutbox, bool]:
    """
    Encola una operación de escritura. Idempotente por idempotency_key:
    si ya existe, devuelve la fila existente con created=False.
    """
    existing = (
        db.query(LegacyOutbox)
        .filter(LegacyOutbox.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing, False

    row = LegacyOutbox(
        operation=operation,
        database=database,
        idempotency_key=idempotency_key,
        payload=payload,
        status="PENDING",
        origin_module=origin_module,
        origin_user_id=origin_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def drain_dry_run(db: Session, *, origin_module: str = "legacy") -> dict:
    """
    Recorre el outbox PENDING y registra en el ledger qué aplicaría, SIN tocar
    las DBF. No cambia el estado del outbox (queda PENDING para la Fase 4).
    """
    pending = (
        db.query(LegacyOutbox)
        .filter(LegacyOutbox.status == "PENDING")
        .order_by(LegacyOutbox.created_at)
        .all()
    )

    report = []
    for entry in pending:
        start = time.monotonic()
        database, table = OPERATION_TARGET.get(entry.operation, (entry.database, entry.operation))
        log_interaction(
            db,
            direction="OUT",
            database=database,
            table_name=table,
            operation=entry.operation,
            status="OK",
            rows_affected=0,
            latency_ms=int((time.monotonic() - start) * 1000),
            origin_module=origin_module,
            origin_user_id=entry.origin_user_id,
            outbox_id=entry.id,
            payload_summary={"dry_run": True, "idempotency_key": entry.idempotency_key},
        )
        report.append(
            {
                "outbox_id": entry.id,
                "operation": entry.operation,
                "database": database,
                "table": table,
                "idempotency_key": entry.idempotency_key,
            }
        )

    return {
        "mode": "dry_run",
        "applied": 0,
        "would_apply": len(report),
        "entries": report,
        "note": "DRY-RUN: no se modificó ninguna DBF. El outbox permanece PENDING.",
    }
