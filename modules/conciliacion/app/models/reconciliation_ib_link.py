from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReconciliationIbLink(Base):
    __tablename__ = "reconciliation_ib_links"

    id = Column(BigInteger, primary_key=True, index=True)
    reconciliation_record_id = Column(BigInteger, ForeignKey("reconciliation_records.id"), nullable=False, index=True)
    ib_transaction_type = Column(String(20), nullable=False)
    ib_transaction_id = Column(BigInteger, nullable=False)
    ib_amount = Column(Numeric(15, 2), nullable=False)
    ib_cbu = Column(String(22), nullable=False)
    ib_concepto = Column(String(255), nullable=True)
    match_type = Column(String(20), nullable=False)
    linked_by_user_id = Column(Integer, nullable=False, default=0)
    linked_at = Column(DateTime(timezone=True), server_default=func.now())
    unlinked_at = Column(DateTime(timezone=True), nullable=True)
    unlinked_by_user_id = Column(Integer, nullable=True)

    record = relationship("ReconciliationRecord",
                          foreign_keys=[reconciliation_record_id],
                          back_populates=None)
