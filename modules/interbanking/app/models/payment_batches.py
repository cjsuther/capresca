from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class PaymentBatch(Base):
    __tablename__ = "payment_batches"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    audit_log_id = Column(BigInteger, ForeignKey("api_audit_log.id"), nullable=True)
    descripcion = Column(String(255))
    id_lote_ib = Column(String(100))
    status = Column(String(50), default="BORRADOR")
    total_items = Column(Integer)
    total_amount = Column(Numeric(15, 2))
    created_by = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True))
    last_status_check = Column(DateTime(timezone=True))
    last_status_payload = Column(JSONB)

    items = relationship("PaymentBatchItem", back_populates="batch", cascade="all, delete-orphan")


class PaymentBatchItem(Base):
    __tablename__ = "payment_batch_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(BigInteger, ForeignKey("payment_batches.id"), nullable=False)
    cbu = Column(String(22))
    monto = Column(Numeric(15, 2))
    detalle = Column(String(255))
    status_item = Column(String(50))

    batch = relationship("PaymentBatch", back_populates="items")
