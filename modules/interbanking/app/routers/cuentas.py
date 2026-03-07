from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_client_ip
from app.services import interbanking_client

router = APIRouter(tags=["cuentas"])


@router.get("")
def list_cuentas(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return interbanking_client.call(
        db=db, user_id=user_id, operation="LISTAR_CUENTAS",
        method="GET", path="/cuentas",
        ip_address=get_client_ip(request),
    )


@router.get("/{cuenta_id}/saldo")
def get_saldo(
    cuenta_id: str,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return interbanking_client.call(
        db=db, user_id=user_id, operation="CONSULTAR_SALDO",
        method="GET", path=f"/cuentas/{cuenta_id}/saldo",
        ip_address=get_client_ip(request),
    )
