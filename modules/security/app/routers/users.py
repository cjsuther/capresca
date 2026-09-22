from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    AssignRolesRequest, AssignGroupsRequest, AdminChangePasswordRequest, ChangeOwnPasswordRequest,
)
from app.services.user_service import (
    get_users, get_user, create_user, update_user, deactivate_user,
    assign_roles, admin_change_password, change_own_password,
)
from app.services.group_service import assign_user_groups
from app.services.permissions_service import get_user_permissions

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    users, total = get_users(db, page, per_page)
    return UserListResponse(data=users, total=total, page=page, per_page=per_page)


@router.post("", response_model=UserResponse, status_code=201)
def create(data: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, data)


@router.get("/{user_id}", response_model=UserResponse)
def detail(user_id: int, db: Session = Depends(get_db)):
    return get_user(db, user_id)


@router.put("/{user_id}", response_model=UserResponse)
def update(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    return update_user(db, user_id, data)


@router.delete("/{user_id}", response_model=UserResponse)
def deactivate(user_id: int, db: Session = Depends(get_db)):
    return deactivate_user(db, user_id)


@router.post("/{user_id}/roles", response_model=UserResponse)
def assign(user_id: int, data: AssignRolesRequest, db: Session = Depends(get_db)):
    return assign_roles(db, user_id, data.role_ids)


@router.post("/{user_id}/groups", response_model=UserResponse)
def assign_groups(user_id: int, data: AssignGroupsRequest, db: Session = Depends(get_db)):
    return assign_user_groups(db, get_user(db, user_id), data.group_ids)


@router.get("/{user_id}/effective-permissions")
def effective_permissions(user_id: int, db: Session = Depends(get_db)):
    """Lo que el usuario puede hacer hoy: roles propios + heredados de sus grupos + overrides directos."""
    get_user(db, user_id)
    return get_user_permissions(db, user_id)


# ── Cambio de contraseña propio ──────────────────────────────────
@router.put("/me/password", status_code=204)
def change_my_password(
    data: ChangeOwnPasswordRequest,
    x_user_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="No autenticado")
    change_own_password(db, int(x_user_id), data.current_password, data.new_password)


# ── Cambio de contraseña por admin ───────────────────────────────
@router.put("/{user_id}/password", status_code=204)
def admin_set_password(user_id: int, data: AdminChangePasswordRequest, db: Session = Depends(get_db)):
    admin_change_password(db, user_id, data.new_password)
