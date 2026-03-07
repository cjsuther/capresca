from pydantic import BaseModel
from datetime import datetime
from typing import Any, List, Optional


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str]
    credential_id: Optional[int]
    operation: str
    http_method: Optional[str]
    endpoint: Optional[str]
    request_payload: Optional[Any]
    response_status: Optional[int]
    response_payload: Optional[Any]
    duration_ms: Optional[int]
    success: Optional[bool]
    error_message: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    data: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
