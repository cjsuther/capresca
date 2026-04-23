from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Date, DateTime, ForeignKey, func
from app.db.base import Base


class LiquidacionConciliacionRecord(Base):
    __tablename__ = "liquidacion_conciliacion_records"

    id = Column(BigInteger, primary_key=True)
    liquidacion_batch_id = Column(Integer, nullable=False)
    agency_number = Column(String(6), nullable=False)
    operation_date = Column(Date, nullable=True)
    importe_adeudado = Column(Numeric(15, 2), nullable=False)
    importe_premios = Column(Numeric(15, 2), nullable=False)
    recaudacion_total = Column(Numeric(15, 2), nullable=False)
    comision_total = Column(Numeric(15, 2), nullable=False)
    resumen_number = Column(String(20), nullable=True)
    moneda = Column(String(5), nullable=True)
    reconciliation_record_id = Column(BigInteger, ForeignKey("reconciliation_records.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
