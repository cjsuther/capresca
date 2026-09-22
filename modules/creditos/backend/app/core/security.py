"""Autenticación JWT y RBAC.

El modelo de perfiles replica `symdeperf` del VFP: cada usuario tiene un
`perfil` (ADMG, xCJ caja, xCR créditos, ...) que determina permisos.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

# Mapa de prefijos de perfil VFP -> descripción (de login1.prg).
PERFILES = {
    "ADMG": "Administrador general",
    "CJ": "Caja / Tesorería",
    "CR": "Créditos",
    "TE": "Tesorería",
    "SE": "Seguros",
    "CG": "Contabilidad general",
    "DE": "Despacho",
    "JU": "Juegos",
    "AD": "Administración",
    "AU": "Mesa de entradas",
    "NT": "Notas / Créditos",
}


def hash_password(password: str) -> str:
    # bcrypt opera sobre <=72 bytes; truncamos defensivamente.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, perfil: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "perfil": perfil, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_portal_token(sub: str, email: str = "", nombre: str = "", documento: str = "") -> str:
    """Token de sesión del PORTAL CIUDADANO. `scope="portal"` lo separa del realm interno:
    un token de ciudadano nunca puede usarse en endpoints del backoffice (y viceversa)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": sub, "email": email, "nombre": nombre, "documento": documento,
               "scope": "portal", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_state_token(nonce: str) -> str:
    """State firmado y efímero para el flujo OIDC (evita CSRF sin estado en servidor)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    return jwt.encode({"nonce": nonce, "scope": "oidc-state", "exp": expire},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
