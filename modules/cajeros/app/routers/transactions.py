from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.transactions import TransactionCreate, TransactionResponse, RejectTransaction
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_username(x_username: Optional[str] = Header(None)) -> Optional[str]:
    return x_username


def get_permissions(x_permissions: Optional[str] = Header(None)) -> list[str]:
    if not x_permissions:
        return []
    return [p.strip() for p in x_permissions.split(",")]


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    data: TransactionCreate,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_username),
    db: Session = Depends(get_db),
):
    return await transaction_service.create_transaction(db, data, user_id, username)


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    status: Optional[str] = None,
    currency: Optional[str] = None,
    cajero: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
    perms: list[str] = Depends(get_permissions),
    db: Session = Depends(get_db),
):
    can_read_all = "transactions:read_all" in perms or "transactions:admin" in perms
    status_filter = [s.strip() for s in status.split(",")] if status else None
    return transaction_service.get_transactions(db, user_id, can_read_all, status_filter, currency, cajero)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    return transaction_service.get_transaction(db, transaction_id)


@router.put("/{transaction_id}/authorize", response_model=TransactionResponse)
async def authorize(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_username),
    db: Session = Depends(get_db),
):
    return await transaction_service.authorize_transaction(db, transaction_id, user_id, username)


@router.put("/{transaction_id}/reject", response_model=TransactionResponse)
async def reject(
    transaction_id: int,
    data: RejectTransaction,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_username),
    db: Session = Depends(get_db),
):
    return await transaction_service.reject_transaction(db, transaction_id, user_id, username, data)


@router.delete("/{transaction_id}", response_model=TransactionResponse)
def delete(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    perms: list[str] = Depends(get_permissions),
    db: Session = Depends(get_db),
):
    is_admin = "transactions:admin" in perms
    return transaction_service.delete_transaction(db, transaction_id, user_id, is_admin)
