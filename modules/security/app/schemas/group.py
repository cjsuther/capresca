from typing import List, Optional

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=64)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoleRef(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MemberRef(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    roles: List[RoleRef] = []
    users: List[MemberRef] = []

    model_config = {"from_attributes": True}


class AssignGroupRolesRequest(BaseModel):
    role_ids: List[int]


class AssignMembersRequest(BaseModel):
    user_ids: List[int]
