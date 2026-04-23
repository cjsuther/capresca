from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class MessageCreate(BaseModel):
    content: str
    message_type: str = "TEXT"


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    direction: str
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    media_mime_type: Optional[str]
    media_filename: Optional[str]
    wa_message_id: Optional[str]
    wa_status: Optional[str]
    sent_by_user_id: Optional[int]
    sent_by_username: Optional[str]
    sent_by_module: Optional[str]
    created_at: datetime
    interactive_reply_id: Optional[str]
    interactive_reply_title: Optional[str]

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    data: List[MessageResponse]
    total: int


class InternalSendRequest(BaseModel):
    client_id: int
    phone: Optional[str] = None
    message: str
    message_type: str = "TEXT"
    media_url: Optional[str] = None
    media_filename: Optional[str] = None
    sent_by_module: Optional[str] = None


class InternalSendResponse(BaseModel):
    message_id: int
    wa_message_id: Optional[str]
    status: str
