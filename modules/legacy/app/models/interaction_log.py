from sqlalchemy import Column, BigInteger, String, Date, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class LegacyInteractionLog(Base):
    """
    Ledger de auditoría de TODA interacción con el legacy.

    direction: 'IN'  = lectura legacy -> sistema nuevo
               'OUT' = escritura sistema nuevo -> legacy
    Es la fuente que alimenta el frontend (consultable por fecha y base de datos).
    """

    __tablename__ = "legacy_interaction_log"

    id = Column(BigInteger, primary_key=True)
    direction = Column(String(3), nullable=False, index=True)  # IN | OUT
    database = Column(String(20), nullable=False, index=True)   # caja|juegos|creditos|general|contabilidad
    table_name = Column(String(50), nullable=False)
    operation = Column(String(20), nullable=False)  # read|sync|insert|replace|anular|...

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    occurred_date = Column(Date, nullable=False, index=True)  # para filtrar por día sin castear timestamp

    rows_affected = Column(Integer, nullable=True)
    status = Column(String(10), nullable=False, server_default="OK")  # OK|ERROR|SKIPPED
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    origin_module = Column(String(50), nullable=True)   # módulo que originó la interacción
    origin_user_id = Column(Integer, nullable=True)
    outbox_id = Column(BigInteger, nullable=True, index=True)  # si la interacción nace de un outbox (OUT)
    payload_summary = Column(JSONB, nullable=True)      # resumen no sensible para diagnóstico
