from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from app.db.base import Base


class ReconciliationPayment(Base):
    """Pago saliente a una agencia con saldo a favor. Uno por registro de
    conciliación (idempotencia): garantiza que nunca se pague dos veces la misma
    agencia/fecha. status: DRY_RUN | ENVIADO | ERROR | SIN_CBU | EN_TESORERIA (esperando que
    Tesorería lo apruebe y lo envíe; al acreditarse pasa a ENVIADO) | OBSERVADO (Tesorería no lo pagó:
    excluido, rechazado o fallido; no se reenvía automáticamente).
    """
    __tablename__ = "reconciliation_payments"

    id = Column(BigInteger, primary_key=True, index=True)
    reconciliation_record_id = Column(
        BigInteger, ForeignKey("reconciliation_records.id"), nullable=False, unique=True, index=True
    )
    client_id = Column(Integer, nullable=True)
    agency_number = Column(String(20), nullable=True)
    cbu_destino = Column(String(22), nullable=True)
    amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), nullable=False, default="DRY_RUN")
    ib_transfer_id = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    tesoreria_lote = Column(String(20), nullable=True)
    created_by_user_id = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
