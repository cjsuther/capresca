from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class ClientType(str, enum.Enum):
    HUMAN = "HUMAN"
    LEGAL = "LEGAL"


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_type = Column(Enum(ClientType), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(64), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(128), nullable=True)
    country = Column(String(64), nullable=True, default="AR")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_user_id = Column(Integer, nullable=True)

    human_profile = relationship("HumanClient", back_populates="client", uselist=False)
    legal_profile = relationship("LegalClient", back_populates="client", uselist=False)
    contacts = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")
    cbus = relationship("ClientCbu", foreign_keys="ClientCbu.client_id", cascade="all, delete-orphan")


class HumanClient(Base):
    __tablename__ = "human_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    document_type = Column(String(32), nullable=True)
    document_number = Column(String(64), nullable=True, index=True)
    birth_date = Column(String(16), nullable=True)
    gender = Column(String(16), nullable=True)
    nationality = Column(String(64), nullable=True)

    client = relationship("Client", back_populates="human_profile")


class LegalClient(Base):
    __tablename__ = "legal_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    tax_id = Column(String(64), nullable=True, index=True)
    tax_id_type = Column(String(32), nullable=True)
    incorporation_date = Column(String(16), nullable=True)
    legal_representative = Column(String(255), nullable=True)
    industry_sector = Column(String(128), nullable=True)
    agency_number = Column(String(20), nullable=True, unique=True)

    client = relationship("Client", back_populates="legal_profile")


class ClientContact(Base):
    __tablename__ = "client_contacts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_type = Column(String(32), nullable=False)
    value = Column(String(255), nullable=False)
    label = Column(String(128), nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)

    client = relationship("Client", back_populates="contacts")


class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="notes")


class LegalClientMember(Base):
    """Vincula personas físicas (PH) a una persona jurídica (PJ)."""
    __tablename__ = "legal_client_members"

    id = Column(Integer, primary_key=True, index=True)
    legal_client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    human_client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(128), nullable=True)   # "Socio", "Director", "Apoderado", etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    legal_client = relationship("Client", foreign_keys=[legal_client_id])
    human_client = relationship("Client", foreign_keys=[human_client_id])


class ClientCbu(Base):
    __tablename__ = "client_cbus"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    cbu = Column(String(22), nullable=False, unique=True, index=True)
    alias = Column(String(100), nullable=True)
    bank_name = Column(String(100), nullable=True)
    account_type = Column(String(50), nullable=True)  # 'CC' | 'CA' | 'OTRO'
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Marca el CBU como cuenta de cobro (destino de los pagos salientes de Capresca)
    is_payment_account = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=False)

    client = relationship("Client", foreign_keys=[client_id], overlaps="cbus")
