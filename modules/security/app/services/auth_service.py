from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import hmac
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.permission import TokenBlacklist

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(user_id: int, username: str, auth_time: int | None = None,
                        amr: list[str] | None = None) -> str:
    """`auth_time`: cuándo se ingresó con usuario y clave. Las renovaciones lo conservan, así una sesión
    no se puede estirar para siempre (ver `jwt_sesion_max_horas`).
    `amr`: cómo se autenticó (["pwd"] o ["pwd", "otp"] si pasó el doble factor). El gateway lo mira para
    saber si la sesión tiene segundo factor."""
    ahora = datetime.now(timezone.utc)
    expire = ahora + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": ahora,
        "auth_time": auth_time or int(ahora.timestamp()),
    }
    if amr:
        payload["amr"] = list(amr)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """Sólo tokens de SESIÓN. Un token con `scope` (paso del login, step-up) nunca vale como sesión."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if "scope" in payload:
        return None
    return payload


# ── Tokens temporales del doble factor ───────────────────────────────────────────────────────────
# Se firman con una clave DERIVADA de JWT_SECRET y distinta por propósito: aunque algún código se
# olvidara de mirar el `scope`, un token del paso del login no valida como sesión ni como step-up.
SCOPE_LOGIN = "mfa_login"            # entre la clave y el código de 6 dígitos
SCOPE_ENROLAR = "mfa_enrolar"        # 2FA obligatorio y el usuario todavía no lo activó
SCOPE_STEP_UP = "step_up"            # operación sensible: el código se pidió hace menos de N minutos


def clave_derivada(scope: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"portezuelo-2fa:{scope}".encode(), hashlib.sha256).hexdigest()


def create_temp_token(scope: str, user_id: int, minutos: int, **extra) -> tuple[str, int]:
    """Token de vida corta para un solo propósito. Devuelve (token, segundos de vida)."""
    ahora = datetime.now(timezone.utc)
    vida = int(minutos * 60)
    payload = {"sub": str(user_id), "scope": scope, "jti": str(uuid.uuid4()), "iat": ahora,
               "exp": ahora + timedelta(seconds=vida), **extra}
    return jwt.encode(payload, clave_derivada(scope), algorithm="HS256"), vida


def decode_temp_token(token: str, scope: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token or "", clave_derivada(scope), algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("scope") != scope or not str(payload.get("sub", "")).isdigit() or not payload.get("jti"):
        return None
    return payload


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def blacklist_token(db: Session, jti: str, user_id: int, expires_at) -> None:
    entry = TokenBlacklist(jti=jti, user_id=user_id, expires_at=expires_at)
    db.add(entry)
    db.commit()


def is_token_blacklisted(db: Session, jti: str) -> bool:
    return db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None
