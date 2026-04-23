from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from app.db.base import Base


class WhatsappConfig(Base):
    __tablename__ = "whatsapp_config"

    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(String(50), nullable=False)
    business_account_id = Column(String(50), nullable=False)
    access_token = Column(Text, nullable=False)
    webhook_verify_token = Column(String(255), nullable=False)
    display_phone_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(Integer, nullable=True)
