from pydantic import BaseModel
from typing import Optional, List, Any


class MenuOptionSchema(BaseModel):
    option_id: str
    title: str
    description: Optional[str] = None
    sort_order: int = 0
    action_type: str  # REPLY_TEXT | CALL_MODULE
    action_payload: dict[str, Any]
    requires_client: bool = True
    is_active: bool = True


class MenuConfigResponse(BaseModel):
    id: int
    greeting_text: str
    is_active: bool
    options: List[MenuOptionSchema]

    model_config = {"from_attributes": True}


class MenuConfigUpdate(BaseModel):
    greeting_text: str
    options: List[MenuOptionSchema]
