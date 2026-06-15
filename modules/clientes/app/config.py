from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    security_service_url: str = "http://security:8001"
    legacy_service_url: str = "http://legacy:8009"
    legacy_internal_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
