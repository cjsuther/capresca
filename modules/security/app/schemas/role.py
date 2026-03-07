from pydantic import BaseModel
from typing import List, Optional


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionRef(BaseModel):
    id: int
    code: str
    description: Optional[str]

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    permissions: List[PermissionRef] = []

    model_config = {"from_attributes": True}


class AssignPermissionsRequest(BaseModel):
    permission_ids: List[int]
