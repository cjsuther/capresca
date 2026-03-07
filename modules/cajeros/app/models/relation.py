from sqlalchemy import Boolean, Column, DateTime, Integer, func
from app.db.base import Base


class AuthorizationRelation(Base):
    __tablename__ = "authorization_relations"

    id = Column(Integer, primary_key=True, index=True)
    cajero_user_id = Column(Integer, nullable=False, index=True)
    authorizer_user_id = Column(Integer, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
