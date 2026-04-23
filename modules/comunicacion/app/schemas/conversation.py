from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ConversationCreate(BaseModel):
    client_id: int
    phone: str


class ConversationLinkClient(BaseModel):
    client_id: int
    add_phone_as_contact: bool = False


class ConversationResponse(BaseModel):
    id: int
    client_id: Optional[int]
    client_name: Optional[str]
    client_phone: str
    status: str
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str]
    unread_count: int
    assigned_to_user_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    data: List[ConversationResponse]
    total: int
    page: int
    per_page: int
