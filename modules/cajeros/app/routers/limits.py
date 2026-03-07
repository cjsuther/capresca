from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.limit import LimitResponse, LimitUpdate
from app.services.limit_service import get_my_limit, get_limit_by_user, update_limit

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("", response_model=LimitResponse)
def my_limit(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_my_limit(db, user_id)


@router.get("/{target_user_id}", response_model=LimitResponse)
def user_limit(target_user_id: int, db: Session = Depends(get_db)):
    return get_limit_by_user(db, target_user_id)


@router.put("/{target_user_id}", response_model=LimitResponse)
def update(target_user_id: int, data: LimitUpdate, db: Session = Depends(get_db)):
    return update_limit(db, target_user_id, data)
