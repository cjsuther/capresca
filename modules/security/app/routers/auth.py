import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, UserInfo, PermissionsPayload, MfaCodigoRequest, MfaTokenRequest,
    MfaActivarRequest, CodigoRequest, ActivarRequest,
)
from app.services.auth_service import (
    authenticate_user, create_access_token, decode_token, blacklist_token, is_token_blacklisted,
    create_temp_token, decode_temp_token, SCOPE_LOGIN, SCOPE_ENROLAR, SCOPE_STEP_UP,
)
from app.services import doble_factor as df
from app.services import auditoria_central as central
from app.services.permissions_service import get_user_permissions

router = APIRouter(prefix="/auth", tags=["auth"])

AMR_CON_2FA = ["pwd", "otp"]


def _sesion(db: Session, user: User, amr: list[str] | None = None, **extra) -> LoginResponse:
    token = create_access_token(user.id, user.username, amr=amr)
    permissions = get_user_permissions(db, user.id)
    return LoginResponse(
        access_token=token,
        user=UserInfo(id=user.id, username=user.username, full_name=user.full_name),
        permissions=PermissionsPayload(**permissions),
        mfa={"habilitado": df.habilitado(), "activo": bool(user.totp_activo) and df.habilitado()},
        **extra,
    )


def _revocar(db: Session, payload: dict) -> None:
    jti = payload.get("jti")
    if jti and not is_token_blacklisted(db, jti):
        exp = payload.get("exp")
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc) if exp else datetime.now(timezone.utc)
        blacklist_token(db, jti, int(payload["sub"]), expires_at)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if df.habilitado():
        # La clave está bien, pero todavía NO hay sesión: sólo un token de un solo uso y vida corta que
        # sirve únicamente para el paso siguiente (el código, o enrolarse si el 2FA es obligatorio).
        if user.totp_activo:
            tok, vida = create_temp_token(SCOPE_LOGIN, user.id, settings.tokenserver_login_minutos)
            return LoginResponse(requires_2fa=True, mfa_token=tok, mfa_expires_in=vida)
        if df.es_obligatorio(user):
            tok, vida = create_temp_token(SCOPE_ENROLAR, user.id, settings.tokenserver_enrolamiento_minutos)
            return LoginResponse(requires_enrollment=True, mfa_token=tok, mfa_expires_in=vida)

    return _sesion(db, user)


# ── Paso 2 del login: el código ──────────────────────────────────────────────────────────────────
def _usuario_del_mfa(db: Session, token: str, scope: str) -> tuple[User, dict]:
    payload = decode_temp_token(token, scope)
    if not payload or is_token_blacklisted(db, payload["jti"]):
        raise df.ErrorDobleFactor(400, "mfa_token_invalido",
                                  "El paso de verificación venció o ya se usó. Volvé a ingresar con tu usuario y clave.")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise df.ErrorDobleFactor(400, "mfa_token_invalido", "Volvé a ingresar con tu usuario y clave.")
    return user, payload


