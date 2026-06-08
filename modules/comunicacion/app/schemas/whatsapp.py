from pydantic import BaseModel
from typing import Optional


class WhatsappConfigResponse(BaseModel):
    id: int
    phone_number_id: str
    business_account_id: str
    access_token_masked: str
    webhook_verify_token: str
    has_app_secret: bool = False
    display_phone_number: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class WhatsappConfigUpdate(BaseModel):
    phone_number_id: str
    business_account_id: str
    access_token: Optional[str] = None  # vacío => preservar el guardado
    webhook_verify_token: str
    app_secret: Optional[str] = None    # vacío => preservar el guardado
    display_phone_number: Optional[str] = None


class StatsResponse(BaseModel):
    total_conversations: int
    active_conversations: int
    unlinked_conversations: int
    messages_today: int
    unread_total: int
