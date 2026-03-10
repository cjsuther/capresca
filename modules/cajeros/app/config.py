from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    security_service_url: str = "http://security:8001"
    notifications_service_url: str = "http://notifications:8005"

    class Config:
        env_file = ".env"


settings = Settings()
