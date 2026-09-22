from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.group import (AssignGroupRolesRequest, AssignMembersRequest, GroupCreate, GroupResponse,
                               GroupUpdate)
from app.services.group_service import (assign_group_roles, assign_members, create_group, delete_group,
                                        get_groups, update_group)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=List[GroupResponse])
def list_groups(db: Session = Depends(get_db)):
    return get_groups(db)


@router.post("", response_model=GroupResponse, status_code=201)
def create(data: GroupCreate, db: Session = Depends(get_db)):
    return create_group(db, data)


@router.put("/{group_id}", response_model=GroupResponse)
def update(group_id: int, data: GroupUpdate, db: Session = Depends(get_db)):
    return update_group(db, group_id, data)


@router.delete("/{group_id}", status_code=204)
def delete(group_id: int, db: Session = Depends(get_db)):
    delete_group(db, group_id)


@router.post("/{group_id}/roles", response_model=GroupResponse)
def roles(group_id: int, data: AssignGroupRolesRequest, db: Session = Depends(get_db)):
    return assign_group_roles(db, group_id, data.role_ids)


@router.post("/{group_id}/users", response_model=GroupResponse)
def members(group_id: int, data: AssignMembersRequest, db: Session = Depends(get_db)):
    return assign_members(db, group_id, data.user_ids)
