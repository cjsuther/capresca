from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional


class BatchItemCreate(BaseModel):
    cbu: str
    monto: Decimal
    detalle: Optional[str] = None


class BatchCreate(BaseModel):
    descripcion: str
    items: List[BatchItemCreate]


class BatchItemResponse(BaseModel):
    id: int
    cbu: Optional[str]
    monto: Optional[Decimal]
    detalle: Optional[str]
    status_item: Optional[str]

    model_config = {"from_attributes": True}


class BatchResponse(BaseModel):
    id: int
    descripcion: Optional[str]
    id_lote_ib: Optional[str]
    status: Optional[str]
    total_items: Optional[int]
    total_amount: Optional[Decimal]
    created_by: Optional[int]
    created_at: Optional[datetime]
    sent_at: Optional[datetime]
    last_status_check: Optional[datetime]
    last_status_payload: Optional[Any]
    items: List[BatchItemResponse] = []

    model_config = {"from_attributes": True}
