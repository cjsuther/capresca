from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReconciliationStatusHistory(Base):
    __tablename__ = "reconciliation_status_history"

    id = Column(BigInteger, primary_key=True, index=True)
    reconciliation_record_id = Column(BigInteger, ForeignKey("reconciliation_records.id"), nullable=False, index=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    previous_importe_adeudado = Column(Numeric(15, 2), nullable=True)
    previous_importe_premios = Column(Numeric(15, 2), nullable=True)
    previous_importe_depositado = Column(Numeric(15, 2), nullable=True)
    new_importe_adeudado = Column(Numeric(15, 2), nullable=True)
    new_importe_premios = Column(Numeric(15, 2), nullable=True)
    new_importe_depositado = Column(Numeric(15, 2), nullable=True)
    changed_by_user_id = Column(Integer, nullable=False)
    changed_by_username = Column(String(100), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    record = relationship("ReconciliationRecord", back_populates="history",
                          foreign_keys=[reconciliation_record_id])
