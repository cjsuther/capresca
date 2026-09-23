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

    # Desembolsos por Tesorería: con el flag activo, liquidar un contrato no lo activa en el acto; manda la
    # transferencia a Tesorería (que la aprueba y la envía por Interbanking) y el contrato pasa a ACTIVO
    # cuando Tesorería avisa que se acreditó. La misma clave autentica el envío y el aviso de vuelta.
    desembolso_via_tesoreria: bool = False
    tesoreria_service_url: str = "http://tesoreria:8012"
    tesoreria_internal_api_key: str = ""
    tesoreria_callback_url: str = "http://creditos:8010/internal/creditos/tesoreria/resultado"

    # Integraciones externas (secretos por entorno; ver README)
    intranet_auth_url: str = ""
    intranet_client_id: str = ""
    intranet_client_secret: str = ""
    intranet_data_url: str = ""

    # Portal del ciudadano · SSO Mi Catamarca (OIDC). Secretos SIEMPRE por entorno.
    # Un solo valor cambia de entorno (producción / desarrollo); los endpoints salen de ahí, tal como
    # los publica el discovery: <issuer>/.well-known/openid-configuration
    #   producción:  https://api-mi.catamarca.gob.ar/openid
    #   desarrollo:  https://develop-api-mi.catamarca.gob.ar/openid
    micatamarca_issuer: str = "https://api-mi.catamarca.gob.ar/openid"
    # Vacíos = se derivan del issuer. Se completan sólo si el proveedor mueve alguna ruta.
    micatamarca_authorization_endpoint: str = ""
    micatamarca_token_endpoint: str = ""
    micatamarca_userinfo_endpoint: str = ""
    micatamarca_jwks_endpoint: str = ""
    micatamarca_client_id: str = ""       # ← MICATAMARCA_CLIENT_ID por entorno
    micatamarca_client_secret: str = ""   # ← MICATAMARCA_CLIENT_SECRET por entorno (rotar el filtrado)
    # El scope concedido a este cliente. `phone` no está otorgado: pedirlo hace fallar la autorización.
    micatamarca_scopes: str = "openid profile email"
    # PKCE (lo pide el documento de integración). El discovery no lo anuncia; mandar el challenge es
    # inocuo si el proveedor lo ignora, pero queda el interruptor por si alguna vez rechaza el parámetro.
    micatamarca_pkce: bool = True
    # Callback = backend (el SPA nunca ve el authorization code). Registrar ESTA URL en Mi Catamarca.
    micatamarca_redirect_uri: str = "http://localhost/api/creditos/portal/auth/callback"
    portal_web_url: str = "http://localhost/portal-creditos"   # SPA del portal, para redirigir tras el login
    # Sin credenciales de Mi Catamarca, ¿se permite el proveedor MOCK fuera de development? (demo/QA)
    portal_mock_sso: bool = False
    # Videos que el ciudadano tiene que ver completos antes de confirmar la solicitud (paso 4 del portal).
    # "id:Título" separados por coma; el archivo es /portal-creditos/videos/<id>.mp4 (carpeta montada en el
    # contenedor del portal, CREDITOS_PORTAL_VIDEOS_HOST_PATH). Vacío = el paso de videos no se exige.
    portal_videos: str = "video1:Video 1,video2:Video 2,video3:Video 3"

    @property
    def micatamarca_configurado(self) -> bool:
        """Hay credenciales reales. Si no, el portal usa el proveedor MOCK (dev/demo/tests)."""
        return bool(self.micatamarca_client_id and self.micatamarca_client_secret)

    def _mc(self, ruta: str, explicito: str) -> str:
        return explicito or f"{self.micatamarca_issuer.rstrip('/')}/{ruta}"

    @property
    def mc_authorize_url(self) -> str:
        return self._mc("authorize", self.micatamarca_authorization_endpoint)

    @property
    def mc_token_url(self) -> str:
        return self._mc("token", self.micatamarca_token_endpoint)

    @property
    def mc_userinfo_url(self) -> str:
        return self._mc("userinfo", self.micatamarca_userinfo_endpoint)

    @property
    def mc_jwks_url(self) -> str:
        return self._mc("jwks", self.micatamarca_jwks_endpoint)

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
