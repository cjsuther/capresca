from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


class TransferValidateRequest(BaseModel):
    cbu_or_alias: str


class TransferIniciarRequest(BaseModel):
    cuenta_origen: str
    cbu_destino: str
    monto: Decimal
    concepto: str


class TransferResponse(BaseModel):
    id: int
    cuenta_origen: Optional[str]
    cbu_destino: Optional[str]
    monto: Optional[Decimal]
    concepto: Optional[str]
    id_operacion_ib: Optional[str]
    status: Optional[str]
    initiated_by: Optional[int]
    initiated_at: Optional[datetime]
    last_status_check: Optional[datetime]
    last_status_payload: Optional[Any]

    model_config = {"from_attributes": True}
