from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    audit_log_id = Column(BigInteger, ForeignKey("api_audit_log.id"), nullable=True)
    cuenta_origen = Column(String(100))
    cbu_destino = Column(String(22))
    monto = Column(Numeric(15, 2))
    concepto = Column(String(255))
    id_operacion_ib = Column(String(100))
    status = Column(String(50), default="INICIADA")
    initiated_by = Column(Integer)
    initiated_at = Column(DateTime(timezone=True), server_default=func.now())
    last_status_check = Column(DateTime(timezone=True))
    last_status_payload = Column(JSONB)
