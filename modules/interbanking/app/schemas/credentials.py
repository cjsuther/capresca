from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CredentialCreate(BaseModel):
    name: str
    base_url: str
    auth_url: str
    client_id: str
    # info-financiera
    client_secret: Optional[str] = ""
    # transferencias-confeccion
    username: Optional[str] = ""
    password: Optional[str] = ""
    # Comunes
    service_url: str = ""
    customer_id: Optional[str] = ""
    # Cuenta elegida para la consolidación bancaria (conciliación)
    consolidation_account_number: Optional[str] = ""
    consolidation_account_type: Optional[str] = "CC"
    consolidation_bank_number: Optional[str] = "011"
    consolidation_currency: Optional[str] = "ARS"
    # Cuenta de pagos salientes (Capresca → agencias)
    payment_account_number: Optional[str] = ""
    payment_account_type: Optional[str] = "CC"
    payment_bank_number: Optional[str] = "011"
    payment_currency: Optional[str] = "ARS"


class CredentialResponse(BaseModel):
    id: int
    name: str
    base_url: str
    auth_url: str
    client_id: str
    username: Optional[str] = None
    service_url: Optional[str] = None
    customer_id: Optional[str] = None
    consolidation_account_number: Optional[str] = None
    consolidation_account_type: Optional[str] = None
    consolidation_bank_number: Optional[str] = None
    consolidation_currency: Optional[str] = None
    payment_account_number: Optional[str] = None
    payment_account_type: Optional[str] = None
    payment_bank_number: Optional[str] = None
    payment_currency: Optional[str] = None
    has_client_secret: bool = False
    has_password: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenStatusEntry(BaseModel):
    scope: str
    has_active_token: bool
    expires_at: Optional[datetime] = None
    minutes_remaining: Optional[int] = None


class TokenStatusResponse(BaseModel):
    tokens: list[TokenStatusEntry] = []
