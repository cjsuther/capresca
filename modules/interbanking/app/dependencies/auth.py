from fastapi import Header, HTTPException, Request


def get_current_user_id(x_user_id: str = Header(...)) -> int:
    try:
        return int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Header X-User-Id inválido")


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
