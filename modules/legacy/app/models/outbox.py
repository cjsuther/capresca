from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class LegacyOutbox(Base):
    """
    Cola de escrituras pendientes hacia el legacy (write-ahead).

    Toda operación de escritura entra acá y devuelve 202 al origen. El drainer la
    aplica en ventana de mantenimiento (nunca en caliente). Idempotente vía
    idempotency_key (clave de negocio, ej. no_recibo).
    """

    __tablename__ = "legacy_outbox"

    id = Column(BigInteger, primary_key=True)

    operation = Column(String(40), nullable=False)  # aplicar_pago|anular_pago|consolidar_creditos|...
    database = Column(String(20), nullable=False)
    idempotency_key = Column(String(120), nullable=False, unique=True, index=True)

    payload = Column(JSONB, nullable=False)  # datos normalizados de la operación

    status = Column(String(12), nullable=False, server_default="PENDING", index=True)
    # PENDING | DRAINING | APPLIED | FAILED | SKIPPED
    attempts = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)

    origin_module = Column(String(50), nullable=True)
    origin_user_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)
