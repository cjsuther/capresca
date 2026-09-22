from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # La presentan los módulos al mandar sus transacciones. Vacía = API interna cerrada.
    internal_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
