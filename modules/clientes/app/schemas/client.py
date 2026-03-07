from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from app.models.client import ClientType


# ── Contactos ──────────────────────────────────────────────────
class ContactCreate(BaseModel):
    contact_type: str
    value: str
    label: Optional[str] = None
    is_primary: bool = False


class ContactResponse(BaseModel):
    id: int
    contact_type: str
    value: str
    label: Optional[str]
    is_primary: bool

    model_config = {"from_attributes": True}


# ── Notas ───────────────────────────────────────────────────────
class NoteCreate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: int
    user_id: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Persona humana ──────────────────────────────────────────────
class HumanProfileCreate(BaseModel):
    first_name: str
    last_name: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None


class HumanProfileResponse(BaseModel):
    first_name: str
    last_name: str
    document_type: Optional[str]
    document_number: Optional[str]
    birth_date: Optional[str]
    gender: Optional[str]
    nationality: Optional[str]

    model_config = {"from_attributes": True}


# ── Persona jurídica ────────────────────────────────────────────
class LegalProfileCreate(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    tax_id: Optional[str] = None
    tax_id_type: Optional[str] = None
    incorporation_date: Optional[str] = None
    legal_representative: Optional[str] = None
    industry_sector: Optional[str] = None


class LegalProfileResponse(BaseModel):
    legal_name: str
    trade_name: Optional[str]
    tax_id: Optional[str]
    tax_id_type: Optional[str]
    incorporation_date: Optional[str]
    legal_representative: Optional[str]
    industry_sector: Optional[str]

    model_config = {"from_attributes": True}


# ── Datos base del cliente ──────────────────────────────────────
class ClientBaseUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


# ── Creación completa ───────────────────────────────────────────
class HumanClientCreate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "AR"
    profile: HumanProfileCreate


class LegalClientCreate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "AR"
    profile: LegalProfileCreate


# ── Respuesta completa ──────────────────────────────────────────
class ClientResponse(BaseModel):
    id: int
    client_type: ClientType
    code: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    human_profile: Optional[HumanProfileResponse] = None
    legal_profile: Optional[LegalProfileResponse] = None
    contacts: List[ContactResponse] = []

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    data: List[ClientResponse]
    total: int
    page: int
    per_page: int


# ── Miembros de persona jurídica ────────────────────────────────
class MemberCreate(BaseModel):
    human_client_id: int
    role: Optional[str] = None


class MemberResponse(BaseModel):
    id: int
    human_client_id: int
    role: Optional[str]
    created_at: datetime
    human_client: ClientResponse

    model_config = {"from_attributes": True}
