from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.request import AuthorizationRequest, AuthorizedOperation, RequestStatus
from app.schemas.request import RequestCreate, ResolveRequest


def create_request(db: Session, data: RequestCreate, cajero_user_id: int) -> AuthorizationRequest:
    req = AuthorizationRequest(
        cajero_user_id=cajero_user_id,
        amount=data.amount,
        currency=data.currency,
        reason=data.reason,
        authorizer_user_id=data.authorizer_user_id,
        status=RequestStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def get_requests(db: Session, user_id: int, as_authorizer: bool = False):
    if as_authorizer:
        return db.query(AuthorizationRequest).filter(
            AuthorizationRequest.authorizer_user_id == user_id
        ).order_by(AuthorizationRequest.requested_at.desc()).all()
    return db.query(AuthorizationRequest).filter(
        AuthorizationRequest.cajero_user_id == user_id
    ).order_by(AuthorizationRequest.requested_at.desc()).all()


def get_all_pending(db: Session, user_id: int):
    """Solicitudes pendientes asignadas a este autorizador."""
    return db.query(AuthorizationRequest).filter(
        AuthorizationRequest.authorizer_user_id == user_id,
        AuthorizationRequest.status == RequestStatus.PENDING,
    ).all()


def get_request(db: Session, request_id: int) -> AuthorizationRequest:
    req = db.query(AuthorizationRequest).filter(AuthorizationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return req


def approve_request(db: Session, request_id: int, authorizer_user_id: int, data: ResolveRequest) -> AuthorizationRequest:
    req = get_request(db, request_id)
    if req.status != RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Solo se pueden aprobar solicitudes PENDING")
    if req.authorizer_user_id and req.authorizer_user_id != authorizer_user_id:
        raise HTTPException(status_code=403, detail="No está asignado como autorizador de esta solicitud")

    req.status = RequestStatus.APPROVED
    req.authorizer_user_id = authorizer_user_id
    req.resolved_at = datetime.now(timezone.utc)
    req.resolution_notes = data.resolution_notes

    op = AuthorizedOperation(
        request_id=req.id,
        executed_by_user_id=authorizer_user_id,
        amount=req.amount,
        notes=data.resolution_notes,
    )
    db.add(op)
    db.commit()
    db.refresh(req)
    return req


def reject_request(db: Session, request_id: int, authorizer_user_id: int, data: ResolveRequest) -> AuthorizationRequest:
    req = get_request(db, request_id)
    if req.status != RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Solo se pueden rechazar solicitudes PENDING")
    if req.authorizer_user_id and req.authorizer_user_id != authorizer_user_id:
        raise HTTPException(status_code=403, detail="No está asignado como autorizador de esta solicitud")

    req.status = RequestStatus.REJECTED
    req.authorizer_user_id = authorizer_user_id
    req.resolved_at = datetime.now(timezone.utc)
    req.resolution_notes = data.resolution_notes
    db.commit()
    db.refresh(req)
    return req


def get_operations(db: Session):
    return db.query(AuthorizedOperation).order_by(AuthorizedOperation.executed_at.desc()).all()
