"""
Cliente HTTP hacia la API de Interbanking.
Gestiona el token automáticamente y registra cada llamada en audit_log.
"""
import time
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services import audit_service, token_manager


def call(
    db: Session,
    user_id: int,
    operation: str,
    method: str,
    path: str,
    scope: str,
    payload: Optional[dict] = None,
    params: Optional[dict] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Any:
    access_token, credential_id = token_manager.get_valid_token(db, scope, user_id)
    cred = token_manager.get_active_credential(db)
    base = (cred.base_url or "").rstrip("/")
    rel = path if path.startswith("/") else f"/{path}"
    url = f"{base}{rel}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "client_id": cred.client_id,
    }
    if cred.service_url:
        headers["service"] = cred.service_url

    start = time.time()
    success = False
    response_data = None
    status_code = None
    error_msg = None

    try:
        resp = httpx.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            params=params,
            timeout=30,
        )
        status_code = resp.status_code
        try:
            response_data = resp.json()
        except Exception:
            response_data = {"raw": resp.text}

        if resp.is_error:
            error_msg = response_data.get("message") or response_data.get("detail") or resp.text
            error_msg = f"{error_msg} [url={url}]"
        else:
            success = True
    except Exception as e:
        error_msg = str(e)
    finally:
        duration_ms = int((time.time() - start) * 1000)
        audit_service.log(
            db=db,
            user_id=user_id,
            username=username,
            credential_id=credential_id,
            operation=operation,
            method=method,
            endpoint=path,
            request_payload=payload,
            response_status=status_code,
            response_payload=response_data,
            duration_ms=duration_ms,
            success=success,
            error_message=error_msg,
            ip_address=ip_address,
        )

    if not success:
        raise HTTPException(
            status_code=status_code or 502,
            detail=f"Error de Interbanking: {error_msg}",
        )

    return response_data
