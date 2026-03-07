from sqlalchemy.orm import Session
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import hash_password, verify_password
from fastapi import HTTPException


def get_users(db: Session, page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    total = db.query(User).count()
    users = db.query(User).offset(offset).limit(per_page).all()
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
