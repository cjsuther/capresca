from sqlalchemy import Column, BigInteger, String, Numeric, ForeignKey
from app.db.base import Base


class LiquidacionResumenRaw(Base):
    __tablename__ = "liquidacion_resumen_raw"

    id = Column(BigInteger, primary_key=True)
    batch_id = Column(BigInteger, ForeignKey("liquidacion_batches.id"), nullable=False, index=True)
    c_juego = Column(String(3), nullable=False)
    n_agen = Column(String(6), nullable=False)
    d_operac = Column(String(10), nullable=False)
    importe = Column(Numeric(15, 2), nullable=False)
    c_moneda = Column(String(2), nullable=True)
    c_resumen = Column(String(10), nullable=True)
    f_movin = Column(String(5), nullable=True)
