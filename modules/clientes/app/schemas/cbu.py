from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class ClientCbuCreate(BaseModel):
    cbu: str
    alias: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    description: Optional[str] = None
    is_payment_account: Optional[bool] = False

    @field_validator("cbu")
    @classmethod
    def validate_cbu(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 22:
            raise ValueError("CBU debe tener exactamente 22 dígitos numéricos")
        return v


class ClientCbuUpdate(BaseModel):
    alias: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    description: Optional[str] = None
    is_payment_account: Optional[bool] = None


class ClientCbuResponse(BaseModel):
    id: int
    client_id: int
    cbu: str
    alias: Optional[str]
    bank_name: Optional[str]
    account_type: Optional[str]
    description: Optional[str]
    is_active: bool
    is_payment_account: bool = False
    created_at: datetime
    created_by: int

    model_config = {"from_attributes": True}
