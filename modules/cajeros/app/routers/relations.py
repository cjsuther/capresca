from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.relation import RelationCreate, RelationResponse
from app.services.relation_service import get_relations, create_relation, delete_relation

router = APIRouter(prefix="/relations", tags=["relations"])


@router.get("", response_model=List[RelationResponse])
def list_relations(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_relations(db, user_id)


@router.post("", response_model=RelationResponse, status_code=201)
def create(data: RelationCreate, db: Session = Depends(get_db)):
    return create_relation(db, data)


@router.delete("/{relation_id}", status_code=204)
def delete(relation_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    delete_relation(db, relation_id, user_id)
