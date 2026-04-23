import os
from datetime import datetime
from app.config import settings
from app.services import whatsapp_service


def get_inbound_path(conversation_id: int, wa_message_id: str, filename: str) -> str:
    directory = os.path.join(settings.media_storage_path, "inbound", str(conversation_id))
    os.makedirs(directory, exist_ok=True)
    safe_filename = f"{wa_message_id}_{filename}"
    return os.path.join(directory, safe_filename)


def get_outbound_path(conversation_id: int, filename: str) -> str:
    directory = os.path.join(settings.media_storage_path, "outbound", str(conversation_id))
    os.makedirs(directory, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"{timestamp}_{filename}"
    return os.path.join(directory, safe_filename)


async def download_and_store_inbound(
    media_id: str, conversation_id: int, wa_message_id: str, filename: str
) -> str | None:
    """Descarga un archivo de WhatsApp y lo almacena localmente."""
    result = await whatsapp_service.download_media(media_id)
    if not result:
        return None
    file_bytes, content_type = result
    local_path = get_inbound_path(conversation_id, wa_message_id, filename)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path


def store_outbound_file(file_bytes: bytes, conversation_id: int, filename: str) -> str:
    """Almacena un archivo saliente localmente."""
    local_path = get_outbound_path(conversation_id, filename)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path
