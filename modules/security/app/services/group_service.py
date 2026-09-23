from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.group import Group
from app.models.role import Role
from app.models.user import User
from app.schemas.group import GroupCreate, GroupUpdate


def get_groups(db: Session):
    return db.query(Group).order_by(Group.name).all()


def get_group(db: Session, group_id: int) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return group


def _nombre_libre(db: Session, name: str, excepto: int | None = None) -> None:
    q = db.query(Group).filter(Group.name == name)
    if excepto is not None:
        q = q.filter(Group.id != excepto)
    if q.first():
        raise HTTPException(status_code=400, detail="El nombre de grupo ya existe")


def create_group(db: Session, data: GroupCreate) -> Group:
    _nombre_libre(db, data.name)
    group = Group(**data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(db: Session, group_id: int, data: GroupUpdate) -> Group:
    group = get_group(db, group_id)
    cambios = data.model_dump(exclude_none=True)
    if "name" in cambios:
        _nombre_libre(db, cambios["name"], excepto=group.id)
    for field, value in cambios.items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group_id: int) -> None:
    """Borrar el grupo quita a sus integrantes los roles que heredaban de él (no los propios)."""
    db.delete(get_group(db, group_id))
    db.commit()


def assign_group_roles(db: Session, group_id: int, role_ids: list[int]) -> Group:
    group = get_group(db, group_id)
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=400, detail="Uno o más roles no encontrados")
    group.roles = roles
    db.commit()
    db.refresh(group)
    return group


def assign_members(db: Session, group_id: int, user_ids: list[int]) -> Group:
    group = get_group(db, group_id)
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    if len(users) != len(set(user_ids)):
        raise HTTPException(status_code=400, detail="Uno o más usuarios no encontrados")
    group.users = users
    db.commit()
    db.refresh(group)
    return group


def assign_user_groups(db: Session, user: User, group_ids: list[int]) -> User:
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    if len(groups) != len(set(group_ids)):
        raise HTTPException(status_code=400, detail="Uno o más grupos no encontrados")
    user.groups = groups
    db.commit()
    db.refresh(user)
    return user
