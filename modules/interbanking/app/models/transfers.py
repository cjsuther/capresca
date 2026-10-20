import re

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    audit_log_id = Column(BigInteger, ForeignKey("api_audit_log.id"), nullable=True)
    cuenta_origen = Column(String(100))  # CBU de la cuenta débito
    cbu_destino = Column(String(22))
    monto = Column(Numeric(15, 2))
    moneda = Column(String(3), default="ARS", nullable=False)
    concepto = Column(String(255))
    id_operacion_ib = Column(String(100))
    status = Column(String(50), default="INICIADA")
    initiated_by = Column(Integer)
    # Usuario de la plataforma que cargó la transferencia (Interbanking sólo conoce al operador de API).
    cargado_por = Column(String(60))
    initiated_at = Column(DateTime(timezone=True), server_default=func.now())
    last_status_check = Column(DateTime(timezone=True))
    last_status_payload = Column(JSONB)

    @property
    def motivo(self):
        """Por qué Interbanking rechazó el envío, sin el prefijo ni la URL que agrega el cliente."""
        error = (self.last_status_payload or {}).get("error") if isinstance(self.last_status_payload, dict) else None
        if not error:
            return None
        error = re.sub(r"\s*\[url=[^\]]*\]$", "", str(error))
        error = error.removeprefix("Error de Interbanking: ")
        return error.removeprefix("Se encontraron los siguientes errores en el body: ")
