from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.rules import RuleCreate, RuleResponse
from app.services import rule_service

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=List[RuleResponse])
def list_rules(
    cajero: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return rule_service.get_rules(db, cajero, currency)


@router.post("", response_model=RuleResponse, status_code=201)
def create_rule(
    data: RuleCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return rule_service.create_rule(db, data, user_id)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rule_service.delete_rule(db, rule_id, user_id)
