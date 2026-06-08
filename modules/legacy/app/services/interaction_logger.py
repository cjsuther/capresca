"""
Helper para registrar interacciones (IN/OUT) con el legacy en el ledger.

Cada lectura (sync u on-demand) y cada escritura (outbox/drainer) llama a
`log_interaction` para dejar trazabilidad consultable desde el frontend.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.interaction_log import LegacyInteractionLog
from app.legacy_catalog import database_of


def log_interaction(
    db: Session,
    *,
    direction: str,            # 'IN' | 'OUT'
    table_name: str,
    operation: str,            # read|sync|insert|replace|anular|...
    status: str = "OK",        # OK|ERROR|SKIPPED
    rows_affected: int | None = None,
    latency_ms: int | None = None,
    error_message: str | None = None,
    origin_module: str | None = None,
    origin_user_id: int | None = None,
    outbox_id: int | None = None,
    payload_summary: dict | None = None,
    database: str | None = None,
    commit: bool = True,
) -> LegacyInteractionLog:
    """Inserta una fila en legacy_interaction_log. database se infiere del catálogo si no se pasa."""
    now = datetime.now(timezone.utc)
    entry = LegacyInteractionLog(
        direction=direction,
        database=database or database_of(table_name) or "desconocida",
        table_name=table_name,
        operation=operation,
        occurred_at=now,
        occurred_date=now.date(),
        rows_affected=rows_affected,
        status=status,
        latency_ms=latency_ms,
        error_message=error_message,
        origin_module=origin_module,
        origin_user_id=origin_user_id,
        outbox_id=outbox_id,
        payload_summary=payload_summary,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry
