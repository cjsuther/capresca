from decimal import Decimal
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id = Column(BigInteger, primary_key=True, index=True)
    reconciliation_date = Column(Date, nullable=False)
    client_id = Column(Integer, nullable=False, index=True)
    agency_number = Column(String(20), nullable=True)
    agency_legal_name = Column(String(255), nullable=False)
    agency_tax_id = Column(String(30), nullable=True)
    importe_adeudado = Column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    importe_premios = Column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    importe_depositado = Column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    status = Column(String(30), nullable=False, default="A_VERIFICAR")
    modified_by_user_id = Column(Integer, nullable=True)
    modified_by_username = Column(String(100), nullable=True)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    links = relationship("ReconciliationIbLink", back_populates="record",
                         primaryjoin="and_(ReconciliationIbLink.reconciliation_record_id==ReconciliationRecord.id, ReconciliationIbLink.unlinked_at==None)",
                         foreign_keys="ReconciliationIbLink.reconciliation_record_id",
                         viewonly=True)
    history = relationship("ReconciliationStatusHistory", back_populates="record",
                           order_by="ReconciliationStatusHistory.changed_at.desc()")

    @property
    def importe_neto(self):
        return (self.importe_adeudado or Decimal("0")) - (self.importe_premios or Decimal("0")) - (self.importe_depositado or Decimal("0"))
