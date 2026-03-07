from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class ApiAuditLog(Base):
    __tablename__ = "api_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100))
    credential_id = Column(Integer, ForeignKey("interbanking_credentials.id"), nullable=True)
    operation = Column(String(100), nullable=False)
    http_method = Column(String(10))
    endpoint = Column(String(255))
    request_payload = Column(JSONB)
    response_status = Column(Integer)
    response_payload = Column(JSONB)
    duration_ms = Column(Integer)
    success = Column(Boolean)
    error_message = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
