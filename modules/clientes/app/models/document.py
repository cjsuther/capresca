from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, func

from app.db.base import Base


class ClientDocument(Base):
    """Documento del cliente (DNI, recibo de sueldo, constancias…). Los bytes van en la base, como en
    Créditos: el volumen es chico y así el módulo no depende de un storage aparte.

    `origen` dice de dónde vino ("Carga manual", "Solicitud SOL-2026-00001"…). `sha256` evita guardar dos
    veces el mismo archivo para el mismo cliente (la copia desde una solicitud es idempotente).
    """
    __tablename__ = "client_documents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False, default="OTRO")      # DNI_FRENTE, DNI_DORSO, RECIBO, OTRO
    nombre = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    tamano = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    contenido = Column(LargeBinary, nullable=False)
    origen = Column(String(120), nullable=False, default="Carga manual")
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
