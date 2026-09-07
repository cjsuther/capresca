from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    clientes_service_url: str = "http://clientes:8003"
    interbanking_service_url: str = "http://interbanking:8004"
    legacy_service_url: str = "http://legacy:8009"
    notifications_service_url: str = "http://notifications:8005"
    # Cruce automático (scheduler horario)
    auto_match_enabled: bool = True
    auto_match_interval_minutes: int = 60
    auto_match_lookback_days: int = 1          # además de hoy, reprocesa N días atrás (transferencias tardías)
    scheduler_timezone: str = "America/Argentina/Buenos_Aires"
    # Pagos salientes automáticos (mueven fondos reales — arrancan seguros)
    auto_payments_enabled: bool = False        # kill-switch: en false NO se generan pagos
    payments_dry_run: bool = True              # true = simula (registra intención sin llamar al banco)
    payment_concepto: str = "Pago Capresca"
    legacy_internal_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
