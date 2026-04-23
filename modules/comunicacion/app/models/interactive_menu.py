from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class InteractiveMenuConfig(Base):
    __tablename__ = "interactive_menu_config"

    id = Column(Integer, primary_key=True, index=True)
    greeting_text = Column(
        Text,
        nullable=False,
        default="Hola! Bienvenido a Portezuelo. Seleccione una opcion:",
    )
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)

    options = relationship(
        "InteractiveMenuOption",
        back_populates="menu",
        order_by="InteractiveMenuOption.sort_order",
        cascade="all, delete-orphan",
    )


class InteractiveMenuOption(Base):
    __tablename__ = "interactive_menu_options"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("interactive_menu_config.id"), nullable=False)
    option_id = Column(String(50), nullable=False)
    title = Column(String(60), nullable=False)
    description = Column(String(200), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    action_type = Column(String(30), nullable=False)  # REPLY_TEXT | CALL_MODULE
    action_payload = Column(JSONB, nullable=False)
    requires_client = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    menu = relationship("InteractiveMenuConfig", back_populates="options")
