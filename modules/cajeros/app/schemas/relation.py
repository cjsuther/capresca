from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime


class RelationCreate(BaseModel):
    cajero_user_id: int
    authorizer_user_id: int
    amount_threshold: Decimal = Decimal("0")
    currency: str = "ARS"


class RelationResponse(BaseModel):
    id: int
    cajero_user_id: int
    authorizer_user_id: int
    amount_threshold: Decimal
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
