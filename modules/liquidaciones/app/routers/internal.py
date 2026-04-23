from decimal import Decimal
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.batch import LiquidacionBatch
from app.models.procesada import LiquidacionProcesada
from app.services.processing import process_from_upload

router = APIRouter()


def verify_api_key(x_api_key: str = Header(...)):
    if not settings.internal_api_key:
        raise HTTPException(status_code=503, detail="API key no configurada")
    if x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


@router.post("/internal/liquidaciones/upload")
async def internal_upload_zip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un ZIP")
    content = await file.read()
    batch = process_from_upload(db, content, file.filename, user_id=0)
    return {
        "id": batch.id,
        "status": batch.status,
        "error_message": batch.error_message,
        "total_detail_records": batch.total_detail_records,
        "total_agencies": batch.total_agencies,
    }


@router.get("/internal/liquidaciones/batch/{batch_id}/agency-totals")
def get_agency_totals(
    batch_id: int,
    db: Session = Depends(get_db),
):
    batch = db.query(LiquidacionBatch).filter(LiquidacionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    procesadas = db.query(LiquidacionProcesada).filter(
        LiquidacionProcesada.batch_id == batch_id
    ).all()

    agency_data = defaultdict(lambda: {
        "total": Decimal("0"),
        "premios": Decimal("0"),
        "recaudacion": Decimal("0"),
        "comision": Decimal("0"),
    })

    for p in procesadas:
        agen = p.n_agen.strip()
        agency_data[agen]["total"] += p.total or Decimal("0")
        agency_data[agen]["premios"] += p.premios or Decimal("0")
        agency_data[agen]["recaudacion"] += p.recaudacion or Decimal("0")
        agency_data[agen]["comision"] += p.comision or Decimal("0")

    result = []
    for agen, data in sorted(agency_data.items()):
        result.append({
            "agency_number": agen,
            "total": float(data["total"]),
            "premios": float(data["premios"]),
            "adeudado": float(data["total"] - data["premios"]),
            "recaudacion": float(data["recaudacion"]),
            "comision": float(data["comision"]),
        })

    return {
        "batch_id": batch_id,
        "operation_date": batch.operation_date.isoformat() if batch.operation_date else None,
        "agencies": result,
    }
