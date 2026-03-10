from sqlalchemy import Column, DateTime, Integer, String, func
from app.db.base import Base


class CbuAgencyCache(Base):
    __tablename__ = "cbu_agency_cache"

    cbu = Column(String(22), primary_key=True)
    client_id = Column(Integer, nullable=False)
    agency_number = Column(String(20), nullable=True)
    legal_name = Column(String(255), nullable=True)
    cached_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
