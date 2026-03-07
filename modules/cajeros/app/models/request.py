from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class AuthorizationRequest(Base):
    __tablename__ = "authorization_requests"

    id = Column(Integer, primary_key=True, index=True)
    cajero_user_id = Column(Integer, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="ARS")
    reason = Column(Text, nullable=True)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    authorizer_user_id = Column(Integer, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    operation = relationship("AuthorizedOperation", back_populates="request", uselist=False)


class AuthorizedOperation(Base):
    __tablename__ = "authorized_operations"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("authorization_requests.id"), nullable=False, unique=True)
    executed_by_user_id = Column(Integer, nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    amount = Column(Numeric(18, 2), nullable=False)
    notes = Column(Text, nullable=True)

    request = relationship("AuthorizationRequest", back_populates="operation")
