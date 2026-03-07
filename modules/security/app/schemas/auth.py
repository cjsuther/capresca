from pydantic import BaseModel
from typing import Dict, List


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPayload(BaseModel):
    user_id: int
    username: str


class UserInfo(BaseModel):
    id: int
    username: str
    full_name: str | None

    model_config = {"from_attributes": True}


class PermissionsPayload(BaseModel):
    modules: List[str]
    actions: Dict[str, List[str]]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    permissions: PermissionsPayload


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
