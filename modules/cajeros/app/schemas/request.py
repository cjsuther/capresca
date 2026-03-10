from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.request import RequestStatus


class RequestCreate(BaseModel):
    amount: Decimal
    currency: str = "ARS"
    reason: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_notes: Optional[str] = None


class RequestResponse(BaseModel):
    id: int
    cajero_user_id: int
    amount: Decimal
    currency: str
    reason: Optional[str]
    status: RequestStatus
    requested_at: datetime
    authorizer_user_id: Optional[int]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]

    model_config = {"from_attributes": True}


class OperationResponse(BaseModel):
    id: int
    request_id: int
    executed_by_user_id: int
    executed_at: datetime
    amount: Decimal
    notes: Optional[str]

    model_config = {"from_attributes": True}
