from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    security_service_url: str = "http://security:8001"
    cajeros_service_url: str = "http://cajeros:8002"
    clientes_service_url: str = "http://clientes:8003"
    interbanking_service_url: str = "http://interbanking:8004"
    notifications_service_url: str = "http://notifications:8005"
    conciliacion_service_url: str = "http://conciliacion:8006"
    liquidaciones_service_url: str = "http://liquidaciones:8007"
    legacy_service_url: str = "http://legacy:8009"
    creditos_service_url: str = "http://creditos:8010"
    configuraciones_service_url: str = "http://configuraciones:8011"
    tesoreria_service_url: str = "http://tesoreria:8012"
    auditoria_service_url: str = "http://auditoria:8013"
    contabilidad_service_url: str = "http://contabilidad:8014"
    despacho_service_url: str = "http://despacho:8015"
    # Auditoría central: el gateway registra TODA operación que modifica datos. Sin clave, no registra.
    auditoria_internal_api_key: str = ""
    auditoria_habilitada: bool = True
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    permissions_cache_ttl: int = 60  # segundos
    # Los reportes de créditos (PDF/Excel sobre la base completa) pueden pasar los 30s.
    upstream_timeout: float = 120.0

    class Config:
        env_file = ".env"


settings = Settings()
