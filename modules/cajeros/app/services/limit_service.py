from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.limit import UserLimit
from app.schemas.limit import LimitUpdate


def get_my_limit(db: Session, user_id: int) -> UserLimit:
    limit = db.query(UserLimit).filter(UserLimit.user_id == user_id).first()
    if not limit:
        # Crear límite por defecto
        limit = UserLimit(user_id=user_id, daily_limit=0, per_transaction_limit=0)
        db.add(limit)
        db.commit()
        db.refresh(limit)
    return limit


def get_limit_by_user(db: Session, user_id: int) -> UserLimit:
    return get_my_limit(db, user_id)


def update_limit(db: Session, user_id: int, data: LimitUpdate) -> UserLimit:
    limit = get_my_limit(db, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(limit, field, value)
    db.commit()
    db.refresh(limit)
    return limit
