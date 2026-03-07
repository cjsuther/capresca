from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func
from app.db.base import Base


class UserLimit(Base):
    __tablename__ = "user_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    daily_limit = Column(Numeric(18, 2), nullable=False, default=0)
    per_transaction_limit = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="ARS")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
