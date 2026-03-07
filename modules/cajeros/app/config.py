from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    security_service_url: str = "http://security:8001"

    class Config:
        env_file = ".env"


settings = Settings()
