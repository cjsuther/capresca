import csv
import io
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.models.audit_log import ApiAuditLog
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse

router = APIRouter(tags=["auditoria"])


def _build_query(db, user_id, operation, success, date_from, date_to):
    q = db.query(ApiAuditLog).order_by(ApiAuditLog.created_at.desc())
    if user_id:
        q = q.filter(ApiAuditLog.user_id == user_id)
    if operation:
        q = q.filter(ApiAuditLog.operation == operation)
    if success is not None:
        q = q.filter(ApiAuditLog.success == success)
    if date_from:
        q = q.filter(ApiAuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(ApiAuditLog.created_at <= date_to)
    return q


@router.get("", response_model=AuditLogListResponse)
def list_auditoria(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    operation: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = _build_query(db, user_id, operation, success, date_from, date_to)
    total = q.count()
    data = q.offset((page - 1) * per_page).limit(per_page).all()
    return AuditLogListResponse(data=data, total=total, page=page, per_page=per_page)


@router.get("/export")
def export_csv(
    user_id: Optional[int] = Query(None),
    operation: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = _build_query(db, user_id, operation, success, date_from, date_to)
    rows = q.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "user_id", "username", "operation", "endpoint",
                     "http_method", "response_status", "duration_ms", "success", "error_message", "ip_address"])
    for r in rows:
        writer.writerow([r.id, r.created_at, r.user_id, r.username, r.operation, r.endpoint,
                         r.http_method, r.response_status, r.duration_ms, r.success, r.error_message, r.ip_address])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auditoria.csv"},
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
def get_auditoria(log_id: int, db: Session = Depends(get_db)):
    entry = db.query(ApiAuditLog).filter(ApiAuditLog.id == log_id).first()
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return entry
