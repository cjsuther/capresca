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
        auth_url=data.auth_url,
        client_id=data.client_id,
        username=data.username,
        password_encrypted=encrypt_secret(data.password),
        scope=data.scope,
        service_url=data.service_url,
        is_active=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


@router.post("/test")
def test_config(data: CredentialCreate, db: Session = Depends(get_db)):
    token_url = f"{data.auth_url}/cas/oidc/accessToken"
    params = {}
    if data.scope:
        params["scope"] = data.scope

    payload = {
        "grant_type": "password",
        "username": data.username,
        "password": data.password,
        "client_id": data.client_id,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if data.service_url:
        headers["service"] = data.service_url

    try:
        resp = httpx.post(
            token_url,
            data=payload,
            params=params,
            headers=headers,
            timeout=15,
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
