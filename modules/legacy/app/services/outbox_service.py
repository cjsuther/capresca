"""
Servicio del outbox: encolado idempotente de escrituras y drenado.

Dry-run: NO toca las DBF; registra en el ledger qué haría y deja el outbox en
PENDING. Real (Fase 4, sandbox): aplica vía dbf_writer SOLO contra la copia
sandbox y marca APPLIED/SKIPPED/FAILED.
"""
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.outbox import LegacyOutbox
from app.services.interaction_logger import log_interaction
from app.services import dbf_writer

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


def drain_real(db: Session, *, origin_module: str = "legacy-admin") -> dict:
    """
    Drenado REAL (modo sandbox): aplica cada operación PENDING vía dbf_writer
    SOLO contra la copia sandbox. Marca APPLIED/SKIPPED/FAILED y loguea OUT.
    """
    pending = (
        db.query(LegacyOutbox)
        .filter(LegacyOutbox.status == "PENDING")
        .order_by(LegacyOutbox.created_at)
        .all()
    )

    applied = skipped = failed = 0
    report = []

    for entry in pending:
        database, table = OPERATION_TARGET.get(entry.operation, (entry.database, entry.operation))
        handler = dbf_writer.HANDLERS.get(entry.operation)
        start = time.monotonic()

        if handler is None:
            entry.status = "FAILED"
            entry.attempts += 1
            entry.last_error = f"Sin handler de escritura para '{entry.operation}'"
            db.commit()
            failed += 1
            log_interaction(
                db, direction="OUT", database=database, table_name=table, operation=entry.operation,
                status="ERROR", latency_ms=int((time.monotonic() - start) * 1000),
                error_message=entry.last_error, origin_module=origin_module,
                origin_user_id=entry.origin_user_id, outbox_id=entry.id,
            )
            report.append({"outbox_id": entry.id, "operation": entry.operation, "status": "FAILED"})
            continue

        entry.status = "DRAINING"
        entry.attempts += 1
        db.commit()

        try:
            result = handler(entry.payload)
            now = datetime.now(timezone.utc)
            if result.get("status") == "SKIPPED":
                entry.status = "SKIPPED"
                entry.applied_at = now
                entry.last_error = None
                db.commit()
                skipped += 1
                rows = 0
                ostatus = "SKIPPED"
            else:
                entry.status = "APPLIED"
                entry.applied_at = now
                entry.last_error = None
                db.commit()
                applied += 1
                rows = sum((result.get("rows") or {}).values())
                ostatus = "OK"
            log_interaction(
                db, direction="OUT", database=database, table_name=table, operation=entry.operation,
                status=ostatus, rows_affected=rows, latency_ms=int((time.monotonic() - start) * 1000),
                origin_module=origin_module, origin_user_id=entry.origin_user_id, outbox_id=entry.id,
                payload_summary={"sandbox": True, **result},
            )
            report.append({"outbox_id": entry.id, "operation": entry.operation, "status": entry.status, "result": result})
        except Exception as e:
            db.rollback()
            entry = db.query(LegacyOutbox).filter(LegacyOutbox.id == entry.id).first()
            entry.status = "FAILED"
            entry.last_error = str(e)
            db.commit()
            failed += 1
            log_interaction(
                db, direction="OUT", database=database, table_name=table, operation=entry.operation,
                status="ERROR", latency_ms=int((time.monotonic() - start) * 1000),
                error_message=str(e), origin_module=origin_module,
                origin_user_id=entry.origin_user_id, outbox_id=entry.id,
            )
            report.append({"outbox_id": entry.id, "operation": entry.operation, "status": "FAILED", "error": str(e)})

    return {"mode": "real_sandbox", "applied": applied, "skipped": skipped, "failed": failed, "entries": report}
