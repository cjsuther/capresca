from decimal import Decimal
from pydantic import BaseModel
from datetime import date
from typing import Optional


class IbTransactionResponse(BaseModel):
    id: int
    type: str          # 'transfer' | 'batch_item'
    date: Optional[date]
    cbu: Optional[str]
    concepto: Optional[str]
    amount: Decimal
    status_ib: Optional[str]
    id_operacion_ib: Optional[str]

    resolved_client_id: Optional[int] = None
    resolved_agency_number: Optional[str] = None
    resolved_legal_name: Optional[str] = None
    match_type: Optional[str] = None
    reconciliation_record_id: Optional[int] = None
    reconciliation_link_id: Optional[int] = None
