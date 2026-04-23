from sqlalchemy import Column, BigInteger, String, Numeric, Boolean, Text, DateTime, ForeignKey, func
from app.db.base import Base


class LiquidacionValidacion(Base):
    __tablename__ = "liquidacion_validaciones"

    id = Column(BigInteger, primary_key=True)
    batch_id = Column(BigInteger, ForeignKey("liquidacion_batches.id"), nullable=False, index=True)
    validation_type = Column(String(50), nullable=False)
    agency_number = Column(String(6), nullable=True)
    expected_value = Column(Numeric(15, 2), nullable=True)
    actual_value = Column(Numeric(15, 2), nullable=True)
    passed = Column(Boolean, nullable=False)
    detail_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
