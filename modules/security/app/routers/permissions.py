from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.permission import Permission

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionResponse(BaseModel):
    id: int
    module_id: int
    code: str
    description: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=List[PermissionResponse])
def list_permissions(db: Session = Depends(get_db)):
    return db.query(Permission).order_by(Permission.module_id, Permission.code).all()
