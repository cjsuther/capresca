"""
Endpoints de Cuentas y Saldos contra la API Información Financiera de Interbanking.

Refs:
  - GET /v1/accounts                       -> Listado de cuentas
  - GET /v1/accounts/{account-number}      -> Detalle de una cuenta
  - GET /v1/accounts/balances              -> Saldos (uno o varios bancos/cuentas)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_client_ip
from app.scopes import INFO_FINANCIERA
from app.services import interbanking_client, token_manager

router = APIRouter(tags=["cuentas"])


def _resolve_customer_id(db: Session, override: Optional[str]) -> str:
    if override:
        return override
    cred = token_manager.get_active_credential(db)
    if not cred.customer_id:
        raise HTTPException(
            status_code=400,
            detail="customer_id no configurado. Cargalo en Configuración Interbanking.",
        )
    return cred.customer_id


@router.get("")
def list_cuentas(
    request: Request,
    account_type: Optional[str] = Query(None, alias="account-type", description="CC | CA"),
    bank_number: Optional[str] = Query(None, alias="bank-number", description="Código BCRA (3 dígitos)"),
    currency: Optional[str] = Query(None, description="ARS | USD"),
    customer_id: Optional[str] = Query(None, alias="customer-id"),
    limit: Optional[int] = Query(100, ge=1, le=500),
    page: Optional[int] = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    params = {"customer-id": _resolve_customer_id(db, customer_id)}
    if account_type: params["account-type"] = account_type
    if bank_number:  params["bank-number"] = bank_number
    if currency:     params["currency"] = currency
    if limit is not None: params["limit"] = limit
    if page is not None:  params["page"] = page

    return interbanking_client.call(
        db=db, user_id=user_id, operation="LISTAR_CUENTAS",
        method="GET", path="/v1/accounts",
        scope=INFO_FINANCIERA,
        params=params,
        ip_address=get_client_ip(request),
    )


@router.get("/saldos")
def list_saldos(
    request: Request,
    account_number: Optional[List[str]] = Query(None, alias="account-number"),
    bank_number: Optional[List[str]] = Query(None, alias="bank-number"),
    account_type: Optional[str] = Query(None, alias="account-type"),
    currency: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None, alias="customer-id"),
    date_since: Optional[str] = Query(None, alias="date-since", description="yyyy-mm-dd"),
    date_until: Optional[str] = Query(None, alias="date-until", description="yyyy-mm-dd"),
    limit: Optional[int] = Query(100, ge=1, le=500),
    page: Optional[int] = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    params: dict = {"customer-id": _resolve_customer_id(db, customer_id)}
    if account_number: params["account-number"] = account_number  # httpx serializa lista -> repetido
    if bank_number:    params["bank-number"] = bank_number
    if account_type:   params["account-type"] = account_type
    if currency:       params["currency"] = currency
    if date_since:     params["date-since"] = date_since
    if date_until:     params["date-until"] = date_until
    if limit is not None: params["limit"] = limit
    if page is not None:  params["page"] = page

    return interbanking_client.call(
        db=db, user_id=user_id, operation="CONSULTAR_SALDOS",
        method="GET", path="/v1/accounts/balances",
        scope=INFO_FINANCIERA,
        params=params,
        ip_address=get_client_ip(request),
    )


@router.get("/{account_number}/movimientos")
def list_movimientos(
    account_number: str,
    request: Request,
    account_type: Optional[str] = Query(None, alias="account-type", description="CC | CA"),
    bank_number: Optional[str] = Query(None, alias="bank-number", description="Código BCRA (3 dígitos)"),
    currency: Optional[str] = Query(None, description="ARS | USD"),
    customer_id: Optional[str] = Query(None, alias="customer-id"),
    date_since: Optional[str] = Query(None, alias="date-since", description="yyyy-mm-dd"),
    date_until: Optional[str] = Query(None, alias="date-until", description="yyyy-mm-dd"),
    tipo: str = Query("anteriores", description="Segmento de la API IB: anteriores (históricos) | dia (del día)"),
    limit: Optional[int] = Query(100, ge=1, le=500),
    page: Optional[int] = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Movimientos de una cuenta (GET /v1/accounts/{account-number}/movements/{tipo})."""
    params: dict = {"customer-id": _resolve_customer_id(db, customer_id)}
    if account_type: params["account-type"] = account_type
    if bank_number:  params["bank-number"] = bank_number
    if currency:     params["currency"] = currency
    if date_since:   params["date-since"] = date_since
    if date_until:   params["date-until"] = date_until
    if limit is not None: params["limit"] = limit
    if page is not None:  params["page"] = page

    return interbanking_client.call(
        db=db, user_id=user_id, operation="LISTAR_MOVIMIENTOS",
        method="GET", path=f"/v1/accounts/{account_number}/movements/{tipo}",
        scope=INFO_FINANCIERA,
        params=params,
        ip_address=get_client_ip(request),
    )


@router.get("/{account_number}")
def get_cuenta(
    account_number: str,
    request: Request,
    account_type: Optional[str] = Query(None, alias="account-type"),
    bank_number: Optional[str] = Query(None, alias="bank-number"),
    currency: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None, alias="customer-id"),
    limit: Optional[int] = Query(100, ge=1, le=500),
    page: Optional[int] = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    params = {"customer-id": _resolve_customer_id(db, customer_id)}
    if account_type: params["account-type"] = account_type
    if bank_number:  params["bank-number"] = bank_number
    if currency:     params["currency"] = currency
    if limit is not None: params["limit"] = limit
    if page is not None:  params["page"] = page

    return interbanking_client.call(
        db=db, user_id=user_id, operation="OBTENER_CUENTA",
        method="GET", path=f"/v1/accounts/{account_number}",
        scope=INFO_FINANCIERA,
        params=params,
        ip_address=get_client_ip(request),
    )
