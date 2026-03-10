from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RuleCreate(BaseModel):
    cajero_user_id: int
    cajero_username: Optional[str] = None
    authorizer_user_id: int
    authorizer_username: Optional[str] = None
    currency: str = "ARS"
    amount_limit: Decimal
    reference: Optional[str] = None


class RuleResponse(BaseModel):
    id: int
    cajero_user_id: int
    cajero_username: Optional[str]
    authorizer_user_id: int
    authorizer_username: Optional[str]
    currency: str
    amount_limit: Decimal
    reference: Optional[str]
    is_active: bool
    created_at: datetime
    created_by: int

    model_config = {"from_attributes": True}
