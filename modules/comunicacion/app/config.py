from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    clientes_service_url: str = "http://clientes:8003"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_webhook_verify_token: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_app_secret: str = ""
    media_storage_path: str = "/data/comunicacion/media"

    class Config:
        env_file = ".env"


settings = Settings()
