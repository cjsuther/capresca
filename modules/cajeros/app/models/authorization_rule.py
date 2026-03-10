from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func
from app.db.base import Base


class AuthorizationRule(Base):
    __tablename__ = "authorization_rules"

    id = Column(Integer, primary_key=True, index=True)
    cajero_user_id = Column(Integer, nullable=False, index=True)
    cajero_username = Column(String(100), nullable=True)
    authorizer_user_id = Column(Integer, nullable=False, index=True)
    authorizer_username = Column(String(100), nullable=True)
    currency = Column(String(10), nullable=False)
    amount_limit = Column(Numeric(15, 2), nullable=False)
    reference = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=False)
