from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    # Tope de una sesión contando las renovaciones: después hay que volver a ingresar con la clave.
    jwt_sesion_max_horas: int = 16

    # ── Doble factor (TOTP) con TokenServer ──────────────────────────────────────────────────────
    # Apagado por defecto: con false el login y todo lo demás funcionan exactamente como antes.
    tokenserver_enabled: bool = False
    # En producción, por la red Docker compartida: http://tokenserver-web:8080/v1
    tokenserver_url: str = "http://tokenserver-web:8080/v1"
    # API key del tenant (tsk_...). Sólo vive en el backend: nunca en el repo ni en el frontend.
    tokenserver_api_key: str = ""
    # Timeouts cortos: si TokenServer no contesta, el login con 2FA falla cerrado enseguida.
    tokenserver_timeout: float = 4.0
    tokenserver_connect_timeout: float = 2.0
    # Política: quién DEBE tener 2FA. Vacío = opcional para todos; "*" = obligatorio para todos;
    # o nombres de roles separados por coma (roles propios o heredados de grupos activos).
    tokenserver_obligatorio_roles: str = ""
    # Vida del token temporal entre la clave y el código (paso 2 del login) y del enrolamiento forzado.
    tokenserver_login_minutos: int = 5
    tokenserver_enrolamiento_minutos: int = 10
    # Vida del token de step-up (operaciones sensibles): no pide el código en cada clic.
    tokenserver_stepup_minutos: int = 5
    # Texto que ve el usuario en la app autenticadora junto al issuer del tenant.
    tokenserver_label: str = "Portezuelo"

    class Config:
        env_file = ".env"


settings = Settings()
