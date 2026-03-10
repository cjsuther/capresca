from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CredentialCreate(BaseModel):
    name: str
    base_url: str
    auth_url: str
    client_id: str
    username: str
    password: str
    scope: str = "transferencias-confeccion"
    service_url: str = ""


class CredentialResponse(BaseModel):
    id: int
    name: str
    base_url: str
    auth_url: str
    client_id: str
    username: str
    scope: str
    service_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenStatusResponse(BaseModel):
    has_active_token: bool
    expires_at: Optional[datetime] = None
    minutes_remaining: Optional[int] = None
