from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.request import RequestCreate, ResolveRequest, RequestResponse
from app.services.request_service import (
    create_request, get_requests, get_request, approve_request, reject_request
)

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestResponse, status_code=201)
def create(data: RequestCreate, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_request(db, data, user_id)


@router.get("", response_model=List[RequestResponse])
def list_requests(
    as_authorizer: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_requests(db, user_id, as_authorizer)


@router.get("/{request_id}", response_model=RequestResponse)
def detail(request_id: int, db: Session = Depends(get_db)):
    return get_request(db, request_id)


@router.put("/{request_id}/approve", response_model=RequestResponse)
def approve(
    request_id: int,
    data: ResolveRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return approve_request(db, request_id, user_id, data)


@router.put("/{request_id}/reject", response_model=RequestResponse)
def reject(
    request_id: int,
    data: ResolveRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return reject_request(db, request_id, user_id, data)
