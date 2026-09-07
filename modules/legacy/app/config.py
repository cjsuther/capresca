from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    # Acceso al share legacy (montado por SMB/CIFS en el host, bind-mount read-only)
    smb_mount_root: str = "/data/agjs"

    # Kill switch de la integración. False = no se toca el legacy; las lecturas
    # se sirven desde el mirror Postgres y las escrituras devuelven 410.
    integration_enabled: bool = True

    # Modo de escritura. "outbox_only" (default seguro): toda escritura se encola
    # y se aplica en ventana de mantenimiento (nunca en caliente sobre las DBF).
    write_mode: str = "outbox_only"

    # Fase 4 — drenado real, SOLO contra una copia sandbox (nunca el share productivo).
    # El productivo seguirá requiriendo REINDEX en VFP (no implementado).
    allow_real_drain: bool = False
    sandbox_write_root: str = "/data/agjs_sandbox"

    # Autenticación de endpoints internos (contenedor-a-contenedor)
    internal_api_key: str = ""

    # Servicios consumidos por este módulo
    notifications_service_url: str = "http://notifications:8005"

    # Scheduler de sincronización (minutos). 0 desactiva ese grupo.
    sync_enabled: bool = True
    sync_caja_minutes: int = 10          # caja: alta volatilidad
    sync_creditos_minutes: int = 60      # creditos: media
    sync_maestros_minutes: int = 1440    # maestros: baja (1/día)

    class Config:
        env_file = ".env"


settings = Settings()
