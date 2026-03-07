from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.config import encrypt_secret, decrypt_secret
from app.models.credentials import InterbankingCredential
from app.schemas.credentials import CredentialCreate, CredentialResponse, TokenStatusResponse
from app.services import token_manager

router = APIRouter(tags=["config"])


@router.get("", response_model=CredentialResponse)
def get_config(db: Session = Depends(get_db)):
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=404, detail="No hay configuración activa")
    return cred


@router.post("", response_model=CredentialResponse)
def save_config(data: CredentialCreate, db: Session = Depends(get_db)):
    # Desactivar credenciales previas
    db.query(InterbankingCredential).update({"is_active": False})

    cred = InterbankingCredential(
        name=data.name,
        base_url=data.base_url,
        client_id=data.client_id,
        client_secret_encrypted=encrypt_secret(data.client_secret),
        is_active=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


@router.post("/test")
def test_config(data: CredentialCreate, db: Session = Depends(get_db)):
    try:
        resp = httpx.post(
            f"{data.base_url}/oauth/token",
            data={"grant_type": "client_credentials", "client_id": data.client_id},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
        return {
            "success": True,
            "token_preview": token_data.get("access_token", "")[:20] + "...",
            "expires_in": token_data.get("expires_in"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/token-status", response_model=TokenStatusResponse)
def token_status(db: Session = Depends(get_db)):
    return token_manager.get_token_status(db)
