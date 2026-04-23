from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services import cbu_cache_service
from app.models.liquidacion_record import LiquidacionConciliacionRecord

router = APIRouter(tags=["internal"])


@router.post("/internal/conciliacion/refresh-cbu-cache")
async def refresh_cbu_cache(db: Session = Depends(get_db)):
    count = await cbu_cache_service.rebuild_cache(db)
    return {"refreshed": count}


class LiquidacionAgenciaItem(BaseModel):
    agency_number: str
    operation_date: Optional[date]
    importe_adeudado: Decimal
    importe_premios: Decimal
    recaudacion_total: Decimal
    comision_total: Decimal
    resumen_number: Optional[str]
    moneda: Optional[str]
    batch_id: int
    batch_source: str


class LiquidacionesPayload(BaseModel):
    batch_id: int
    operation_date: Optional[date]
    agencies: list[LiquidacionAgenciaItem]


@router.post("/internal/conciliacion/liquidaciones")
def receive_liquidaciones(payload: LiquidacionesPayload, db: Session = Depends(get_db)):
    records = []
    for agency in payload.agencies:
        record = LiquidacionConciliacionRecord(
            liquidacion_batch_id=payload.batch_id,
            agency_number=agency.agency_number,
            operation_date=agency.operation_date,
            importe_adeudado=agency.importe_adeudado,
            importe_premios=agency.importe_premios,
            recaudacion_total=agency.recaudacion_total,
            comision_total=agency.comision_total,
            resumen_number=agency.resumen_number,
            moneda=agency.moneda,
        )
        records.append(record)

    db.add_all(records)
    db.commit()

    return {
        "received": len(records),
        "batch_id": payload.batch_id,
        "operation_date": payload.operation_date.isoformat() if payload.operation_date else None,
    }
