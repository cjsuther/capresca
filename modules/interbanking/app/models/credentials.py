from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from app.db.base import Base


class InterbankingCredential(Base):
    __tablename__ = "interbanking_credentials"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    base_url = Column(String(255), nullable=False)
    auth_url = Column(String(255), nullable=True)
    client_id = Column(String(255), nullable=False)
    # info-financiera (client_credentials)
    client_secret_encrypted = Column(Text, nullable=True)
    # transferencias-confeccion (password)
    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)
    # Comunes
    service_url = Column(String(512), nullable=True)
    customer_id = Column(String(50), nullable=True)
    # Cuenta bancaria elegida como fuente de depósitos para la consolidación de conciliación
    consolidation_account_number = Column(String(50), nullable=True)
    consolidation_account_type = Column(String(5), nullable=True)
    consolidation_bank_number = Column(String(5), nullable=True)
    consolidation_currency = Column(String(5), nullable=True)
    # Cuenta de Capresca desde la que salen los pagos a agencias (saldo positivo)
    payment_account_number = Column(String(50), nullable=True)
    payment_account_type = Column(String(5), nullable=True)
    payment_bank_number = Column(String(5), nullable=True)
    payment_currency = Column(String(5), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
