from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Clave de la API interna: la presentan los módulos que mandan lotes (Créditos, Conciliación) y la
    # manda Tesorería al avisarles el resultado. Vacía = API interna cerrada.
    internal_api_key: str = ""

    interbanking_service_url: str = "http://interbanking:8004"
    configuraciones_service_url: str = "http://configuraciones:8011"
    configuraciones_internal_api_key: str = ""

    # Modo simulación: registra todo el circuito (aprobación, envío, confirmación) SIN llamar al banco.
    # Encendido por defecto: para mover dinero real hay que apagarlo a propósito.
    envio_simulado: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
