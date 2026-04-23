from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class ProcessRequest(BaseModel):
    zip_path: str


class BatchResponse(BaseModel):
    id: int
    zip_filename: str
    operation_date: Optional[date]
    resumen_number: Optional[str]
    status: str
    total_detail_records: Optional[int]
    total_summary_records: Optional[int]
    total_agencies: Optional[int]
    error_message: Optional[str]
    created_by: int
    created_at: datetime
    processed_at: Optional[datetime]
    sent_to_conciliacion_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProcesadaResponse(BaseModel):
    id: int
    batch_id: int
    n_agen: str
    c_juego: int
    d_juego: Optional[str]
    n_sorteo: int
    modalidad: int
    moneda: Optional[str]
    recaudacion: Decimal
    premios: Decimal
    comision: Decimal
    fdo_gtia: Decimal
    ing_brutos: Decimal
    debitos: Decimal
    creditos: Decimal
    total: Decimal
    no_recibo: Optional[int]
    operation_date: Optional[date]

    class Config:
        from_attributes = True


class ValidacionResponse(BaseModel):
    id: int
    batch_id: int
    validation_type: str
    agency_number: Optional[str]
    expected_value: Optional[Decimal]
    actual_value: Optional[Decimal]
    passed: bool
    detail_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ArchivoResponse(BaseModel):
    id: int
    batch_id: int
    file_type: str
    original_filename: str
    file_size: int
    created_at: datetime

    class Config:
        from_attributes = True


class DetalleRawResponse(BaseModel):
    id: int
    batch_id: int
    n_agen: str
    c_juego: str
    d_juego: str
    n_sorteo: str
    c_codigo: str
    d_codigo: str
    d_operac: str
    importe: Decimal
    c_moneda: Optional[str]
    c_resumen: Optional[str]

    class Config:
        from_attributes = True
