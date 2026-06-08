from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import httpx

from app.db.session import get_db
from app.config import encrypt_secret, decrypt_secret
from app.models.credentials import InterbankingCredential
from app.models.tokens import InterbankingToken
from app.schemas.credentials import CredentialCreate, CredentialResponse, TokenStatusResponse
from app.scopes import SCOPE_TO_GRANT, INFO_FINANCIERA, grant_for
from app.services import token_manager

router = APIRouter(tags=["config"])


def _to_response(cred: InterbankingCredential) -> dict:
    return {
        "id": cred.id,
        "name": cred.name,
        "base_url": cred.base_url,
        "auth_url": cred.auth_url,
        "client_id": cred.client_id,
        "username": cred.username,
        "service_url": cred.service_url,
        "customer_id": cred.customer_id,
        "has_client_secret": bool(cred.client_secret_encrypted),
        "has_password": bool(cred.password_encrypted),
        "is_active": cred.is_active,
        "created_at": cred.created_at,
        "updated_at": cred.updated_at,
    }


@router.get("", response_model=CredentialResponse)
def get_config(db: Session = Depends(get_db)):
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=404, detail="No hay configuración activa")
    return _to_response(cred)


@router.post("", response_model=CredentialResponse)
def save_config(data: CredentialCreate, db: Session = Depends(get_db)):
    existing = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()

    # client_secret (info-financiera): si llega vacío preservar el guardado
    if data.client_secret:
        client_secret_encrypted = encrypt_secret(data.client_secret)
    elif existing and existing.client_secret_encrypted and existing.client_id == data.client_id:
        client_secret_encrypted = existing.client_secret_encrypted
    else:
        client_secret_encrypted = None

    # password (transferencias-confeccion): idem
    if data.password:
        password_encrypted = encrypt_secret(data.password)
    elif existing and existing.password_encrypted and existing.username == (data.username or None):
        password_encrypted = existing.password_encrypted
    else:
        password_encrypted = None

    # Desactivar credenciales previas y todos sus tokens (cambiaron secretos)
    db.query(InterbankingCredential).update({"is_active": False})
    db.query(InterbankingToken).filter(InterbankingToken.is_active == True).update({"is_active": False})

    cred = InterbankingCredential(
        name=data.name,
        base_url=data.base_url,
        auth_url=data.auth_url,
        client_id=data.client_id,
        client_secret_encrypted=client_secret_encrypted,
        username=data.username or None,
        password_encrypted=password_encrypted,
        service_url=data.service_url,
        customer_id=data.customer_id or None,
        is_active=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return _to_response(cred)


@router.post("/test")
def test_config(
    data: CredentialCreate,
    scope: str = Query(INFO_FINANCIERA, description="Scope a probar"),
    db: Session = Depends(get_db),
):
    if scope not in SCOPE_TO_GRANT:
        raise HTTPException(status_code=400, detail=f"Scope inválido: {scope}")

    # Si vino vacío, completar con lo guardado
    existing = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if existing and existing.client_id == data.client_id:
        if not data.client_secret and existing.client_secret_encrypted:
            data.client_secret = decrypt_secret(existing.client_secret_encrypted)
        if not data.password and existing.password_encrypted:
            data.password = decrypt_secret(existing.password_encrypted)
        if not data.username and existing.username:
            data.username = existing.username

    grant = grant_for(scope)
    if grant == "client_credentials":
        if not data.client_secret:
            return {"success": False, "error": "Falta client_secret para info-financiera"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": data.client_id,
            "client_secret": data.client_secret,
        }
    else:
        if not data.username or not data.password:
            return {"success": False, "error": "Faltan usuario/contraseña para transferencias-confeccion"}
        payload = {
            "grant_type": "password",
            "username": data.username,
            "password": data.password,
            "client_id": data.client_id,
        }

    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if data.service_url:
        headers["service"] = data.service_url

    try:
        resp = httpx.post(
            f"{data.auth_url}/cas/oidc/accessToken",
            data=payload,
            params={"scope": scope},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
        return {
            "success": True,
            "scope": scope,
            "token_preview": token_data.get("access_token", "")[:20] + "...",
            "expires_in": token_data.get("expires_in"),
        }
    except Exception as e:
        return {"success": False, "scope": scope, "error": str(e)}


@router.get("/token-status", response_model=TokenStatusResponse)
def token_status(db: Session = Depends(get_db)):
    return token_manager.get_token_status(db)
