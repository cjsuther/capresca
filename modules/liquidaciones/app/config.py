from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    conciliacion_service_url: str = "http://conciliacion:8006"
    clientes_service_url: str = "http://clientes:8003"
    notifications_service_url: str = "http://notifications:8005"
    internal_api_key: str = ""
    legacy_service_url: str = "http://legacy:8009"
    legacy_internal_api_key: str = ""
    # Ingesta automática diaria del archivo de liquidación desde una carpeta/share
    inbox_enabled: bool = True
    inbox_dir: str = "/data/liquidaciones/inbox"
    inbox_cron_hour: int = 7
    inbox_cron_minute: int = 0
    inbox_scan_on_startup: bool = True         # procesa lo pendiente al arrancar (idempotente: mueve a processed/)
    inbox_default_user_id: int = 0             # usuario "sistema" para los lotes automáticos
    scheduler_timezone: str = "America/Argentina/Buenos_Aires"

    class Config:
        env_file = ".env"


settings = Settings()
