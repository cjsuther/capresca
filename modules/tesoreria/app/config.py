from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Clave de la API interna: la presentan los módulos que mandan lotes (Créditos, Conciliación) y la
    # manda Tesorería al avisarles el resultado. Vacía = API interna cerrada.
    internal_api_key: str = ""

    interbanking_service_url: str = "http://interbanking:8004"
    configuraciones_service_url: str = "http://configuraciones:8011"
    # Créditos: dueño de los lotes de solicitudes que pagan las órdenes de pago (misma clave interna).
    creditos_service_url: str = "http://creditos:8010"
    configuraciones_internal_api_key: str = ""

    # Modo simulación: registra todo el circuito (aprobación, envío, confirmación) SIN llamar al banco.
    # Encendido por defecto: para mover dinero real hay que apagarlo a propósito.
    envio_simulado: bool = True

    # Código de cliente (abonado) en Interbanking: encabeza el archivo de alta de cuentas de terceros.
    interbanking_codigo_cliente: str = "X79555A"

    class Config:
        env_file = ".env"


settings = Settings()
