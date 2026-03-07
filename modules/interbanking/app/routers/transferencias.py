from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_client_ip
from app.schemas.transfers import TransferValidateRequest, TransferIniciarRequest, TransferResponse
from app.services import transfer_service

router = APIRouter(tags=["transferencias"])


@router.get("", response_model=dict)
def list_transferencias(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    data, total = transfer_service.list_transfers(db, page, per_page)
    return {"data": [TransferResponse.model_validate(t).model_dump() for t in data], "total": total, "page": page, "per_page": per_page}


@router.post("/validar")
def validar(
    data: TransferValidateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.validar_cbu(db, user_id, data.cbu_or_alias, ip=get_client_ip(request))


@router.post("/iniciar", response_model=TransferResponse)
def iniciar(
    data: TransferIniciarRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.iniciar_transferencia(
        db, user_id,
        data.cuenta_origen, data.cbu_destino, data.monto, data.concepto,
        ip=get_client_ip(request),
    )


@router.get("/{transfer_id}/estado")
def get_estado(
    transfer_id: str,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.get_estado_transferencia(db, user_id, transfer_id, ip=get_client_ip(request))
