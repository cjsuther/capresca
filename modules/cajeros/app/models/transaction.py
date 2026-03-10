from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(BigInteger, primary_key=True, index=True)
    cajero_user_id = Column(Integer, nullable=False, index=True)
    cajero_username = Column(String(100), nullable=True)
    authorizer_user_id = Column(Integer, nullable=True, index=True)
    authorizer_username = Column(String(100), nullable=True)
    currency = Column(String(10), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    reference = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="PROCESADA")
    rejection_reason = Column(Text, nullable=True)
    authorized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=False)

    triggers = relationship("TransactionRuleTrigger", back_populates="transaction")


class TransactionRuleTrigger(Base):
    __tablename__ = "transaction_rule_triggers"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(BigInteger, ForeignKey("transactions.id"), nullable=False, index=True)
    rule_id = Column(Integer, nullable=False)
    authorizer_user_id = Column(Integer, nullable=False)

    transaction = relationship("Transaction", back_populates="triggers")
