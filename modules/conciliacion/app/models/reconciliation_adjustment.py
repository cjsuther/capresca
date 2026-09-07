from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from app.db.base import Base


class ReconciliationAdjustment(Base):
    """Ajuste manual sobre el saldo de una agencia. `amount` con signo: positivo
    acredita a la agencia (sube el saldo a favor), negativo lo baja. Se suma al
    importe_depositado al recalcular, por lo que sobrevive a las corridas del cruce.
    Registra quién, cuándo y por qué (auditoría exigida por el negocio).
    """
    __tablename__ = "reconciliation_adjustments"

    id = Column(BigInteger, primary_key=True, index=True)
    reconciliation_record_id = Column(
        BigInteger, ForeignKey("reconciliation_records.id"), nullable=False, index=True
    )
    amount = Column(Numeric(15, 2), nullable=False)
    reason = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, nullable=False)
    created_by_username = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
