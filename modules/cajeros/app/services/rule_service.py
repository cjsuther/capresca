from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.authorization_rule import AuthorizationRule
from app.schemas.rules import RuleCreate


def get_rules(db: Session, cajero_filter: int | None = None, currency: str | None = None):
    q = db.query(AuthorizationRule).filter(AuthorizationRule.is_active == True)
    if cajero_filter:
        q = q.filter(AuthorizationRule.cajero_user_id == cajero_filter)
    if currency:
        q = q.filter(AuthorizationRule.currency == currency)
    return q.order_by(AuthorizationRule.created_at.desc()).all()


def create_rule(db: Session, data: RuleCreate, created_by: int) -> AuthorizationRule:
    rule = AuthorizationRule(**data.model_dump(), created_by=created_by)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int, user_id: int) -> None:
    rule = db.query(AuthorizationRule).filter(AuthorizationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    rule.is_active = False
    db.commit()
