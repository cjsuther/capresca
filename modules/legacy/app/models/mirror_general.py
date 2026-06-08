from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func
from app.db.base import Base


class MirrorMaestrodio(Base):
    """Espejo de general!maestrodio (maestro de agentes: legajos, haberes)."""

    __tablename__ = "mirror_maestrodio"

    id = Column(BigInteger, primary_key=True)
    legajo = Column(String(20), nullable=True, index=True)
    cuil = Column(String(15), nullable=True, index=True)
    nombre = Column(String(120), nullable=True)
    haberes = Column(Numeric(15, 2), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MirrorOrganismos(Base):
    """Espejo de general!organismos (catálogo de organismos empleadores)."""

    __tablename__ = "mirror_organismos"

    id = Column(BigInteger, primary_key=True)
    cod_organismo = Column(String(20), nullable=True, unique=True, index=True)
    descripcion = Column(String(120), nullable=True)
    capresca = Column(String(5), nullable=True)  # marca de convenio

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
