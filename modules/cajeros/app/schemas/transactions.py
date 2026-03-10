from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TransactionCreate(BaseModel):
    currency: str = "ARS"
    amount: Decimal
    reference: Optional[str] = None
    description: Optional[str] = None


class RejectTransaction(BaseModel):
    rejection_reason: str


class TriggerResponse(BaseModel):
    id: int
    rule_id: int
    authorizer_user_id: int

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: int
    cajero_user_id: int
    cajero_username: Optional[str]
    authorizer_user_id: Optional[int]
    authorizer_username: Optional[str]
    currency: str
    amount: Decimal
    reference: Optional[str]
    description: Optional[str]
    status: str
    rejection_reason: Optional[str]
    authorized_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: int
    triggers: list[TriggerResponse] = []

    model_config = {"from_attributes": True}
