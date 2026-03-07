from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from app.db.base import Base


class InterbankingCredential(Base):
    __tablename__ = "interbanking_credentials"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    base_url = Column(String(255), nullable=False)
    client_id = Column(String(255), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
