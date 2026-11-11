"""TokenServer simulado en memoria, detrás de un `httpx.MockTransport`.

Responde como la API /v1 real (mismas rutas, códigos y cuerpos de error), así los tests ejercitan el
cliente HTTP de verdad (`app/services/tokenserver.py`) y la traducción de errores.
"""
from __future__ import annotations

import json
import re
import uuid

import httpx

CODIGO_OK = "123456"
CODIGO_OK_2 = "654321"


class TokenServerFalso:
    def __init__(self, max_intentos: int = 5):
        self.tokens: dict[str, list[dict]] = {}
        self.recuperacion: dict[str, set[str]] = {}
        self.fallidos: dict[str, int] = {}
        self.max_intentos = max_intentos
        self.caido = False                   # simula red caída / timeout
        self.forzar: tuple[int, dict, dict] | None = None   # (status, body, headers) para la próxima llamada
        self.llamadas: list[tuple[str, str]] = []
        self.api_key = "tsk_test_clave"
        self.usados: set[tuple[str, str]] = set()          # anti-replay

    # ── helpers para los tests ──
    def activar_usuario(self, uid: str) -> None:
        self.tokens.setdefault(uid, []).append({"id": str(uuid.uuid4()), "status": "active", "label": "x"})

    def transporte(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._manejar)

    # ── servidor ──
    def _json(self, status: int, body: dict | None = None, headers: dict | None = None) -> httpx.Response:
        return httpx.Response(status, json=body if body is not None else None, headers=headers or {})

    def _manejar(self, req: httpx.Request) -> httpx.Response:
        if self.caido:
            raise httpx.ConnectTimeout("timeout simulado", request=req)
        ruta = req.url.path
        self.llamadas.append((req.method, ruta))
        if req.headers.get("authorization") != f"Bearer {self.api_key}":
            return self._json(401, {"error": "unauthorized", "message": "API key ausente o inválida"})
        if self.forzar:
            status, body, headers = self.forzar
            self.forzar = None
            return self._json(status, body, headers)
        body = json.loads(req.content or b"{}") if req.content else {}

        m = re.fullmatch(r"/v1/users/([^/]+)(/.*)?", ruta)
        if not m:
            return self._json(404, {"error": "not_found", "message": "no"})
        uid, resto = m.group(1), m.group(2) or ""

        if req.method == "DELETE" and resto == "":
            n = len(self.tokens.pop(uid, []))
            self.recuperacion.pop(uid, None)
            self.fallidos.pop(uid, None)
            return self._json(200, {"tokens_deleted": n})

        if resto == "/tokens" and req.method == "POST":
            tid = str(uuid.uuid4())
            self.tokens.setdefault(uid, []).append({"id": tid, "status": "pending", "label": body.get("label")})
            return self._json(201, {
                "token_id": tid, "status": "pending", "secret": "JBSWY3DPEHPK3PXP",
                "otpauth_uri": f"otpauth://totp/Capresca:{body.get('account')}?secret=JBSWY3DPEHPK3PXP",
                "qr_png_base64": "iVBORw0KGgo=", "expires_at": "2026-11-11T12:10:00Z", "issuer": "Capresca",
                "account": body.get("account"), "algorithm": "SHA1", "digits": 6, "period": 30})
        if resto == "/tokens" and req.method == "GET":
            return self._json(200, {"tokens": self.tokens.get(uid, [])})

        mt = re.fullmatch(r"/tokens/([^/]+)(/activate)?", resto)
        if mt:
            tok = next((t for t in self.tokens.get(uid, []) if t["id"] == mt.group(1)), None)
            if req.method == "DELETE":
                if not tok:
                    return self._json(404, {"error": "not_found", "message": "recurso no encontrado"})
                self.tokens[uid].remove(tok)
                return httpx.Response(204)
            if not tok or tok["status"] != "pending":
                return self._json(404, {"error": "not_found", "message": "recurso no encontrado"})
            if body.get("code") != CODIGO_OK:
                return self._fallido(uid, 422)
            tok["status"] = "active"
            return self._json(200, {"status": "active", "token_id": tok["id"]})

        if resto == "/verify":
            if self._bloqueado(uid):
                return self._bloqueo()
            if not any(t["status"] == "active" for t in self.tokens.get(uid, [])):
                return self._json(404, {"error": "no_active_token", "message": "el usuario no tiene tokens activos"})
            code = body.get("code")
            if code in (CODIGO_OK, CODIGO_OK_2) and (uid, code) not in self.usados:
                self.usados.add((uid, code))
                self.fallidos[uid] = 0
                return self._json(200, {"valid": True, "token_id": "t"})
            return self._fallido(uid, 200)

        if resto == "/recovery-codes":
            codigos = [f"AAAA{i}-BBBB{i}" for i in range(10)]
            self.recuperacion[uid] = {c.replace("-", "") for c in codigos}
            return self._json(201, {"codes": codigos})
        if resto == "/recovery-codes/verify":
            code = (body.get("code") or "").replace("-", "").upper()
            if code in self.recuperacion.get(uid, set()):
                self.recuperacion[uid].discard(code)
                return self._json(200, {"valid": True, "remaining_codes": len(self.recuperacion[uid])})
            return self._fallido(uid, 200)
        return self._json(404, {"error": "not_found", "message": "no"})

    def _bloqueado(self, uid: str) -> bool:
        return self.fallidos.get(uid, 0) >= self.max_intentos

    def _bloqueo(self) -> httpx.Response:
        return self._json(429, {"error": "user_locked", "message": "usuario bloqueado por intentos fallidos",
                                "retry_after_seconds": 60}, {"Retry-After": "60"})

    def _fallido(self, uid: str, status: int) -> httpx.Response:
        self.fallidos[uid] = self.fallidos.get(uid, 0) + 1
        restantes = max(self.max_intentos - self.fallidos[uid], 0)
        if status == 422:
            return self._json(422, {"error": "invalid_code", "message": "código inválido",
                                    "remaining_attempts": restantes})
        return self._json(200, {"valid": False, "reason": "invalid_code", "remaining_attempts": restantes})
