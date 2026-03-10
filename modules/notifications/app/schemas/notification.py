from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str
    module: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    redirect_path: Optional[str] = None
    created_by_module: Optional[str] = None


class BulkNotificationCreate(BaseModel):
    notifications: List[NotificationCreate]


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    module: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    redirect_path: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    created_by_module: Optional[str]

    model_config = {"from_attributes": True}


class NotificationsListResponse(BaseModel):
    data: List[NotificationResponse]
    unread_count: int
    total: int


class UnreadCountResponse(BaseModel):
    count: int
