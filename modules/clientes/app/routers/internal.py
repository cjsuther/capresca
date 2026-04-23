from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.client import Client, ClientType, ClientContact, HumanClient, LegalClient, ClientCbu
from app.schemas.cbu import ClientCbuResponse

router = APIRouter(tags=["internal"])


@router.get("/internal/clientes/agencies")
def list_agencies(db: Session = Depends(get_db)):
    legal_clients = (
        db.query(LegalClient)
        .join(Client, Client.id == LegalClient.client_id)
        .filter(
            LegalClient.agency_number != None,
            Client.is_active == True,
        )
        .all()
    )
    result = []
    for lc in legal_clients:
        cbus = db.query(ClientCbu).filter(
            ClientCbu.client_id == lc.client_id,
            ClientCbu.is_active == True,
        ).all()
        result.append({
            "client_id": lc.client_id,
            "agency_number": lc.agency_number,
            "legal_name": lc.legal_name,
            "tax_id": lc.tax_id,
            "cbus": [
                {"id": c.id, "cbu": c.cbu, "alias": c.alias, "bank_name": c.bank_name, "account_type": c.account_type}
                for c in cbus
            ],
        })
    return result


@router.get("/internal/clientes/cbu/{cbu}")
def get_by_cbu(cbu: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    cbu_entry = db.query(ClientCbu).filter(ClientCbu.cbu == cbu, ClientCbu.is_active == True).first()
    if not cbu_entry:
        raise HTTPException(404, "CBU no registrado")
    lc = db.query(LegalClient).filter(LegalClient.client_id == cbu_entry.client_id).first()
    return {
        "client_id": cbu_entry.client_id,
        "agency_number": lc.agency_number if lc else None,
        "legal_name": lc.legal_name if lc else None,
    }


def _get_client_display_name(client: Client) -> str:
    if client.client_type == ClientType.LEGAL and client.legal_profile:
        return client.legal_profile.legal_name
    elif client.client_type == ClientType.HUMAN and client.human_profile:
        return f"{client.human_profile.first_name} {client.human_profile.last_name}"
    return client.code


@router.get("/internal/clientes/by-phone/{phone}")
def get_by_phone(phone: str, db: Session = Depends(get_db)):
    """Busca un cliente por numero de telefono (en clients.phone o client_contacts)."""
    # Search in main phone field
    client = db.query(Client).filter(Client.phone == phone, Client.is_active == True).first()

    if not client:
        # Search in contacts table
        contact = (
            db.query(ClientContact)
            .filter(
                ClientContact.value == phone,
                ClientContact.contact_type.in_(["whatsapp", "celular", "phone"]),
            )
            .first()
        )
        if contact:
            client = db.query(Client).filter(Client.id == contact.client_id, Client.is_active == True).first()

    if not client:
        return JSONResponse(content=None, status_code=200)

    return {
        "client_id": client.id,
        "client_name": _get_client_display_name(client),
        "client_type": client.client_type.value,
        "phone": phone,
    }


@router.get("/internal/clientes/{client_id}")
def get_client_internal(client_id: int, db: Session = Depends(get_db)):
    """Retorna datos basicos de un cliente por ID (uso interno entre modulos)."""
    client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
    if not client:
        return JSONResponse(content=None, status_code=200)

    return {
        "client_id": client.id,
        "client_name": _get_client_display_name(client),
        "client_type": client.client_type.value,
        "phone": client.phone,
        "email": client.email,
    }


@router.get("/internal/clientes/{client_id}/phones")
def get_client_phones(client_id: int, db: Session = Depends(get_db)):
    """Retorna los telefonos disponibles de un cliente."""
    client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
    if not client:
        return []

    phones = []
    if client.phone:
        phones.append({"phone": client.phone, "type": "principal", "label": "Principal"})

    contacts = (
        db.query(ClientContact)
        .filter(
            ClientContact.client_id == client_id,
            ClientContact.contact_type.in_(["whatsapp", "celular", "phone"]),
        )
        .all()
    )
    for c in contacts:
        phones.append({"phone": c.value, "type": c.contact_type, "label": c.label or c.contact_type})

    return phones
