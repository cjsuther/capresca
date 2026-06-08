from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func
from app.db.base import Base


class MirrorMaeagencias(Base):
    """Espejo de juegos!maeagencias (maestro de agencias)."""

    __tablename__ = "mirror_maeagencias"

    id = Column(BigInteger, primary_key=True)
    cod_agencia = Column(String(10), nullable=False, unique=True, index=True)
    titular = Column(String(120), nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MirrorMaejuegos(Base):
    """Espejo de juegos!maejuegos (maestro de juegos)."""

    __tablename__ = "mirror_maejuegos"

    id = Column(BigInteger, primary_key=True)
    cod_juego = Column(Integer, nullable=False, unique=True, index=True)
    descripcion = Column(String(120), nullable=True)
    modalidad = Column(Integer, nullable=True)

    row_hash = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
