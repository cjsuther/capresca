"""
Endpoints internos — accesibles solo desde la red Docker interna (proxy).
No deben exponerse al exterior (nginx bloquea /internal/*).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.permissions_service import get_user_permissions, get_user_modules
from app.services.auth_service import decode_token, is_token_blacklisted

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/permissions/{user_id}")
def user_permissions(user_id: int, db: Session = Depends(get_db)):
    return get_user_permissions(db, user_id)


@router.get("/modules/{user_id}")
def user_modules(user_id: int, db: Session = Depends(get_db)):
    return {"modules": get_user_modules(db, user_id)}


@router.get("/validate-token")
def validate_token(token: str, db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    jti = payload.get("jti")
    if jti and is_token_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    return {
        "valid": True,
        "user_id": int(payload["sub"]),
        "username": payload.get("username"),
        "exp": payload.get("exp"),
    }
