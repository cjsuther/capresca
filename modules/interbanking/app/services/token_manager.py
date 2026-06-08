import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import decrypt_secret
from app.models.credentials import InterbankingCredential
from app.models.tokens import InterbankingToken
from app.scopes import SCOPE_TO_GRANT, grant_for
from app.services import audit_service

TOKEN_REFRESH_MARGIN_MINUTES = 5


def get_active_credential(db: Session) -> InterbankingCredential:
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=503, detail="No hay credenciales de Interbanking configuradas")
    return cred


def get_valid_token(db: Session, scope: str, user_id: int = 0) -> tuple[str, int]:
    """Retorna (access_token, credential_id) para el scope dado. Renueva si hace falta."""
    cred = get_active_credential(db)
    threshold = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_REFRESH_MARGIN_MINUTES)

    token = (
        db.query(InterbankingToken)
        .filter(
            InterbankingToken.credential_id == cred.id,
            InterbankingToken.scope == scope,
            InterbankingToken.is_active == True,
            InterbankingToken.expires_at > threshold,
        )
        .first()
    )

    if token:
        return token.access_token, cred.id

    return _refresh_token(db, cred, scope, user_id)


def _build_token_payload(cred: InterbankingCredential, scope: str) -> dict:
    grant = grant_for(scope)
    if grant == "client_credentials":
        if not cred.client_secret_encrypted:
            raise HTTPException(
                status_code=400,
                detail=f"No hay client_secret configurado para scope={scope}",
            )
        return {
            "grant_type": "client_credentials",
            "client_id": cred.client_id,
            "client_secret": decrypt_secret(cred.client_secret_encrypted),
        }
    # password
    if not cred.username or not cred.password_encrypted:
        raise HTTPException(
            status_code=400,
            detail=f"No hay usuario/contraseña configurado para scope={scope}",
        )
    return {
        "grant_type": "password",
        "username": cred.username,
        "password": decrypt_secret(cred.password_encrypted),
        "client_id": cred.client_id,
    }


def _refresh_token(db: Session, cred: InterbankingCredential, scope: str, user_id: int) -> tuple[str, int]:
    token_url = f"{cred.auth_url}/cas/oidc/accessToken"
    params = {"scope": scope}
    payload = _build_token_payload(cred, scope)

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
        resp = httpx.post(token_url, data=payload, params=params, headers=headers, timeout=15)
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
            operation=f"OBTENER_TOKEN[{scope}]",
            method="POST",
            endpoint="/cas/oidc/accessToken",
            request_payload={
                "client_id": cred.client_id,
                "grant_type": grant_for(scope),
                "scope": scope,
                "username": cred.username,
            },
            response_status=status_code,
            response_payload={"token_type": response_data.get("token_type")} if response_data else None,
            duration_ms=duration_ms,
            success=success,
            credential_id=cred.id,
            error_message=error_msg,
        )

    if not success:
        raise HTTPException(status_code=502, detail=f"Error al obtener token de Interbanking ({scope}): {error_msg}")

    # Desactivar tokens anteriores del mismo scope
    db.query(InterbankingToken).filter(
        InterbankingToken.credential_id == cred.id,
        InterbankingToken.scope == scope,
        InterbankingToken.is_active == True,
    ).update({"is_active": False})

    expires_in = response_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    new_token = InterbankingToken(
        credential_id=cred.id,
        scope=scope,
        access_token=response_data["access_token"],
        token_type=response_data.get("token_type", "Bearer"),
        expires_at=expires_at,
        is_active=True,
    )
    db.add(new_token)
    db.commit()

    return new_token.access_token, cred.id


def get_token_status(db: Session) -> dict:
    """Retorna el estado de los tokens activos por scope."""
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred:
        return {"tokens": []}

    tokens = (
        db.query(InterbankingToken)
        .filter(
            InterbankingToken.credential_id == cred.id,
            InterbankingToken.is_active == True,
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    out = []
    for scope in SCOPE_TO_GRANT.keys():
        t = next((x for x in tokens if x.scope == scope), None)
        if not t:
            out.append({"scope": scope, "has_active_token": False})
            continue
        expires_at = t.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        mins = int((expires_at - now).total_seconds() / 60)
        out.append({
            "scope": scope,
            "has_active_token": mins > 0,
            "expires_at": expires_at,
            "minutes_remaining": max(0, mins),
        })
    return {"tokens": out}
