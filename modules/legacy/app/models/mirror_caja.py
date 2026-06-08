from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Boolean, Date, DateTime, func, Index
from app.db.base import Base


class MirrorCajaliq(Base):
    """Espejo de caja!cajaliq (liquidaciones pendientes/pagadas)."""

    __tablename__ = "mirror_cajaliq"

    id = Column(BigInteger, primary_key=True)
    # clave natural: (cod_agencia, cod_juego, no_sorteo)
    cod_agencia = Column(String(10), nullable=False)
    cod_juego = Column(Integer, nullable=True)
    no_sorteo = Column(Integer, nullable=True)
    importe = Column(Numeric(15, 2), nullable=True)
    intereses = Column(Numeric(15, 2), nullable=True)
    pagado = Column(Boolean, nullable=True)
    fecha_pago = Column(Date, nullable=True)
    no_recibo = Column(Integer, nullable=True, index=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_mirror_cajaliq_natural", "cod_agencia", "cod_juego", "no_sorteo", unique=True),
    )


class MirrorCajapagos(Base):
    """Espejo de caja!cajapagos (registro principal de pagos)."""

    __tablename__ = "mirror_cajapagos"

    id = Column(BigInteger, primary_key=True)
    no_recibo = Column(Integer, nullable=False, unique=True, index=True)
    cod_agencia = Column(String(10), nullable=True, index=True)
    fecha_pago = Column(Date, nullable=True, index=True)
    origen = Column(String(20), nullable=True)
    total = Column(Numeric(15, 2), nullable=True)
    bonos = Column(Numeric(15, 2), nullable=True)
    pesos = Column(Numeric(15, 2), nullable=True)
    cajero = Column(String(50), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MirrorCajaforpag(Base):
    """Espejo de caja!cajaforpag (detalle de formas de pago)."""

    __tablename__ = "mirror_cajaforpag"

    id = Column(BigInteger, primary_key=True)
    no_recibo = Column(Integer, nullable=False, index=True)
    sno_recibo = Column(Integer, nullable=True)
    moneda = Column(String(5), nullable=True)
    origen = Column(String(20), nullable=True)
    fecha_pago = Column(Date, nullable=True)
    anulado = Column(Boolean, nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_mirror_cajaforpag_natural", "no_recibo", "sno_recibo", unique=True),
    )


class MirrorCajacreseg(Base):
    """Espejo de caja!cajacreseg (créditos y seguros cobrados)."""

    __tablename__ = "mirror_cajacreseg"

    id = Column(BigInteger, primary_key=True)
    nrecibo = Column(Integer, nullable=True, index=True)
    recofi = Column(Integer, nullable=True)
    origen = Column(String(20), nullable=True)
    fecha_pago = Column(Date, nullable=True, index=True)
    via_pago = Column(String(20), nullable=True)
    usuario_pago = Column(String(50), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
