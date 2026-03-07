from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.schemas.client import (
    HumanClientCreate, LegalClientCreate, ClientBaseUpdate,
    HumanProfileCreate, LegalProfileCreate,
    ContactCreate, ContactResponse,
    NoteCreate, NoteResponse,
    ClientResponse, ClientListResponse,
    MemberCreate, MemberResponse,
)
from app.services.client_service import (
    list_clients, get_client,
    create_human_client, create_legal_client,
    update_client_base, update_human_profile, update_legal_profile,
    deactivate_client,
    add_contact, remove_contact,
    add_note, get_notes,
    get_members, add_member, remove_member,
)

router = APIRouter(tags=["clients"])


@router.get("", response_model=ClientListResponse)
def list_all(
    client_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    clients, total = list_clients(db, client_type, search, city, page, per_page)
    return ClientListResponse(data=clients, total=total, page=page, per_page=per_page)


@router.get("/search", response_model=ClientListResponse)
def search(
    q: str = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    db: Session = Depends(get_db),
):
    clients, total = list_clients(db, search=q, page=page, per_page=per_page)
    return ClientListResponse(data=clients, total=total, page=page, per_page=per_page)


@router.post("/human", response_model=ClientResponse, status_code=201)
def create_human(
    data: HumanClientCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return create_human_client(db, data, user_id)


@router.post("/legal", response_model=ClientResponse, status_code=201)
def create_legal(
    data: LegalClientCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return create_legal_client(db, data, user_id)


@router.get("/{client_id}", response_model=ClientResponse)
def detail(client_id: int, db: Session = Depends(get_db)):
    return get_client(db, client_id)


@router.put("/{client_id}", response_model=ClientResponse)
def update_base(client_id: int, data: ClientBaseUpdate, db: Session = Depends(get_db)):
    return update_client_base(db, client_id, data)


@router.put("/{client_id}/human", response_model=ClientResponse)
def update_human(client_id: int, data: HumanProfileCreate, db: Session = Depends(get_db)):
    return update_human_profile(db, client_id, data.model_dump(exclude_none=True))


@router.put("/{client_id}/legal", response_model=ClientResponse)
def update_legal(client_id: int, data: LegalProfileCreate, db: Session = Depends(get_db)):
    return update_legal_profile(db, client_id, data.model_dump(exclude_none=True))


@router.delete("/{client_id}", response_model=ClientResponse)
def deactivate(client_id: int, db: Session = Depends(get_db)):
    return deactivate_client(db, client_id)


# ── Contactos ───────────────────────────────────────────────────
@router.get("/{client_id}/contacts", response_model=List[ContactResponse])
def list_contacts(client_id: int, db: Session = Depends(get_db)):
    client = get_client(db, client_id)
    return client.contacts


@router.post("/{client_id}/contacts", response_model=ContactResponse, status_code=201)
def create_contact(client_id: int, data: ContactCreate, db: Session = Depends(get_db)):
    return add_contact(db, client_id, data)


@router.delete("/{client_id}/contacts/{contact_id}", status_code=204)
def delete_contact(client_id: int, contact_id: int, db: Session = Depends(get_db)):
    remove_contact(db, client_id, contact_id)


# ── Notas ────────────────────────────────────────────────────────
@router.get("/{client_id}/notes", response_model=List[NoteResponse])
def list_notes(client_id: int, db: Session = Depends(get_db)):
    return get_notes(db, client_id)


@router.post("/{client_id}/notes", response_model=NoteResponse, status_code=201)
def create_note(
    client_id: int,
    data: NoteCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return add_note(db, client_id, user_id, data)


# ── Miembros ─────────────────────────────────────────────────────
@router.get("/{client_id}/members", response_model=List[MemberResponse])
def list_members(client_id: int, db: Session = Depends(get_db)):
    return get_members(db, client_id)


@router.post("/{client_id}/members", response_model=MemberResponse, status_code=201)
def create_member(client_id: int, data: MemberCreate, db: Session = Depends(get_db)):
    return add_member(db, client_id, data)


@router.delete("/{client_id}/members/{member_id}", status_code=204)
def delete_member(client_id: int, member_id: int, db: Session = Depends(get_db)):
    remove_member(db, client_id, member_id)
