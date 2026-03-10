from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.models.client import ClientCbu, Client
from app.schemas.cbu import ClientCbuCreate, ClientCbuUpdate, ClientCbuResponse

router = APIRouter(tags=["cbus"])


@router.get("/{client_id}/cbus", response_model=List[ClientCbuResponse])
def list_cbus(client_id: int, db: Session = Depends(get_db)):
    return db.query(ClientCbu).filter(
        ClientCbu.client_id == client_id,
        ClientCbu.is_active == True,
    ).all()


@router.post("/{client_id}/cbus", response_model=ClientCbuResponse, status_code=201)
def add_cbu(
    client_id: int,
    data: ClientCbuCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Check if CBU already registered
    existing = db.query(ClientCbu).filter(ClientCbu.cbu == data.cbu, ClientCbu.is_active == True).first()
    if existing:
        owner = db.query(Client).filter(Client.id == existing.client_id).first()
        name = ""
        if owner:
            if owner.legal_profile:
                name = owner.legal_profile.legal_name
            elif owner.human_profile:
                name = f"{owner.human_profile.first_name} {owner.human_profile.last_name}"
        raise HTTPException(400, f"CBU ya registrado en {name or f'cliente {existing.client_id}'}")

    cbu = ClientCbu(client_id=client_id, created_by=user_id, **data.model_dump())
    db.add(cbu)
    db.commit()
    db.refresh(cbu)
    return cbu


@router.put("/{client_id}/cbus/{cbu_id}", response_model=ClientCbuResponse)
def update_cbu(
    client_id: int,
    cbu_id: int,
    data: ClientCbuUpdate,
    db: Session = Depends(get_db),
):
    cbu = db.query(ClientCbu).filter(ClientCbu.id == cbu_id, ClientCbu.client_id == client_id).first()
    if not cbu:
        raise HTTPException(404, "CBU no encontrado")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(cbu, k, v)
    db.commit()
    db.refresh(cbu)
    return cbu


@router.delete("/{client_id}/cbus/{cbu_id}", status_code=204)
def delete_cbu(client_id: int, cbu_id: int, db: Session = Depends(get_db)):
    cbu = db.query(ClientCbu).filter(ClientCbu.id == cbu_id, ClientCbu.client_id == client_id).first()
    if not cbu:
        raise HTTPException(404, "CBU no encontrado")
    cbu.is_active = False
    db.commit()
