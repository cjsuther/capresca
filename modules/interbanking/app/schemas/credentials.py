from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CredentialCreate(BaseModel):
    name: str
    base_url: str
    client_id: str
    client_secret: str


class CredentialResponse(BaseModel):
    id: int
    name: str
    base_url: str
    client_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenStatusResponse(BaseModel):
    has_active_token: bool
    expires_at: Optional[datetime] = None
    minutes_remaining: Optional[int] = None
