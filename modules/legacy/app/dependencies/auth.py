from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def verify_api_key(x_api_key: str = Header(...)):
    """Autenticación de endpoints internos (contenedor-a-contenedor)."""
    if not settings.internal_api_key:
        raise HTTPException(status_code=503, detail="API key no configurada")
    if x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[int]:
    """ID de usuario inyectado por el proxy en las rutas /api/legacy."""
    if x_user_id is None:
        return None
    try:
        return int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Header X-User-Id inválido")
