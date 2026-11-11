"""Doble factor (TOTP) de Portezuelo sobre TokenServer: política, verificación y enrolamiento.

Principios:
  - Apagado (`TOKENSERVER_ENABLED=false`) no cambia nada: ni el login ni el gateway piden códigos.
  - La marca local `users.totp_activo` decide si el login pide el código, sin consultar a TokenServer:
    si TokenServer no responde, el que tiene 2FA NO entra (falla cerrado, 503 con mensaje claro).
  - Los errores de TokenServer se traducen a `ErrorDobleFactor` (status + `code` estable + mensaje en
    castellano), que el handler de `main.py` devuelve como {"detail", "code", ...}.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services import tokenserver as ts
from app.services.permissions_service import roles_efectivos

log = logging.getLogger("security.2fa")

_TOTP = re.compile(r"^\d{6}$")
_RECUPERACION = re.compile(r"^[A-Za-z0-9]{10}$")


class ErrorDobleFactor(Exception):
    def __init__(self, status: int, code: str, detail: str, headers: dict | None = None, **extra):
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra
        super().__init__(f"{status} {code}")

    def cuerpo(self) -> dict:
        return {"detail": self.detail, "code": self.code, **self.extra}


def habilitado() -> bool:
    return bool(settings.tokenserver_enabled)


def exigir_habilitado() -> None:
    if not habilitado():
        raise ErrorDobleFactor(404, "2fa_deshabilitado", "El doble factor no está habilitado en el sistema.")


def roles_obligatorios() -> set[str]:
    return {r.strip().lower() for r in settings.tokenserver_obligatorio_roles.split(",") if r.strip()}


def es_obligatorio(user: User) -> bool:
    """¿La política exige 2FA a este usuario? ("*" = a todos; si no, por nombre de rol efectivo)."""
    if not habilitado():
        return False
    exigidos = roles_obligatorios()
    if not exigidos:
        return False
    if "*" in exigidos:
        return True
    return any(r.is_active and (r.name or "").lower() in exigidos for r in roles_efectivos(user))


def account_de(user: User) -> str:
    """Lo que el usuario ve en la app autenticadora (junto al issuer del tenant)."""
    return user.username


def normalizar(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "")


# ── Traducción de errores de TokenServer ─────────────────────────────────────────────────────────
NO_DISPONIBLE = ("El servicio de doble factor no responde. Por seguridad no se puede continuar sin el "
                 "segundo factor: probá de nuevo en unos minutos o avisá a Sistemas.")


def _traducir(e: Exception) -> ErrorDobleFactor:
    if isinstance(e, ts.TokenServerNoDisponible):
        return ErrorDobleFactor(503, "2fa_no_disponible", NO_DISPONIBLE)
    assert isinstance(e, ts.TokenServerError)
    if e.code == "user_locked":
        espera = e.retry_after or 60
        return ErrorDobleFactor(429, "2fa_bloqueado",
                                f"Demasiados códigos incorrectos. Probá de nuevo en {espera} segundos.",
                                headers={"Retry-After": str(espera)}, retry_after=espera)
    if e.code == "invalid_code" or e.status == 422 or e.status == 400:
        return ErrorDobleFactor(422, "codigo_invalido", "El código no es correcto.",
                                **({"remaining_attempts": e.remaining_attempts}
                                   if e.remaining_attempts is not None else {}))
    if e.code == "no_active_token":
        return ErrorDobleFactor(409, "2fa_sin_dispositivo",
                                "Tu doble factor no tiene ningún dispositivo activo. Pedile a un "
                                "administrador que te lo resetee para volver a activarlo.")
    if e.status == 410 or e.code == "enrollment_expired" or (e.status == 404 and e.code == "not_found"):
        return ErrorDobleFactor(410, "enrolamiento_vencido",
                                "El código QR venció. Generá uno nuevo y escanealo otra vez.")
    if e.code == "too_many_tokens":
        return ErrorDobleFactor(409, "demasiados_dispositivos",
                                "Tenés demasiados dispositivos pendientes. Esperá 10 minutos y reintentá.")
    log.error("TokenServer: error no esperado %s %s", e.status, e.code)
    return ErrorDobleFactor(503, "2fa_no_disponible", NO_DISPONIBLE)


# ── Verificación ─────────────────────────────────────────────────────────────────────────────────
def verificar(user: User, code: str, db: Session | None = None) -> dict:
    """Valida un código de 6 dígitos o uno de recuperación (XXXXX-XXXXX). Nunca deja pasar sin
    respuesta afirmativa de TokenServer. Devuelve {"metodo": "totp"|"recuperacion", ...}."""
    limpio = normalizar(code)
    try:
        if _TOTP.match(limpio):
            r = ts.verificar(user.id, limpio)
            if r.get("valid") is True:
                return {"metodo": "totp"}
            extra = {"remaining_attempts": r["remaining_attempts"]} if "remaining_attempts" in r else {}
            raise ErrorDobleFactor(422, "codigo_invalido", "El código no es correcto.", **extra)
        if _RECUPERACION.match(limpio):
            r = ts.verificar_codigo_recuperacion(user.id, limpio)
            if r.get("valid") is True:
                log.info("2FA: user_id=%s usó un código de recuperación", user.id)
                return {"metodo": "recuperacion", "remaining_codes": r.get("remaining_codes")}
            extra = {"remaining_attempts": r["remaining_attempts"]} if "remaining_attempts" in r else {}
            raise ErrorDobleFactor(422, "codigo_invalido", "El código de recuperación no es válido o ya se usó.",
                                   **extra)
    except (ts.TokenServerError, ts.TokenServerNoDisponible) as e:
        err = _traducir(e)
        # TokenServer dice que no hay dispositivo activo: la marca local quedó vieja (reset desde el panel
        # de TokenServer). Se baja la marca, pero igual se niega: nadie entra sin el segundo factor.
        if err.code == "2fa_sin_dispositivo" and db is not None and user.totp_activo:
            marcar(db, user, False)
        raise err from e
    raise ErrorDobleFactor(422, "codigo_invalido",
                           "Ingresá los 6 dígitos de la app o un código de recuperación (XXXXX-XXXXX).")


# ── Enrolamiento ─────────────────────────────────────────────────────────────────────────────────
def enrolar(user: User) -> dict:
    """Crea un token pendiente (QR). Antes borra los pendientes que hayan quedado de intentos previos."""
    if user.totp_activo:
        raise ErrorDobleFactor(409, "2fa_ya_activo", "El doble factor ya está activo. Desactivalo antes de "
                               "enrolar otro dispositivo.")
    try:
        for t in ts.listar_tokens(user.id):
            if t.get("status") == "pending" and t.get("id"):
                ts.borrar_token(user.id, t["id"])
        en = ts.enrolar(user.id, account_de(user))
    except (ts.TokenServerError, ts.TokenServerNoDisponible) as e:
        raise _traducir(e) from e
    return {k: en.get(k) for k in ("token_id", "qr_png_base64", "secret", "otpauth_uri", "expires_at",
                                   "issuer", "account", "digits", "period")}


def activar(db: Session, user: User, token_id: str, code: str) -> list[str]:
    """Activa con el primer código, marca al usuario y genera los códigos de recuperación."""
    if not token_id or len(token_id) > 64:
        raise ErrorDobleFactor(422, "token_invalido", "Falta el dispositivo a activar.")
    try:
        ts.activar(user.id, token_id, normalizar(code))
    except (ts.TokenServerError, ts.TokenServerNoDisponible) as e:
        raise _traducir(e) from e
    marcar(db, user, True)
    try:
        return ts.generar_codigos_recuperacion(user.id)
    except (ts.TokenServerError, ts.TokenServerNoDisponible):
        # El 2FA ya quedó activo: los códigos se pueden generar después desde "Doble factor".
        log.warning("2FA: user_id=%s activado sin códigos de recuperación (TokenServer no respondió)", user.id)
        return []


def regenerar_codigos(user: User) -> list[str]:
    try:
        return ts.generar_codigos_recuperacion(user.id)
    except (ts.TokenServerError, ts.TokenServerNoDisponible) as e:
        raise _traducir(e) from e


def resetear(db: Session, user: User) -> int:
    """Borra todo el 2FA del usuario en TokenServer y baja la marca local."""
    try:
        borrados = ts.resetear(user.id)
    except (ts.TokenServerError, ts.TokenServerNoDisponible) as e:
        raise _traducir(e) from e
    marcar(db, user, False)
    return borrados


def marcar(db: Session, user: User, activo: bool) -> None:
    user.totp_activo = activo
    user.totp_activado_en = datetime.now(timezone.utc) if activo else None
    db.commit()
    db.refresh(user)
