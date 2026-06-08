from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    clientes_service_url: str = "http://clientes:8003"
    media_storage_path: str = "/data/comunicacion/media"
    # Las credenciales de WhatsApp se administran en la tabla whatsapp_config
    # (Comunicación → Configuración → WhatsApp). Se ignoran las antiguas
    # WHATSAPP_* env vars si están seteadas.

    class Config:
        env_file = ".env"


settings = Settings()
