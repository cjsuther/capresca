import base64
import hashlib
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    interbanking_base_url: str = "https://api.interbanking.com.ar"
    interbanking_auth_url: str = "https://preauth.interbanking.com.ar"
    encryption_key: str
    notifications_service_url: str = "http://notifications:8005"
    # Mock: cuando no hay credenciales de transferencias-confeccion operativas en este ambiente.
    # Setear en false al pasar a credenciales reales.
    interbanking_mock_transfers: bool = True
    # Dominios admitidos para base_url / auth_url / service_url de las credenciales. Sin esto, quien
    # pueda configurar credenciales apunta el módulo a un host propio: el "probar conexión" le manda
    # los secretos descifrados y las operaciones (incluidas transferencias) se van a ese host.
    allowed_provider_domains: str = "interbanking.com.ar"

    class Config:
        env_file = ".env"


settings = Settings()


def provider_domains() -> list[str]:
    return [d.strip().lower() for d in settings.allowed_provider_domains.split(",") if d.strip()]


def get_fernet() -> Fernet:
    """Deriva una clave Fernet válida de 32 bytes a partir de la variable de entorno."""
    key_bytes = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_secret(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
