from pydantic import BaseModel
from datetime import datetime


class RelationCreate(BaseModel):
    cajero_user_id: int
    authorizer_user_id: int


class RelationResponse(BaseModel):
    id: int
    cajero_user_id: int
    authorizer_user_id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
