from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import ApiAuditLog


def log(
    db: Session,
    user_id: int,
    operation: str,
    method: str,
    endpoint: str,
    request_payload: Optional[Any],
    response_status: Optional[int],
    response_payload: Optional[Any],
    duration_ms: int,
    success: bool,
    credential_id: Optional[int] = None,
    username: Optional[str] = None,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> ApiAuditLog:
    entry = ApiAuditLog(
        user_id=user_id,
        username=username,
        credential_id=credential_id,
        operation=operation,
        http_method=method,
        endpoint=endpoint,
        request_payload=request_payload,
        response_status=response_status,
        response_payload=response_payload,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
