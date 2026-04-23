from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func
from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(BigInteger, primary_key=True, index=True)
    client_id = Column(Integer, nullable=True, index=True)
    client_name = Column(String(255), nullable=True)
    client_phone = Column(String(20), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message_preview = Column(String(255), nullable=True)
    unread_count = Column(Integer, nullable=False, default=0)
    assigned_to_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
