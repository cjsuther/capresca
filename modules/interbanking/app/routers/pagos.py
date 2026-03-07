from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_client_ip
from app.schemas.payment_batches import BatchCreate, BatchResponse
from app.services import batch_service

router = APIRouter(tags=["pagos"])


@router.get("/lotes")
def list_lotes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    data, total = batch_service.list_batches(db, page, per_page)
    return {"data": [BatchResponse.model_validate(b).model_dump() for b in data], "total": total, "page": page, "per_page": per_page}


@router.post("/lotes", response_model=BatchResponse, status_code=201)
def create_lote(
    data: BatchCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return batch_service.create_batch(db, user_id, data)


@router.get("/lotes/{batch_id}", response_model=BatchResponse)
def get_lote(batch_id: int, db: Session = Depends(get_db)):
    return batch_service.get_batch(db, batch_id)


@router.get("/lotes/{batch_id}/items")
def get_lote_items(batch_id: int, db: Session = Depends(get_db)):
    batch = batch_service.get_batch(db, batch_id)
    return batch.items


@router.post("/lotes/{batch_id}/procesar", response_model=BatchResponse)
def procesar_lote(
    batch_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return batch_service.procesar_batch(db, batch_id, user_id, ip=get_client_ip(request))


@router.get("/lotes/{batch_id}/estado")
def get_estado_lote(
    batch_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return batch_service.get_estado_batch(db, batch_id, user_id, ip=get_client_ip(request))
