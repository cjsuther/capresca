"""Proveedor de identidad OIDC de Mi Catamarca (SSO del portal ciudadano).

Flujo Authorization Code (cliente confidencial, client_secret_post):
  authorize_url() → el ciudadano se autentica en Mi Catamarca → callback con `code`
  identidad_desde_code(code) → intercambia el code en /token y lee /userinfo → identidad normalizada.

Está desacoplado detrás de una interfaz para poder:
  - usar el proveedor REAL cuando hay credenciales por entorno (producción/staging), y
  - usar un proveedor MOCK determinista en dev/demo/tests (sin API real ni el WAF de Cloudflare).

Endpoints reales (discovery verificado):
  https://api-mi.catamarca.gob.ar/openid/.well-known/openid-configuration
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings


@dataclass
class Identidad:
    """Identidad normalizada que devuelve cualquier proveedor (real o mock)."""
    sub: str
    email: str = ""
    nombre: str = ""
    telefono: str = ""
    documento: str = ""
    crudo: dict | None = None   # claims originales, para depurar / decidir el vínculo con el maestro


class MiCatamarcaProvider:
    """Proveedor real: habla con los endpoints OIDC de Mi Catamarca."""
    mock = False

    def __init__(self, s):
        self.s = s

    def authorize_url(self, state: str) -> str:
        q = {"client_id": self.s.micatamarca_client_id, "response_type": "code",
             "scope": self.s.micatamarca_scopes, "redirect_uri": self.s.micatamarca_redirect_uri,
             "state": state}
        return f"{self.s.micatamarca_authorization_endpoint}?{urlencode(q)}"

    def identidad_desde_code(self, code: str) -> Identidad:
        with httpx.Client(timeout=15) as c:
            tok = c.post(self.s.micatamarca_token_endpoint, data={
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": self.s.micatamarca_redirect_uri,
                "client_id": self.s.micatamarca_client_id,
                "client_secret": self.s.micatamarca_client_secret,
            }, headers={"Accept": "application/json"})
            tok.raise_for_status()
            access = tok.json().get("access_token", "")
            ui = c.get(self.s.micatamarca_userinfo_endpoint,
                       headers={"Authorization": f"Bearer {access}"})
            ui.raise_for_status()
            claims = ui.json()
        return _normalizar(claims)


class MockMiCatamarca:
    """Proveedor MOCK: sin red. `authorize_url` apunta al endpoint mock del backend, que
    redirige al callback con un code fijo; `identidad_desde_code` devuelve un ciudadano demo."""
    mock = True

    def __init__(self, s):
        self.s = s

    def authorize_url(self, state: str) -> str:
        # El backend expone /api/creditos/portal/auth/mock-authorize sólo cuando el proveedor es mock.
        return f"/api/creditos/portal/auth/mock-authorize?{urlencode({'state': state})}"

    def identidad_desde_code(self, code: str) -> Identidad:
        return Identidad(sub="mc-demo-30123456", email="juan.perez@example.gob.ar",
                         nombre="JUAN CARLOS PEREZ", telefono="+54 383 400 0000",
                         documento="30123456", crudo={"mock": True, "code": code})


def _normalizar(claims: dict) -> Identidad:
    """Mapea los claims OIDC (userinfo) a nuestra Identidad. Tolerante a nombres alternativos."""
    nombre = (claims.get("name")
              or " ".join(x for x in (claims.get("given_name"), claims.get("family_name")) if x)
              or "").strip()
    return Identidad(
        sub=str(claims.get("sub", "")),
        email=claims.get("email", "") or "",
        nombre=nombre,
        telefono=claims.get("phone_number", "") or claims.get("phone", "") or "",
        documento=str(claims.get("documento") or claims.get("dni") or claims.get("cuil") or ""),
        crudo=claims,
    )


def get_provider():
    """Proveedor real si hay credenciales por entorno; si no, el mock (dev/demo/tests).

    Fuera de development el mock exige PORTAL_MOCK_SSO=true: el portal está publicado en Internet y el
    mock deja entrar a cualquiera como el ciudadano demo (y cargar solicitudes en la base real)."""
    s = get_settings()
    if s.micatamarca_configurado:
        return MiCatamarcaProvider(s)
    if s.environment.lower() in ("development", "dev", "test", "testing") or s.portal_mock_sso:
        return MockMiCatamarca(s)
    from fastapi import HTTPException
    raise HTTPException(503, "El portal no tiene configurado el ingreso con Mi Catamarca.")
