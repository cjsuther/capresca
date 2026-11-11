from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPayload(BaseModel):
    user_id: int
    username: str


class UserInfo(BaseModel):
    id: int
    username: str
    full_name: str | None

    model_config = {"from_attributes": True}


class PermissionsPayload(BaseModel):
    modules: List[str]
    actions: Dict[str, List[str]]


class LoginResponse(BaseModel):
    """Sesión completa, o (con el doble factor) el paso intermedio:
    - `requires_2fa`: falta el código; `mfa_token` sirve sólo para POST /auth/2fa/login.
    - `requires_enrollment`: el 2FA es obligatorio y no está activo; `mfa_token` sirve sólo para
      enrolarse (POST /auth/2fa/login/enrolar y /activar).
    En esos dos casos NO hay `access_token`."""
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserInfo] = None
    permissions: Optional[PermissionsPayload] = None
    requires_2fa: bool = False
    requires_enrollment: bool = False
    mfa_token: Optional[str] = None
    mfa_expires_in: Optional[int] = None
    # Al ingresar con un código de recuperación: cuántos le quedan (para sugerirle regenerarlos).
    remaining_recovery_codes: Optional[int] = None
    recovery_codes: Optional[List[str]] = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Doble factor ─────────────────────────────────────────────────────────────────────────────────
class CodigoRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class MfaCodigoRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=4096)
    code: str = Field(min_length=1, max_length=32)


class MfaTokenRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=4096)


class ActivarRequest(BaseModel):
    token_id: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=32)


class MfaActivarRequest(ActivarRequest):
    mfa_token: str = Field(min_length=1, max_length=4096)
