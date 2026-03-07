from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse, AssignPermissionsRequest
from app.services.role_service import get_roles, create_role, update_role, delete_role, assign_permissions

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=List[RoleResponse])
def list_roles(db: Session = Depends(get_db)):
    return get_roles(db)


@router.post("", response_model=RoleResponse, status_code=201)
def create(data: RoleCreate, db: Session = Depends(get_db)):
    return create_role(db, data)


@router.put("/{role_id}", response_model=RoleResponse)
def update(role_id: int, data: RoleUpdate, db: Session = Depends(get_db)):
    return update_role(db, role_id, data)


@router.delete("/{role_id}", status_code=204)
def delete(role_id: int, db: Session = Depends(get_db)):
    delete_role(db, role_id)


@router.post("/{role_id}/permissions", response_model=RoleResponse)
def assign(role_id: int, data: AssignPermissionsRequest, db: Session = Depends(get_db)):
    return assign_permissions(db, role_id, data.permission_ids)
