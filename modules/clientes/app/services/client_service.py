import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.models.client import Client, HumanClient, LegalClient, ClientContact, ClientNote, ClientType, LegalClientMember
from app.schemas.client import (
    HumanClientCreate, LegalClientCreate, ClientBaseUpdate,
    ContactCreate, NoteCreate, MemberCreate
)


def _generate_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def list_clients(db: Session, client_type: str = None, search: str = None,
                 city: str = None, page: int = 1, per_page: int = 20):
    q = db.query(Client).filter(Client.is_active == True)

    if client_type:
        q = q.filter(Client.client_type == client_type.upper())
    if city:
        q = q.filter(Client.city.ilike(f"%{city}%"))
    if search:
        human_match = (
            db.query(Client.id)
            .join(HumanClient)
            .filter(
                or_(
                    HumanClient.first_name.ilike(f"%{search}%"),
                    HumanClient.last_name.ilike(f"%{search}%"),
                    HumanClient.document_number.ilike(f"%{search}%"),
                )
            ).subquery()
        )
        legal_match = (
            db.query(Client.id)
            .join(LegalClient)
            .filter(
                or_(
                    LegalClient.legal_name.ilike(f"%{search}%"),
                    LegalClient.trade_name.ilike(f"%{search}%"),
                    LegalClient.tax_id.ilike(f"%{search}%"),
                )
            ).subquery()
        )
        q = q.filter(
            or_(
                Client.email.ilike(f"%{search}%"),
                Client.id.in_(human_match),
                Client.id.in_(legal_match),
            )
        )

    total = q.count()
    clients = q.offset((page - 1) * per_page).limit(per_page).all()
    return clients, total


def get_client(db: Session, client_id: int) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


def create_human_client(db: Session, data: HumanClientCreate, user_id: int) -> Client:
    client = Client(
        client_type=ClientType.HUMAN,
        code=_generate_code("PH"),
        email=data.email,
        phone=data.phone,
        address=data.address,
        city=data.city,
        country=data.country,
        created_by_user_id=user_id,
    )
    db.add(client)
    db.flush()

    profile = HumanClient(client_id=client.id, **data.profile.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(client)
    return client


def create_legal_client(db: Session, data: LegalClientCreate, user_id: int) -> Client:
    client = Client(
        client_type=ClientType.LEGAL,
        code=_generate_code("PJ"),
        email=data.email,
        phone=data.phone,
        address=data.address,
        city=data.city,
        country=data.country,
        created_by_user_id=user_id,
    )
    db.add(client)
    db.flush()

    profile = LegalClient(client_id=client.id, **data.profile.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(client)
    return client


def update_client_base(db: Session, client_id: int, data: ClientBaseUpdate) -> Client:
    client = get_client(db, client_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


def update_human_profile(db: Session, client_id: int, data: dict) -> Client:
    client = get_client(db, client_id)
    if not client.human_profile:
        raise HTTPException(status_code=400, detail="El cliente no es persona humana")
    for field, value in data.items():
        if value is not None:
            setattr(client.human_profile, field, value)
    db.commit()
    db.refresh(client)
    return client


def update_legal_profile(db: Session, client_id: int, data: dict) -> Client:
    client = get_client(db, client_id)
    if not client.legal_profile:
        raise HTTPException(status_code=400, detail="El cliente no es persona jurídica")
    for field, value in data.items():
        if value is not None:
            setattr(client.legal_profile, field, value)
    db.commit()
    db.refresh(client)
    return client


def deactivate_client(db: Session, client_id: int) -> Client:
    client = get_client(db, client_id)
    client.is_active = False
    db.commit()
    db.refresh(client)
    return client


# ── Contactos ──────────────────────────────────────────────────
def add_contact(db: Session, client_id: int, data: ContactCreate) -> ClientContact:
    get_client(db, client_id)
    contact = ClientContact(client_id=client_id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def remove_contact(db: Session, client_id: int, contact_id: int):
    contact = db.query(ClientContact).filter(
        ClientContact.id == contact_id,
        ClientContact.client_id == client_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    db.delete(contact)
    db.commit()


# ── Notas ───────────────────────────────────────────────────────
def add_note(db: Session, client_id: int, user_id: int, data: NoteCreate) -> ClientNote:
    get_client(db, client_id)
    note = ClientNote(client_id=client_id, user_id=user_id, content=data.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_notes(db: Session, client_id: int):
    return db.query(ClientNote).filter(ClientNote.client_id == client_id).order_by(ClientNote.created_at.desc()).all()


# ── Miembros ─────────────────────────────────────────────────────
def get_members(db: Session, legal_client_id: int):
    client = get_client(db, legal_client_id)
    if client.client_type != ClientType.LEGAL:
        raise HTTPException(status_code=400, detail="El cliente no es persona jurídica")
    return db.query(LegalClientMember).filter(
        LegalClientMember.legal_client_id == legal_client_id
    ).all()


def add_member(db: Session, legal_client_id: int, data: MemberCreate) -> LegalClientMember:
    legal = get_client(db, legal_client_id)
    if legal.client_type != ClientType.LEGAL:
        raise HTTPException(status_code=400, detail="El cliente no es persona jurídica")
    human = get_client(db, data.human_client_id)
    if human.client_type != ClientType.HUMAN:
        raise HTTPException(status_code=400, detail="El miembro debe ser persona física")
    existing = db.query(LegalClientMember).filter(
        LegalClientMember.legal_client_id == legal_client_id,
        LegalClientMember.human_client_id == data.human_client_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="El miembro ya pertenece a esta persona jurídica")
    member = LegalClientMember(
        legal_client_id=legal_client_id,
        human_client_id=data.human_client_id,
        role=data.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, legal_client_id: int, member_id: int):
    member = db.query(LegalClientMember).filter(
        LegalClientMember.id == member_id,
        LegalClientMember.legal_client_id == legal_client_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    db.delete(member)
    db.commit()
