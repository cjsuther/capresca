from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo, PermissionsPayload
from app.services.auth_service import (
    authenticate_user, create_access_token, decode_token, blacklist_token, is_token_blacklisted
)
from app.services.permissions_service import get_user_permissions

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token(user.id, user.username)
    permissions = get_user_permissions(db, user.id)

    return LoginResponse(
        access_token=token,
        user=UserInfo(id=user.id, username=user.username, full_name=user.full_name),
        permissions=PermissionsPayload(**permissions),
    )


@router.post("/logout")
def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    jti = payload.get("jti")
    if jti and not is_token_blacklisted(db, jti):
        exp = payload.get("exp")
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc) if exp else datetime.now(timezone.utc)
        blacklist_token(db, jti, payload["sub"], expires_at)

    return {"message": "Sesión cerrada exitosamente"}


@router.post("/refresh")
def refresh_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    jti = payload.get("jti")
    if jti and is_token_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    new_token = create_access_token(int(payload["sub"]), payload["username"])
    return {"access_token": new_token, "token_type": "bearer"}
