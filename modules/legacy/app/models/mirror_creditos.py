from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Date, DateTime, func, Index
from app.db.base import Base


class MirrorMaeclientes(Base):
    """Espejo de creditos!maeclientes (maestro de clientes de la cartera)."""

    __tablename__ = "mirror_maeclientes"

    id = Column(BigInteger, primary_key=True)
    cuil = Column(String(15), nullable=True, index=True)
    nombre = Column(String(120), nullable=True)
    domicilio = Column(String(120), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MirrorSolicitud(Base):
    """Espejo de creditos!solicitud (solicitudes de préstamos vigentes)."""

    __tablename__ = "mirror_solicitud"

    id = Column(BigInteger, primary_key=True)
    no_credito = Column(Integer, nullable=False, unique=True, index=True)
    cuil = Column(String(15), nullable=True, index=True)
    estado = Column(String(2), nullable=True)  # A | P | L ...
    monto = Column(Numeric(15, 2), nullable=True)
    tasa = Column(Numeric(8, 4), nullable=True)
    ga_cuil = Column(String(15), nullable=True)
    g2_cuil = Column(String(15), nullable=True)
    g3_cuil = Column(String(15), nullable=True)
    g4_cuil = Column(String(15), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MirrorMaecuotas(Base):
    """Espejo de creditos!maecuotas (plan de pagos / mora)."""

    __tablename__ = "mirror_maecuotas"

    id = Column(BigInteger, primary_key=True)
    no_credito = Column(Integer, nullable=False, index=True)
    no_cuota = Column(Integer, nullable=False)
    estado = Column(String(2), nullable=True)  # A | M ...
    fecha_vto = Column(Date, nullable=True, index=True)
    total_vdo = Column(Numeric(15, 2), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_mirror_maecuotas_natural", "no_credito", "no_cuota", unique=True),
    )


class MirrorLineacred(Base):
    """Espejo de creditos!lineacred (líneas de crédito)."""

    __tablename__ = "mirror_lineacred"

    id = Column(BigInteger, primary_key=True)
    cod_linea = Column(Integer, nullable=False, unique=True, index=True)
    descripcion = Column(String(120), nullable=True)
    nmoradia = Column(Numeric(8, 4), nullable=True)  # tasa punitoria diaria

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
