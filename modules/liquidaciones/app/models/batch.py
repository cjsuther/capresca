from sqlalchemy import Column, BigInteger, String, Date, Integer, Text, DateTime, func
from app.db.base import Base


class LiquidacionBatch(Base):
    __tablename__ = "liquidacion_batches"

    id = Column(BigInteger, primary_key=True)
    zip_filename = Column(String(255), nullable=False)
    operation_date = Column(Date, nullable=True)
    resumen_number = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False, server_default="PENDIENTE")
    total_detail_records = Column(Integer, nullable=True)
    total_summary_records = Column(Integer, nullable=True)
    total_agencies = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    sent_to_conciliacion_at = Column(DateTime(timezone=True), nullable=True)
