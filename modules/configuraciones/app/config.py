from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Clave de la API interna (`/internal/*`): la presentan los módulos que consumen la configuración
    # (hoy Créditos). Vacía = API interna deshabilitada.
    internal_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
