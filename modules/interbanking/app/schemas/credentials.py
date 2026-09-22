from urllib.parse import urlparse

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

from app.config import provider_domains


def _validar_url_proveedor(valor: str, campo: str) -> str:
    """Sólo https y dentro de los dominios admitidos (ver ALLOWED_PROVIDER_DOMAINS)."""
    if not valor:
        return valor
    u = urlparse(valor)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not host:
        raise ValueError(f"{campo} debe ser una URL https del proveedor")
    if not any(host == d or host.endswith("." + d) for d in provider_domains()):
        raise ValueError(f"{campo} apunta a un host no permitido: {host}")
    return valor


class CredentialCreate(BaseModel):
    name: str
    base_url: str
    auth_url: str

    @field_validator("base_url", "auth_url", "service_url")
    @classmethod
    def _urls_del_proveedor(cls, v: str, info):
        return _validar_url_proveedor(v, info.field_name)

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
