from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.group import Group
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import hash_password, verify_password
from fastapi import HTTPException


def get_users(db: Session, page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    total = db.query(User).count()
    users = db.query(User).order_by(User.username).offset(offset).limit(per_page).all()
    return users, total


# Columnas por las que se puede ordenar el listado paginado. "nombre" cae al username si no hay
# nombre completo, así nadie queda al final por no tenerlo cargado.
ORDENES = {
    "nombre": lambda: func.lower(func.coalesce(func.nullif(User.full_name, ""), User.username)),
    "username": lambda: func.lower(User.username),
    "email": lambda: func.lower(User.email),
    "estado": lambda: User.is_active,
    "creado": lambda: User.created_at,
}


def _like(texto: str) -> str:
    """Patrón LIKE literal: `%` y `_` tipeados por el usuario no son comodines."""
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def search_users(
    db: Session,
    *,
    q: Optional[str] = None,
    role_id: Optional[int] = None,
    group_id: Optional[int] = None,
    estado: Optional[str] = None,
    mfa: Optional[bool] = None,
    sort: str = "nombre",
    order: str = "asc",
    page: int = 1,
    page_size: int = 25,
):
    """Listado de usuarios filtrado, ordenado y paginado del lado del servidor.

    - `q`: texto libre sobre usuario, email y nombre completo (sin distinguir mayúsculas).
    - `role_id`: usuarios que tienen el rol, asignado directo o heredado de un grupo activo
      (lo mismo que muestra la columna Roles de la pantalla).
    - `group_id`: integrantes del grupo.
    - `estado`: "activo" | "inactivo".
    - `mfa`: con (True) o sin (False) doble factor activo.
    """
    query = db.query(User)
    if q and q.strip():
        patron = _like(q.strip())
        query = query.filter(or_(
            User.username.ilike(patron, escape="\\"),
            User.email.ilike(patron, escape="\\"),
            User.full_name.ilike(patron, escape="\\"),
        ))
    if role_id is not None:
        query = query.filter(or_(
            User.roles.any(Role.id == role_id),
            User.groups.any((Group.is_active.is_(True)) & Group.roles.any(Role.id == role_id)),
        ))
    if group_id is not None:
        query = query.filter(User.groups.any(Group.id == group_id))
    if estado is not None:
        query = query.filter(User.is_active.is_(estado == "activo"))
    if mfa is not None:
        query = query.filter(User.totp_activo.is_(mfa))

    total = query.count()
    columna = ORDENES[sort]()
    columna = columna.desc() if order == "desc" else columna.asc()
    users = (
        query.options(selectinload(User.roles), selectinload(User.groups).selectinload(Group.roles))
        .order_by(columna, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return users, total


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def create_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="El username ya existe")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="El email ya existe")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int) -> User:
    user = get_user(db, user_id)
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


def admin_change_password(db: Session, user_id: int, new_password: str) -> None:
    user = get_user(db, user_id)
    user.hashed_password = hash_password(new_password)
    db.commit()


def change_own_password(db: Session, user_id: int, current_password: str, new_password: str) -> None:
    user = get_user(db, user_id)
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    user.hashed_password = hash_password(new_password)
    db.commit()


def assign_roles(db: Session, user_id: int, role_ids: list[int]) -> User:
    user = get_user(db, user_id)
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    if len(roles) != len(role_ids):
        raise HTTPException(status_code=400, detail="Uno o más roles no encontrados")
    user.roles = roles
    db.commit()
    db.refresh(user)
    return user
