from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.client import Client, ClientType, ClientContact, HumanClient, LegalClient, ClientCbu
from app.services.client_service import _generate_code
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
                {"id": c.id, "cbu": c.cbu, "alias": c.alias, "bank_name": c.bank_name,
                 "account_type": c.account_type, "is_payment_account": c.is_payment_account}
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


@router.get("/internal/clientes/{client_id}/ficha")
def get_client_ficha(client_id: int, db: Session = Depends(get_db)):
    """
    Ficha de identidad completa de un cliente, para los modulos que mantienen un espejo local
    (Creditos). El padron vive aca: los modulos no guardan su propio maestro, espejan este.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return JSONResponse(content=None, status_code=200)
    return _ficha(client, db)


@router.post("/internal/clientes/buscar-por-documento")
def buscar_por_documento(payload: dict, db: Session = Depends(get_db)):
    """
    Resuelve documentos (DNI/CUIL/CUIT) a ids de cliente, en lote. Lo usa Creditos para enlazar
    sus creditos con el padron sin exponer busquedas al usuario final.
    """
    documentos = [str(d).strip() for d in (payload.get("documentos") or []) if str(d).strip()]
    if not documentos:
        return {"encontrados": {}}
    humanos = (
        db.query(HumanClient)
        .filter(HumanClient.document_number.in_(documentos))
        .all()
    )
    juridicos = (
        db.query(LegalClient)
        .filter(LegalClient.tax_id.in_(documentos))
        .all()
    )
    encontrados = {h.document_number: h.client_id for h in humanos if h.document_number}
    encontrados.update({j.tax_id: j.client_id for j in juridicos if j.tax_id})
    return {"encontrados": encontrados}


def _ficha(client: Client, db: Session) -> dict:
    h = client.human_profile
    l = client.legal_profile
    cbu = (
        db.query(ClientCbu)
        .filter(ClientCbu.client_id == client.id, ClientCbu.is_active == True)
        .order_by(ClientCbu.is_payment_account.desc(), ClientCbu.id)
        .first()
    )
    return {
        "client_id": client.id,
        "codigo": client.code,
        "tipo": client.client_type.value,
        "nombre": _get_client_display_name(client),
        "apellido": h.last_name if h else None,
        "nombres": h.first_name if h else None,
        "razon_social": l.legal_name if l else None,
        "tipo_documento": (h.document_type if h else l.tax_id_type if l else None),
        "documento": (h.document_number if h else l.tax_id if l else None),
        "fecha_nacimiento": h.birth_date if h else None,
        "sexo": h.gender if h else None,
        "email": client.email,
        "telefono": client.phone,
        "domicilio": client.address,
        "localidad": client.city,
        "cbu": cbu.cbu if cbu else None,
        "activo": client.is_active,
    }


@router.post("/internal/clientes/importar")
def importar_personas(payload: dict, db: Session = Depends(get_db)):
    """
    Alta/actualizacion de personas fisicas en lote, identificadas por documento (DNI/CUIL).
    La usa la migracion del maestro de CCyPP: el padron de clientes vive en este modulo, y los
    modulos que necesitan datos del cliente (Creditos) espejan estos registros.

    Es idempotente por documento: si la persona ya existe, completa los campos vacios y devuelve
    su id; nunca duplica.
    """
    personas = payload.get("personas") or []
    creados, existentes, sin_documento = {}, {}, 0

    for p in personas:
        documento = str(p.get("documento") or "").strip()
        if not documento:
            sin_documento += 1
            continue

        perfil = (
            db.query(HumanClient)
            .filter(HumanClient.document_number == documento)
            .first()
        )
        if perfil:
            cliente = db.query(Client).filter(Client.id == perfil.client_id).first()
            # Completa sólo lo que falte: el padrón es la fuente de verdad y no se pisa.
            for campo, valor in (("email", p.get("email")), ("phone", p.get("telefono")),
                                 ("address", p.get("domicilio")), ("city", p.get("localidad"))):
                if valor and cliente is not None and not getattr(cliente, campo):
                    setattr(cliente, campo, valor)
            if p.get("apellido") and not perfil.last_name:
                perfil.last_name = p["apellido"]
            if p.get("nombres") and not perfil.first_name:
                perfil.first_name = p["nombres"]
            existentes[documento] = perfil.client_id
            continue

        cliente = Client(
            client_type=ClientType.HUMAN,
            code=_generate_code("PH"),
            email=p.get("email") or None,
            phone=p.get("telefono") or None,
            address=p.get("domicilio") or None,
            city=p.get("localidad") or None,
            country="AR",
            is_active=not p.get("baja", False),
            created_by_user_id=p.get("usuario_id"),
        )
        db.add(cliente)
        db.flush()
        db.add(HumanClient(
            client_id=cliente.id,
            first_name=(p.get("nombres") or "").strip() or "-",
            last_name=(p.get("apellido") or "").strip() or (p.get("nombre") or "").strip() or "-",
            document_type=p.get("tipo_documento") or "DNI",
            document_number=documento,
            birth_date=p.get("fecha_nacimiento"),
            gender=p.get("sexo"),
        ))
        creados[documento] = cliente.id

    db.commit()
    return {
        "creados": creados,
        "existentes": existentes,
        "sin_documento": sin_documento,
        "total": len(creados) + len(existentes),
    }
