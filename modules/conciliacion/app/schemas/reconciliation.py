from decimal import Decimal
from pydantic import BaseModel, computed_field
from datetime import date, datetime
from typing import Optional, List


class RecordResponse(BaseModel):
    id: int
    reconciliation_date: date
    client_id: int
    agency_number: Optional[str]
    agency_legal_name: str
    agency_tax_id: Optional[str]
    importe_adeudado: Decimal
    importe_premios: Decimal
    importe_depositado: Decimal
    importe_neto: Decimal
    status: str
    modified_by_user_id: Optional[int]
    modified_by_username: Optional[str]
    modified_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # inject computed importe_neto from model property
        instance = super().model_validate(obj, **kwargs)
        if hasattr(obj, 'importe_neto'):
            instance.importe_neto = obj.importe_neto
        return instance


class LinkResponse(BaseModel):
    id: int
    reconciliation_record_id: int
    ib_transaction_type: str
    ib_transaction_id: int
    ib_amount: Decimal
    ib_cbu: str
    ib_concepto: Optional[str]
    match_type: str
    linked_by_user_id: int
    linked_at: datetime
    unlinked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    id: int
    previous_status: Optional[str]
    new_status: str
    previous_importe_adeudado: Optional[Decimal]
    previous_importe_premios: Optional[Decimal]
    previous_importe_depositado: Optional[Decimal]
    new_importe_adeudado: Optional[Decimal]
    new_importe_premios: Optional[Decimal]
    new_importe_depositado: Optional[Decimal]
    changed_by_user_id: int
    changed_by_username: Optional[str]
    changed_at: datetime
    notes: Optional[str]

    model_config = {"from_attributes": True}


class IbLinkAdd(BaseModel):
    ib_transaction_type: str
    ib_transaction_id: int


class RecordUpdate(BaseModel):
    importe_adeudado: Optional[Decimal] = None
    importe_premios: Optional[Decimal] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    ib_links_to_add: List[IbLinkAdd] = []
    ib_links_to_remove: List[int] = []


class AssignAgencyRequest(BaseModel):
    client_id: int


class SummaryResponse(BaseModel):
    date: str
    A_VERIFICAR: int
    CONSOLIDADO: int
    CONSOLIDADO_MANUAL: int
    total_records: int
    total_importe_adeudado: Decimal
    total_importe_depositado: Decimal
    total_importe_neto: Decimal
