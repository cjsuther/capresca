from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, func
from app.db.base import Base


class LegacySyncState(Base):
    """Estado de sincronización legacy -> mirror Postgres, una fila por tabla."""

    __tablename__ = "legacy_sync_state"

    id = Column(BigInteger, primary_key=True)
    table_name = Column(String(50), nullable=False, unique=True, index=True)
    database = Column(String(20), nullable=False)

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(10), nullable=True)  # OK|ERROR|RUNNING
    last_error = Column(Text, nullable=True)

    rows_seen = Column(Integer, nullable=True)
    rows_changed = Column(Integer, nullable=True)

    # Marca de agua para escaneo incremental en tablas append-only (ej. último no_recibo/fecha)
    watermark = Column(String(100), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
