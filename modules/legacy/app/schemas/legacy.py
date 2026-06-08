from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class InteractionOut(BaseModel):
    id: int
    direction: str
    database: str
    table_name: str
    operation: str
    occurred_at: datetime
    occurred_date: date
    rows_affected: Optional[int] = None
    status: str
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    origin_module: Optional[str] = None
    origin_user_id: Optional[int] = None
    outbox_id: Optional[int] = None
    payload_summary: Optional[Any] = None

    class Config:
        from_attributes = True


class InteractionPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[InteractionOut]


class SyncStateOut(BaseModel):
    table_name: str
    database: str
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    rows_seen: Optional[int] = None
    rows_changed: Optional[int] = None
    watermark: Optional[str] = None

    class Config:
        from_attributes = True


class StatusOut(BaseModel):
    integration_enabled: bool
    write_mode: str
    smb: dict
    sync_state: list[SyncStateOut]
    outbox_pending: int


class OutboxOut(BaseModel):
    id: int
    operation: str
    database: str
    idempotency_key: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    origin_module: Optional[str] = None
    origin_user_id: Optional[int] = None
    created_at: datetime
    applied_at: Optional[datetime] = None
    payload: Optional[Any] = None

    class Config:
        from_attributes = True


class OutboxPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OutboxOut]
