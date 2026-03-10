from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.relation import AuthorizationRelation
from app.schemas.relation import RelationCreate


def get_relations(db: Session, user_id: int):
    return (
        db.query(AuthorizationRelation)
        .filter(
            (AuthorizationRelation.cajero_user_id == user_id) |
            (AuthorizationRelation.authorizer_user_id == user_id),
            AuthorizationRelation.is_active == True,
        )
        .all()
    )


def create_relation(db: Session, data: RelationCreate) -> AuthorizationRelation:
    existing = db.query(AuthorizationRelation).filter(
        AuthorizationRelation.cajero_user_id == data.cajero_user_id,
        AuthorizationRelation.amount_threshold == data.amount_threshold,
        AuthorizationRelation.currency == data.currency,
        AuthorizationRelation.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una relación con ese umbral para este cajero")

    rel = AuthorizationRelation(**data.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def delete_relation(db: Session, relation_id: int, user_id: int):
    rel = db.query(AuthorizationRelation).filter(AuthorizationRelation.id == relation_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relación no encontrada")
    # Solo el cajero o autorizador involucrado puede eliminarla
    if rel.cajero_user_id != user_id and rel.authorizer_user_id != user_id:
        raise HTTPException(status_code=403, detail="No tiene permiso para eliminar esta relación")
    rel.is_active = False
    db.commit()
