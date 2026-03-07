from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class LimitUpdate(BaseModel):
    daily_limit: Optional[Decimal] = None
    per_transaction_limit: Optional[Decimal] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


class LimitResponse(BaseModel):
    id: int
    user_id: int
    daily_limit: Decimal
    per_transaction_limit: Decimal
    currency: str
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
