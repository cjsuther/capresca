from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    # Tope de una sesión contando las renovaciones: después hay que volver a ingresar con la clave.
    jwt_sesion_max_horas: int = 16

    class Config:
        env_file = ".env"


settings = Settings()
