from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=True)
    icon = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    permissions = relationship("Permission", back_populates="module")
