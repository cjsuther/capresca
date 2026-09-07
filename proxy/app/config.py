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
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    permissions_cache_ttl: int = 60  # segundos

    class Config:
        env_file = ".env"


settings = Settings()
