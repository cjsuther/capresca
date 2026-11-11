"""Cliente de TokenServer (2FA TOTP, compatible con Google y Microsoft Authenticator).

Sólo lo usa este módulo: la API key del tenant (`TOKENSERVER_API_KEY`) nunca sale del backend.

Reglas del cliente (ver el portal de TokenServer, /docs/):
  - timeouts cortos: si TokenServer no responde, se corta enseguida y el login FALLA CERRADO;
  - nunca se reintenta un POST (un /verify repetido contaría como replay o como intento fallido);
  - `uid` = id interno del usuario (estable), el username es sólo la cuenta visible en la app.

Errores:
  - `TokenServerError`: TokenServer respondió con un error de negocio (422 invalid_code, 429 user_locked,
    404 no_active_token, 410 enrollment_expired, 409 too_many_tokens…). Trae `code`, `retry_after` y
    `remaining_attempts` cuando vienen.
  - `TokenServerNoDisponible`: no hubo respuesta usable (red, timeout, 5xx, 401/403 de la API key o del
    tenant, 429 rate_limited). Quien llama NUNCA debe dejar pasar sin el segundo factor.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from app.config import settings

log = logging.getLogger("security.tokenserver")


class TokenServerError(Exception):
    def __init__(self, status: int, code: str, message: str = "", retry_after: int | None = None,
                 remaining_attempts: int | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.remaining_attempts = remaining_attempts
        super().__init__(f"{status} {code}: {message}")


class TokenServerNoDisponible(Exception):
    """TokenServer no respondió o la integración está mal configurada (API key, tenant)."""


def uid_de(user_id: int) -> str:
    """Identificador del usuario en TokenServer: el id interno (no cambia como el mail o el username)."""
    return str(int(user_id))


def _ruta_usuario(user_id: int) -> str:
    return "/users/" + quote(uid_de(user_id), safe="")


def _cliente() -> httpx.Client:
    return httpx.Client(
        base_url=settings.tokenserver_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.tokenserver_api_key}", "Accept": "application/json"},
        timeout=httpx.Timeout(settings.tokenserver_timeout, connect=settings.tokenserver_connect_timeout),
    )


def _entero(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _llamar(metodo: str, ruta: str, body: dict | None = None) -> dict:
    if not settings.tokenserver_api_key:
        log.error("TokenServer: falta TOKENSERVER_API_KEY")
        raise TokenServerNoDisponible("Falta configurar TOKENSERVER_API_KEY")
    try:
        with _cliente() as c:
            r = c.request(metodo, ruta, json=body)
    except httpx.HTTPError as e:
        log.error("TokenServer no responde (%s %s): %s", metodo, ruta.split("/")[-1], type(e).__name__)
        raise TokenServerNoDisponible(str(e)) from e

    if r.status_code == 204:
        return {}
    try:
        data = r.json() if r.content else {}
    except ValueError:
        data = {}
    if r.is_success:
        return data if isinstance(data, dict) else {}

    if not isinstance(data, dict):
        data = {}
    code = str(data.get("error") or "unknown")
    retry = _entero(r.headers.get("Retry-After")) or _entero(data.get("retry_after_seconds"))
    # Lo que no es un error del usuario sino de la integración o del servicio: no hay segundo factor.
    if r.status_code >= 500 or r.status_code in (401, 403) or code == "rate_limited":
        log.error("TokenServer respondió %s %s en %s", r.status_code, code, metodo)
        raise TokenServerNoDisponible(f"{r.status_code} {code}")
    raise TokenServerError(r.status_code, code, str(data.get("message") or ""), retry,
                           _entero(data.get("remaining_attempts")))


# ── API pública de TokenServer ───────────────────────────────────────────────────────────────────
def enrolar(user_id: int, account: str) -> dict:
    """Token pendiente (10 min). Devuelve token_id, qr_png_base64, secret, otpauth_uri, expires_at…"""
    return _llamar("POST", _ruta_usuario(user_id) + "/tokens",
                   {"label": settings.tokenserver_label[:100], "account": account[:200]})


def activar(user_id: int, token_id: str, code: str) -> dict:
    return _llamar("POST", f"{_ruta_usuario(user_id)}/tokens/{quote(token_id, safe='')}/activate",
                   {"code": code})


def listar_tokens(user_id: int) -> list[dict]:
    return list(_llamar("GET", _ruta_usuario(user_id) + "/tokens").get("tokens") or [])


def borrar_token(user_id: int, token_id: str) -> None:
    _llamar("DELETE", f"{_ruta_usuario(user_id)}/tokens/{quote(token_id, safe='')}")


def verificar(user_id: int, code: str) -> dict:
    """200 siempre que el código se pudo evaluar: {"valid": true|false, "remaining_attempts"?}."""
    return _llamar("POST", _ruta_usuario(user_id) + "/verify", {"code": code})


def generar_codigos_recuperacion(user_id: int) -> list[str]:
    return list(_llamar("POST", _ruta_usuario(user_id) + "/recovery-codes").get("codes") or [])


def verificar_codigo_recuperacion(user_id: int, code: str) -> dict:
    return _llamar("POST", _ruta_usuario(user_id) + "/recovery-codes/verify", {"code": code})


def resetear(user_id: int) -> int:
    """Borra todos los tokens y códigos del usuario y levanta su bloqueo."""
    return int(_llamar("DELETE", _ruta_usuario(user_id)).get("tokens_deleted") or 0)
