from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    conciliacion_service_url: str = "http://conciliacion:8006"
    clientes_service_url: str = "http://clientes:8003"
    internal_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
