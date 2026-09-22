"""Configuración de la aplicación. Los secretos vienen del entorno (nunca hardcodeados).

Recordatorio de migración: el sistema VFP tenía el ClientSecret de la API de
Catamarca en texto plano. Aquí todo secreto se lee de variables de entorno.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_INSEGURO = "cambiar-en-produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CCyPP API"
    environment: str = "development"

    # Base de datos
    database_url: str = "postgresql+psycopg://ccypp:ccypp@db:5432/ccypp"

    # Seguridad / JWT
    jwt_secret: str = JWT_SECRET_INSEGURO
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    @model_validator(mode="after")
    def _no_default_secret_en_produccion(self):
        # Fuera de development, el secreto JWT del código (público) permitiría forjar tokens = bypass de
        # auth. Se exige JWT_SECRET por entorno; si sigue el default, la app NO arranca. H-112.
        if self.environment.lower() not in ("development", "dev", "test", "testing") \
                and self.jwt_secret == JWT_SECRET_INSEGURO:
            raise ValueError(
                "JWT_SECRET no configurado: en producción debe setearse un secreto propio por entorno "
                "(el default del código permitiría forjar tokens). Configurá la variable JWT_SECRET.")
        return self

    # Padrón de clientes: vive en el módulo Clientes de Portezuelo. Créditos NO tiene maestro propio;
    # mantiene un espejo de sólo lectura que sincroniza contra este servicio (red interna de Docker).
    clientes_service_url: str = "http://clientes:8003"

    # Impuestos, índices de referencia, feriados y reglas del workflow viven en el módulo
    # Configuraciones; Créditos los lee por su API interna (con esta clave) y los cachea unos segundos.
    configuraciones_service_url: str = "http://configuraciones:8011"
    configuraciones_internal_api_key: str = ""
    configuraciones_cache_segundos: int = 30
    # Si Configuraciones no responde, se sigue con la última copia hasta este tope; sin copia, 503.
    configuraciones_copia_max_segundos: int = 600

    # Integraciones externas (secretos por entorno; ver README)
    intranet_auth_url: str = ""
    intranet_client_id: str = ""
    intranet_client_secret: str = ""
    intranet_data_url: str = ""

    # Portal del ciudadano · SSO Mi Catamarca (OIDC). Secretos SIEMPRE por entorno.
    # Endpoints reales del discovery: https://api-mi.catamarca.gob.ar/openid/.well-known/openid-configuration
    micatamarca_issuer: str = "https://api-mi.catamarca.gob.ar/openid"
    micatamarca_authorization_endpoint: str = "https://api-mi.catamarca.gob.ar/openid/authorize"
    micatamarca_token_endpoint: str = "https://api-mi.catamarca.gob.ar/openid/token"
    micatamarca_userinfo_endpoint: str = "https://api-mi.catamarca.gob.ar/openid/userinfo"
    micatamarca_client_id: str = ""       # ← MICATAMARCA_CLIENT_ID por entorno
    micatamarca_client_secret: str = ""   # ← MICATAMARCA_CLIENT_SECRET por entorno (rotar el filtrado)
    micatamarca_scopes: str = "openid email profile phone"
    # Callback = backend (el SPA nunca ve el authorization code). Registrar ESTA URL en Mi Catamarca.
    micatamarca_redirect_uri: str = "http://localhost/api/creditos/portal/auth/callback"
    portal_web_url: str = "http://localhost/portal-creditos"   # SPA del portal, para redirigir tras el login
    # Sin credenciales de Mi Catamarca, ¿se permite el proveedor MOCK fuera de development? (demo/QA)
    portal_mock_sso: bool = False

    @property
    def micatamarca_configurado(self) -> bool:
        """Hay credenciales reales. Si no, el portal usa el proveedor MOCK (dev/demo/tests)."""
        return bool(self.micatamarca_client_id and self.micatamarca_client_secret)

    # Fuente de haberes (sueldo/antigüedad) — Mi Catamarca u otro RRHH. Aún no existe el scope/API;
    # sin configurar, el portal usa un proveedor MOCK (el ciudadano igual puede declarar sus datos).
    haberes_api_url: str = ""      # endpoint que devuelve haberes por documento
    haberes_api_token: str = ""

    @property
    def haberes_configurado(self) -> bool:
        return bool(self.haberes_api_url and self.haberes_api_token)

    cors_origins: str = "http://localhost:5173,http://localhost:5174"


@lru_cache
def get_settings() -> Settings:
    return Settings()
