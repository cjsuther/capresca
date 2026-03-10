from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func
from app.db.base import Base


class AuthorizationRelation(Base):
    __tablename__ = "authorization_relations"

    id = Column(Integer, primary_key=True, index=True)
    cajero_user_id = Column(Integer, nullable=False, index=True)
    authorizer_user_id = Column(Integer, nullable=False, index=True)
    amount_threshold = Column(Numeric(18, 2), nullable=False, server_default="0")
    currency = Column(String(10), nullable=False, server_default="ARS")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
