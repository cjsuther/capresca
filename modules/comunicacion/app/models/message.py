from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, func
from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, index=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # INBOUND | OUTBOUND
    message_type = Column(String(20), nullable=False)  # TEXT | IMAGE | DOCUMENT | AUDIO | VIDEO | INTERACTIVE | TEMPLATE
    content = Column(Text, nullable=True)
    media_url = Column(String(1000), nullable=True)
    media_mime_type = Column(String(100), nullable=True)
    media_filename = Column(String(255), nullable=True)
    media_local_path = Column(String(500), nullable=True)

    # WhatsApp metadata
    wa_message_id = Column(String(100), unique=True, nullable=True)
    wa_status = Column(String(20), nullable=True)  # SENT | DELIVERED | READ | FAILED
    wa_error_code = Column(String(20), nullable=True)
    wa_error_message = Column(Text, nullable=True)

    # Sender info (for outbound)
    sent_by_user_id = Column(Integer, nullable=True)
    sent_by_username = Column(String(100), nullable=True)
    sent_by_module = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Interactive reply data
    interactive_reply_id = Column(String(100), nullable=True)
    interactive_reply_title = Column(String(255), nullable=True)
