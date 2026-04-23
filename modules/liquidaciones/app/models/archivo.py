from sqlalchemy import Column, BigInteger, String, Integer, LargeBinary, DateTime, ForeignKey, func
from app.db.base import Base


class LiquidacionArchivo(Base):
    __tablename__ = "liquidacion_archivos"

    id = Column(BigInteger, primary_key=True)
    batch_id = Column(BigInteger, ForeignKey("liquidacion_batches.id"), nullable=False, index=True)
    file_type = Column(String(30), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
