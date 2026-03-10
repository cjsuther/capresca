from fastapi import Header, HTTPException
from typing import Optional


def get_current_user_id(x_user_id: str = Header(...)) -> int:
    try:
        return int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Header X-User-Id inválido")


def get_current_username(x_username: Optional[str] = Header(None)) -> Optional[str]:
    return x_username
