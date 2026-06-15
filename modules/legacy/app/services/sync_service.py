"""
Sincronización legacy -> mirror Postgres.

Por cada tabla: lee la DBF (read-only), coacciona tipos según sync_spec, hace
upsert por clave natural detectando cambios con hash de fila, actualiza
sync_state y registra una interacción IN en el ledger. Resiliente: si la DBF no
existe o falla, marca ERROR sin romper (para no tumbar el scheduler).

Cada sync de una tabla es una transacción: si algo falla, rollback (nunca mirror
parcial).
"""
import hashlib
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.legacy_catalog import database_of
from app.models.sync_state import LegacySyncState
from app.services import dbf_reader
from app.services.dbf_reader import DbfNotFound
from app.services.interaction_logger import log_interaction
from app.sync_spec import SPECS, TableSpec


def _row_hash(values: dict) -> str:
    parts = [f"{k}={values[k]!r}" for k in sorted(values)]
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _build_values(spec: TableSpec, raw: dict) -> dict:
    out = {}
    for attr, dbf_field, coerce in spec.fields:
        out[attr] = coerce(dbf_reader.get_field_ci(raw, dbf_field))
    return out


def _get_or_create_state(db: Session, table_name: str) -> LegacySyncState:
    state = db.query(LegacySyncState).filter(LegacySyncState.table_name == table_name).first()
    if not state:
        state = LegacySyncState(table_name=table_name, database=database_of(table_name) or "desconocida")
        db.add(state)
        db.flush()
    return state


def sync_table(db: Session, table_name: str, *, origin_module: str = "legacy-scheduler") -> dict:
    """Sincroniza una tabla legacy hacia su mirror. Devuelve un reporte."""
    spec = SPECS.get(table_name)
    if not spec:
        raise ValueError(f"Tabla no sincronizable: {table_name}")

    state = _get_or_create_state(db, table_name)
    db.commit()
    start = time.monotonic()

    try:
        rows = dbf_reader.read_table(table_name)
    except DbfNotFound as e:
        return _finish_error(db, state, table_name, str(e), start, origin_module, operation="sync")
    except Exception as e:  # pragma: no cover - defensivo
        return _finish_error(db, state, table_name, f"Error leyendo DBF: {e}", start, origin_module, operation="sync")

    try:
        Model = spec.model
        seen = 0
        changed = 0
        watermark = None

        for raw in rows:
            seen += 1
            values = _build_values(spec, raw)
            h = _row_hash(values)

            filters = [getattr(Model, k) == values[k] for k in spec.natural_key]
            existing = db.query(Model).filter(*filters).first()

            if existing is None:
                obj = Model(row_hash=h, **values)
                db.add(obj)
                changed += 1
            elif existing.row_hash != h:
                for attr, val in values.items():
                    setattr(existing, attr, val)
                existing.row_hash = h
                changed += 1

            if spec.watermark_field:
                wv = values.get(spec.watermark_field)
                if wv is not None and (watermark is None or str(wv) > str(watermark)):
                    watermark = wv

        state.last_run_at = datetime.now(timezone.utc)
        state.last_status = "OK"
        state.last_error = None
        state.rows_seen = seen
        state.rows_changed = changed
        if watermark is not None:
            state.watermark = str(watermark)
        db.commit()

        latency = int((time.monotonic() - start) * 1000)
        log_interaction(
            db,
            direction="IN",
            table_name=table_name,
            operation="sync",
            status="OK",
            rows_affected=changed,
            latency_ms=latency,
            origin_module=origin_module,
            payload_summary={"rows_seen": seen, "rows_changed": changed},
        )
        return {"table": table_name, "status": "OK", "rows_seen": seen, "rows_changed": changed}

    except Exception as e:
        db.rollback()
        return _finish_error(db, state, table_name, f"Error en sync: {e}", start, origin_module, operation="sync")


def _finish_error(db, state, table_name, message, start, origin_module, *, operation):
    # recargar state por si hubo rollback
    state = _get_or_create_state(db, table_name)
    state.last_run_at = datetime.now(timezone.utc)
    state.last_status = "ERROR"
    state.last_error = message
    db.commit()
    latency = int((time.monotonic() - start) * 1000)
    log_interaction(
        db,
        direction="IN",
        table_name=table_name,
        operation=operation,
        status="ERROR",
        latency_ms=latency,
        error_message=message,
        origin_module=origin_module,
    )
    return {"table": table_name, "status": "ERROR", "error": message}


def sync_all(db: Session, *, origin_module: str = "legacy-scheduler") -> list[dict]:
    """Sincroniza todas las tablas del spec. No corta ante errores individuales."""
    results = []
    for table_name in SPECS:
        results.append(sync_table(db, table_name, origin_module=origin_module))
    return results
