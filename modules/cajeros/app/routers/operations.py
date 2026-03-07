from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.request import OperationResponse
from app.services.request_service import get_operations

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=List[OperationResponse])
def list_operations(db: Session = Depends(get_db)):
    return get_operations(db)
