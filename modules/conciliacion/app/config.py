from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    clientes_service_url: str = "http://clientes:8003"
    interbanking_service_url: str = "http://interbanking:8004"

    class Config:
        env_file = ".env"


settings = Settings()
