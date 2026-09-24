from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Clave de la API interna (la usan los módulos que consultan resoluciones). Vacía = cerrada.
    internal_api_key: str = ""

    auditoria_service_url: str = "http://auditoria:8013"
    auditoria_internal_api_key: str = ""

    # Dónde quedan los archivos del sistema anterior que se suben para importar.
    despacho_import_dir: str = "/data/despacho"

    class Config:
        env_file = ".env"


settings = Settings()
