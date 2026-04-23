"""Integracion con la WhatsApp Business Cloud API de Meta."""
import hashlib
import hmac
import httpx
from app.config import settings

WA_API_BASE = "https://graph.facebook.com/v21.0"


def get_api_url() -> str:
    return f"{WA_API_BASE}/{settings.whatsapp_phone_number_id}/messages"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }


def normalize_ar_phone(phone: str) -> str:
    """Convierte numeros argentinos del formato webhook (549...) al formato API (5411...).
    Meta recibe mensajes con formato 5491169058614 pero envia con 54111569058614.
    """
    import re
    # Match Argentine mobile: 549 + area code (2-4 digits) + number
    m = re.match(r"^549(\d{2,4})(\d{8})$", phone)
    if m:
        area = m.group(1)
        number = m.group(2)
        return f"54{area}15{number}"
    return phone


async def send_text_message(to: str, text: str) -> dict | None:
    """Envia un mensaje de texto por WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_ar_phone(to),
        "type": "text",
        "text": {"body": text},
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(get_api_url(), json=payload, headers=get_headers(), timeout=15.0)
            r.raise_for_status()
            data = r.json()
            return {
                "wa_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "SENT",
            }
    except Exception as e:
        print(f"[whatsapp] Error sending text to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}


async def send_document_message(to: str, filename: str, caption: str = None, media_url: str = None, media_id: str = None) -> dict | None:
    """Envia un documento por WhatsApp. Usa media_id (upload previo) o media_url (link publico)."""
    document = {"filename": filename}
    if media_id:
        document["id"] = media_id
    elif media_url:
        document["link"] = media_url
    if caption:
        document["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_ar_phone(to),
        "type": "document",
        "document": document,
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(get_api_url(), json=payload, headers=get_headers(), timeout=30.0)
            r.raise_for_status()
            data = r.json()
            return {
                "wa_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "SENT",
            }
    except Exception as e:
        print(f"[whatsapp] Error sending document to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}


async def send_image_message(to: str, caption: str = None, media_url: str = None, media_id: str = None) -> dict | None:
    """Envia una imagen por WhatsApp. Usa media_id (upload previo) o media_url (link publico)."""
    image = {}
    if media_id:
        image["id"] = media_id
    elif media_url:
        image["link"] = media_url
    if caption:
        image["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_ar_phone(to),
        "type": "image",
        "image": image,
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(get_api_url(), json=payload, headers=get_headers(), timeout=30.0)
            r.raise_for_status()
            data = r.json()
            return {
                "wa_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "SENT",
            }
    except Exception as e:
        print(f"[whatsapp] Error sending image to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}


async def send_interactive_list(to: str, header_text: str, body_text: str, sections: list[dict]) -> dict | None:
    """Envia un mensaje interactivo tipo lista por WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_ar_phone(to),
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "action": {
                "button": "Ver opciones",
                "sections": sections,
            },
        },
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(get_api_url(), json=payload, headers=get_headers(), timeout=15.0)
            r.raise_for_status()
            data = r.json()
            return {
                "wa_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "SENT",
            }
    except httpx.HTTPStatusError as e:
        print(f"[whatsapp] Error sending interactive list to {to}: {e}")
        print(f"[whatsapp] Response body: {e.response.text}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    except Exception as e:
        print(f"[whatsapp] Error sending interactive list to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}


async def upload_media(file_bytes: bytes, mime_type: str, filename: str) -> str | None:
    """Sube un archivo a la API de WhatsApp y retorna el media_id."""
    url = f"{WA_API_BASE}/{settings.whatsapp_phone_number_id}/media"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                headers=headers,
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": (filename, file_bytes, mime_type)},
                timeout=60.0,
            )
            r.raise_for_status()
            return r.json().get("id")
    except Exception as e:
        print(f"[whatsapp] Error uploading media: {e}")
        return None


async def download_media(media_id: str) -> tuple[bytes, str] | None:
    """Descarga un archivo desde la API de WhatsApp. Retorna (bytes, content_type)."""
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        async with httpx.AsyncClient() as client:
            # First get the media URL
            r = await client.get(f"{WA_API_BASE}/{media_id}", headers=headers, timeout=10.0)
            r.raise_for_status()
            media_url = r.json().get("url")
            if not media_url:
                return None
            # Download the actual file
            r2 = await client.get(media_url, headers=headers, timeout=60.0)
            r2.raise_for_status()
            return r2.content, r2.headers.get("content-type", "application/octet-stream")
    except Exception as e:
        print(f"[whatsapp] Error downloading media {media_id}: {e}")
        return None


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verifica la firma HMAC SHA256 del webhook de Meta."""
    if not settings.whatsapp_app_secret:
        return True  # Skip verification if no app secret configured
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
