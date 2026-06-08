from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_client_ip
from app.schemas.transfers import (
    TransferCreateRequest,
    TransferResponse,
    TransferValidateRequest,
)
from app.services import transfer_service

router = APIRouter(tags=["transferencias"])


# ─────────────────────────────────────────────────────────────────────────────
# Listado (Interbanking)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("")
def listar(
    request: Request,
    date_since: Optional[str] = Query(None, description="yyyy-mm-dd (default: hoy)"),
    date_until: Optional[str] = Query(None, description="yyyy-mm-dd (default: hoy)"),
    page: int = Query(0, ge=0),
    rows: int = Query(100, ge=1, le=500),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data = transfer_service.listar_transferencias_remoto(
        db=db, user_id=user_id,
        date_since=date_since, date_until=date_until,
        page=page, rows=rows,
        ip=get_client_ip(request),
    )
    return {"mock": settings.interbanking_mock_transfers, **data}


# ─────────────────────────────────────────────────────────────────────────────
# Crear
# ─────────────────────────────────────────────────────────────────────────────
@router.post("", response_model=TransferResponse)
def crear(
    data: TransferCreateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.crear_transferencia(
        db=db, user_id=user_id,
        cuenta_debito_account_number=data.cuenta_debito_account_number,
        cuenta_debito_account_type=data.cuenta_debito_account_type,
        cuenta_debito_bank_id=data.cuenta_debito_bank_id,
        cbu_destino=data.cbu_destino,
        monto=data.monto,
        moneda=data.moneda,
        comentario=data.comentario,
        ip=get_client_ip(request),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy (validar / iniciar / estado) — se mantienen
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/local", response_model=dict)
def list_local(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    data, total = transfer_service.list_local_transfers(db, page, per_page)
    return {
        "data": [TransferResponse.model_validate(t).model_dump() for t in data],
        "total": total, "page": page, "per_page": per_page,
    }


@router.post("/validar")
def validar(
    data: TransferValidateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.validar_cbu(db, user_id, data.cbu_or_alias, ip=get_client_ip(request))


@router.get("/{transfer_id}/estado")
def get_estado(
    transfer_id: str,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transfer_service.get_estado_transferencia(db, user_id, transfer_id, ip=get_client_ip(request))
