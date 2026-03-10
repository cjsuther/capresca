import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import decrypt_secret
from app.models.credentials import InterbankingCredential
from app.models.tokens import InterbankingToken
from app.services import audit_service

TOKEN_REFRESH_MARGIN_MINUTES = 5


def get_active_credential(db: Session) -> InterbankingCredential:
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=503, detail="No hay credenciales de Interbanking configuradas")
    return cred


def get_valid_token(db: Session, user_id: int = 0) -> tuple[str, int]:
    """Retorna (access_token, credential_id). Renueva el token si es necesario."""
    cred = get_active_credential(db)
    threshold = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_REFRESH_MARGIN_MINUTES)

    token = (
        db.query(InterbankingToken)
        .filter(
            InterbankingToken.credential_id == cred.id,
            InterbankingToken.is_active == True,
            InterbankingToken.expires_at > threshold,
        )
        .first()
    )

    if token:
        return token.access_token, cred.id

    return _refresh_token(db, cred, user_id)


def _refresh_token(db: Session, cred: InterbankingCredential, user_id: int) -> tuple[str, int]:
    password = decrypt_secret(cred.password_encrypted)

    # Construir URL del token endpoint con scope como query param
    token_url = f"{cred.auth_url}/cas/oidc/accessToken"
    params = {}
    if cred.scope:
        params["scope"] = cred.scope

    payload = {
        "grant_type": "password",
        "username": cred.username,
        "password": password,
        "client_id": cred.client_id,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if cred.service_url:
        headers["service"] = cred.service_url

    start = time.time()
    success = False
    error_msg = None
    response_data = None
    status_code = None

    try:
        resp = httpx.post(
            token_url,
            data=payload,
            params=params,
            headers=headers,
            timeout=15,
        )
        status_code = resp.status_code
        resp.raise_for_status()
        response_data = resp.json()
        success = True
    except Exception as e:
        error_msg = str(e)
    finally:
        duration_ms = int((time.time() - start) * 1000)
        audit_service.log(
            db=db,
            user_id=user_id,
            operation="OBTENER_TOKEN",
            method="POST",
            endpoint="/cas/oidc/accessToken",
            request_payload={"client_id": cred.client_id, "grant_type": "password", "username": cred.username},
            response_status=status_code,
            response_payload={"token_type": response_data.get("token_type")} if response_data else None,
            duration_ms=duration_ms,
            success=success,
            credential_id=cred.id,
            error_message=error_msg,
        )

    if not success:
        raise HTTPException(status_code=502, detail=f"Error al obtener token de Interbanking: {error_msg}")

    # Desactivar tokens anteriores
    db.query(InterbankingToken).filter(
        InterbankingToken.credential_id == cred.id,
        InterbankingToken.is_active == True,
    ).update({"is_active": False})

    expires_in = response_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    new_token = InterbankingToken(
        credential_id=cred.id,
        access_token=response_data["access_token"],
        token_type=response_data.get("token_type", "Bearer"),
        expires_at=expires_at,
        is_active=True,
    )
    db.add(new_token)
    db.commit()

    return new_token.access_token, cred.id


def get_token_status(db: Session) -> dict:
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        return {"has_active_token": False}

    token = (
        db.query(InterbankingToken)
        .filter(InterbankingToken.credential_id == cred.id, InterbankingToken.is_active == True)
        .first()
    )
    if not token:
        return {"has_active_token": False}

    now = datetime.now(timezone.utc)
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    minutes_remaining = int((expires_at - now).total_seconds() / 60)
    return {
        "has_active_token": minutes_remaining > 0,
        "expires_at": expires_at,
        "minutes_remaining": max(0, minutes_remaining),
    }
