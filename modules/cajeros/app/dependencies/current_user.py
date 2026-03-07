from fastapi import Header, HTTPException


def get_current_user_id(x_user_id: str = Header(...)) -> int:
    try:
        return int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Header X-User-Id inválido")
