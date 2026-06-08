from pydantic import BaseModel, Field
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


class TransferCreateRequest(BaseModel):
    """Form simplificado: la fecha se asigna server-side (hoy).

    Cuenta débito identificada por account_number + account_type (el sandbox
    de Interbanking no devuelve CBU). El destino sigue siendo CBU porque es
    un tercero fuera de las cuentas operativas.
    """
    cuenta_debito_account_number: str = Field(..., min_length=1, max_length=50)
    cuenta_debito_account_type: str = Field(..., pattern="^(CC|CA)$")
    cuenta_debito_bank_id: Optional[str] = Field(None, max_length=10)
    cbu_destino: str = Field(..., min_length=8, max_length=22)
    monto: Decimal = Field(..., gt=0)
    moneda: str = Field("ARS", pattern="^(ARS|USD)$")
    comentario: str = Field(..., min_length=1, max_length=255)


class TransferResponse(BaseModel):
    id: int
    cuenta_origen: Optional[str]
    cbu_destino: Optional[str]
    monto: Optional[Decimal]
    moneda: Optional[str]
    concepto: Optional[str]
    id_operacion_ib: Optional[str]
    status: Optional[str]
    initiated_by: Optional[int]
    initiated_at: Optional[datetime]
    last_status_check: Optional[datetime]
    last_status_payload: Optional[Any]

    model_config = {"from_attributes": True}
