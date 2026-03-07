from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.role import Role
from app.models.permission import Permission
from app.schemas.role import RoleCreate, RoleUpdate


def get_roles(db: Session):
    return db.query(Role).all()


def get_role(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    return role


def create_role(db: Session, data: RoleCreate) -> Role:
    if db.query(Role).filter(Role.name == data.name).first():
        raise HTTPException(status_code=400, detail="El nombre de rol ya existe")
    role = Role(**data.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role_id: int, data: RoleUpdate) -> Role:
    role = get_role(db, role_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: int) -> None:
    role = get_role(db, role_id)
    db.delete(role)
    db.commit()


def assign_permissions(db: Session, role_id: int, permission_ids: list[int]) -> Role:
    role = get_role(db, role_id)
    perms = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
    if len(perms) != len(permission_ids):
        raise HTTPException(status_code=400, detail="Uno o más permisos no encontrados")
    role.permissions = perms
    db.commit()
    db.refresh(role)
    return role
