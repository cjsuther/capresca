from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.module import Module
from app.schemas.module import ModuleResponse

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("", response_model=List[ModuleResponse])
def list_modules(db: Session = Depends(get_db)):
    return db.query(Module).filter(Module.is_active == True).all()
