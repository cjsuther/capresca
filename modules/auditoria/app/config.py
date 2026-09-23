from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Clave de la API interna: la presentan el gateway y los módulos al registrar eventos.
    # Vacía = API interna cerrada (no se registra nada de afuera).
    internal_api_key: str = ""
    # Retención del registro (5 años): la auditoría se purga sola, no crece para siempre.
    retencion_dias: int = 1825
    purga_habilitada: bool = True
    # Zona horaria de los cortes del purgado diario.
    scheduler_timezone: str = "America/Argentina/Buenos_Aires"

    class Config:
        env_file = ".env"


settings = Settings()
