from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.client import Client, LegalClient, ClientCbu
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