@router.post("/2fa/login", response_model=LoginResponse)
def login_codigo(data: MfaCodigoRequest, db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, payload = _usuario_del_mfa(db, data.mfa_token, SCOPE_LOGIN)
    if not user.totp_activo:
        # Le resetearon el 2FA entre la clave y el código: que vuelva a empezar (y se enrole si corresponde).
        raise df.ErrorDobleFactor(400, "mfa_token_invalido", "Volvé a ingresar con tu usuario y clave.")
    try:
        r = df.verificar(user, data.code, db)
    except df.ErrorDobleFactor as e:
        central.registrar(usuario=user.username, usuario_id=user.id, operacion="ACCESO", entidad="User",
                          entidad_id=str(user.id), descripcion=f"Doble factor rechazado en el login ({e.code})",
                          exito=False)
        raise
    _revocar(db, payload)   # un solo uso
    extra = {}
    if r["metodo"] == "recuperacion":
        extra["remaining_recovery_codes"] = r.get("remaining_codes")
    return _sesion(db, user, amr=AMR_CON_2FA, **extra)


# ── 2FA obligatorio sin activar: enrolamiento dentro del login ──────────────────────────────────
@router.post("/2fa/login/enrolar")
def login_enrolar(data: MfaTokenRequest, db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, _ = _usuario_del_mfa(db, data.mfa_token, SCOPE_ENROLAR)
    return df.enrolar(user)


@router.post("/2fa/login/activar", response_model=LoginResponse)
def login_activar(data: MfaActivarRequest, db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, payload = _usuario_del_mfa(db, data.mfa_token, SCOPE_ENROLAR)
    codigos = df.activar(db, user, data.token_id, data.code)
    _revocar(db, payload)
    central.registrar(usuario=user.username, usuario_id=user.id, operacion="ACCION", entidad="User",
                      entidad_id=str(user.id), descripcion="Activó el doble factor (al ingresar)")
    return _sesion(db, user, amr=AMR_CON_2FA, recovery_codes=codigos)


# ── Con sesión: estado, enrolamiento, códigos de recuperación, desactivar y step-up ──────────────
def sesion_actual(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> tuple[User, dict]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    payload = decode_token(authorization.split(" ", 1)[1])
    if not payload or not str(payload.get("sub", "")).isdigit():
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    if payload.get("jti") and is_token_blacklisted(db, payload["jti"]):
        raise HTTPException(status_code=401, detail="Sesión cerrada")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    return user, payload


def _renovar_sesion(db: Session, user: User, payload: dict, amr: list[str] | None) -> str:
    """Misma sesión (mismo auth_time) con otro `amr`; la anterior deja de servir."""
    nuevo = create_access_token(user.id, user.username, auth_time=int(payload.get("auth_time") or 0) or None,
                                amr=amr)
    _revocar(db, payload)
    return nuevo


@router.get("/2fa/estado")
def estado(sesion=Depends(sesion_actual)):
    user, payload = sesion
    return {
        "habilitado": df.habilitado(),
        "activo": bool(user.totp_activo) and df.habilitado(),
        "obligatorio": df.es_obligatorio(user),
        "activado_en": user.totp_activado_en,
        "sesion_con_2fa": "otp" in (payload.get("amr") or []),
        "step_up_minutos": settings.tokenserver_stepup_minutos,
    }


@router.post("/2fa/enrolar")
def enrolar(sesion=Depends(sesion_actual)):
    df.exigir_habilitado()
    user, _ = sesion
    return df.enrolar(user)


@router.post("/2fa/activar")
def activar(data: ActivarRequest, sesion=Depends(sesion_actual), db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, payload = sesion
    if user.totp_activo:
        raise df.ErrorDobleFactor(409, "2fa_ya_activo", "El doble factor ya está activo.")
    codigos = df.activar(db, user, data.token_id, data.code)
    central.registrar(operacion="ACCION", entidad="User", entidad_id=str(user.id),
                      descripcion="Activó el doble factor")
    # Acaba de demostrar que tiene el dispositivo: la sesión pasa a tener segundo factor.
    return {"recovery_codes": codigos, "access_token": _renovar_sesion(db, user, payload, AMR_CON_2FA)}


@router.post("/2fa/codigos-recuperacion")
def regenerar_codigos(data: CodigoRequest, sesion=Depends(sesion_actual), db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, _ = sesion
    if not user.totp_activo:
        raise df.ErrorDobleFactor(409, "2fa_no_activo", "Primero activá el doble factor.")
    df.verificar(user, data.code, db)
    codigos = df.regenerar_codigos(user)
    central.registrar(operacion="ACCION", entidad="User", entidad_id=str(user.id),
                      descripcion="Regeneró sus códigos de recuperación del doble factor")
    return {"recovery_codes": codigos}


@router.post("/2fa/desactivar")
def desactivar(data: CodigoRequest, sesion=Depends(sesion_actual), db: Session = Depends(get_db)):
    df.exigir_habilitado()
    user, payload = sesion
    if not user.totp_activo:
        raise df.ErrorDobleFactor(409, "2fa_no_activo", "El doble factor no está activo.")
    if df.es_obligatorio(user):
        raise df.ErrorDobleFactor(403, "2fa_obligatorio",
                                  "Tu rol exige doble factor: no lo podés desactivar. Si perdiste el "
                                  "celular, pedile a un administrador que te lo resetee.")
    df.verificar(user, data.code, db)
    df.resetear(db, user)
    central.registrar(operacion="ACCION", entidad="User", entidad_id=str(user.id),
                      descripcion="Desactivó el doble factor")
    return {"access_token": _renovar_sesion(db, user, payload, None)}


@router.post("/2fa/step-up")
def step_up(data: CodigoRequest, sesion=Depends(sesion_actual), db: Session = Depends(get_db)):
    """Operaciones sensibles: con el código vigente, un token de step-up atado a ESTA sesión por unos
    minutos (el gateway lo pide en el header X-2FA-Token)."""
    df.exigir_habilitado()
    user, payload = sesion
    if not user.totp_activo:
        raise df.ErrorDobleFactor(409, "2fa_no_activo",
                                  "Esta operación exige doble factor. Activalo desde tu menú → Doble factor.")
    try:
        df.verificar(user, data.code, db)
    except df.ErrorDobleFactor as e:
        central.registrar(operacion="ACCION", entidad="User", entidad_id=str(user.id),
                          descripcion=f"Step-up rechazado ({e.code})", exito=False)
        raise
    tok, vida = create_temp_token(SCOPE_STEP_UP, user.id, settings.tokenserver_stepup_minutos,
                                  sid=payload.get("jti", ""))
    return {"step_up_token": tok, "expires_in": vida}


# ── Sesión ───────────────────────────────────────────────────────────────────────────────────────
@router.post("/logout")
def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    _revocar(db, payload)
    return {"message": "Sesión cerrada exitosamente"}


@router.post("/refresh")
def refresh_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    jti = payload.get("jti")
    if jti and is_token_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    # Un usuario desactivado no renueva: si no, la baja no corta la sesión (se renueva para siempre).
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    # Tope absoluto: una sesión robada no se puede renovar indefinidamente.
    auth_time = int(payload.get("auth_time") or payload.get("iat") or 0)
    if time.time() - auth_time > settings.jwt_sesion_max_horas * 3600:
        raise HTTPException(status_code=401, detail="La sesión venció: volvé a ingresar")

    # La renovación conserva cómo se autenticó (con o sin doble factor).
    new_token = create_access_token(int(payload["sub"]), payload["username"], auth_time=auth_time,
                                    amr=payload.get("amr"))
    # El token renovado reemplaza al anterior, que deja de servir.
    _revocar(db, payload)
    return {"access_token": new_token, "token_type": "bearer"}
