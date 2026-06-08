from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from app.db.base import Base


class InterbankingToken(Base):
    __tablename__ = "interbanking_tokens"

    id = Column(Integer, primary_key=True)
    credential_id = Column(Integer, ForeignKey("interbanking_credentials.id"), nullable=False)
    scope = Column(String(64), nullable=True)  # nullable por migración; nuevos rows siempre tienen valor
    access_token = Column(Text, nullable=False)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    obtained_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)
