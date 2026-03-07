from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class RoleRef(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    roles: List[RoleRef] = []

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    data: List[UserResponse]
    total: int
    page: int
    per_page: int


class AssignRolesRequest(BaseModel):
    role_ids: List[int]


class AdminChangePasswordRequest(BaseModel):
    new_password: str


class ChangeOwnPasswordRequest(BaseModel):
    current_password: str
    new_password: str
