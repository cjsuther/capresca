from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, func
from app.db.base import Base


class LiquidacionProcesada(Base):
    __tablename__ = "liquidacion_procesadas"

    id = Column(BigInteger, primary_key=True)
    batch_id = Column(BigInteger, ForeignKey("liquidacion_batches.id"), nullable=False, index=True)
    n_agen = Column(String(6), nullable=False)
    c_juego = Column(Integer, nullable=False)
    d_juego = Column(String(50), nullable=True)
    n_sorteo = Column(Integer, nullable=False)
    modalidad = Column(Integer, nullable=False, server_default="0")
    moneda = Column(String(5), nullable=True)
    recaudacion = Column(Numeric(15, 2), nullable=False, server_default="0")
    premios = Column(Numeric(15, 2), nullable=False, server_default="0")
    comision = Column(Numeric(15, 2), nullable=False, server_default="0")
    fdo_gtia = Column(Numeric(15, 2), nullable=False, server_default="0")
    ing_brutos = Column(Numeric(15, 2), nullable=False, server_default="0")
    debitos = Column(Numeric(15, 2), nullable=False, server_default="0")
    creditos = Column(Numeric(15, 2), nullable=False, server_default="0")
    total = Column(Numeric(15, 2), nullable=False, server_default="0")
    no_recibo = Column(Integer, nullable=True)
    operation_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("batch_id", "n_agen", "c_juego", "n_sorteo", "modalidad",
                         name="uq_procesada_batch_agen_juego_sorteo_mod"),
    )
