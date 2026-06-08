"""Integracion con la WhatsApp Business Cloud API de Meta.

La configuración (phone_number_id, access_token, app_secret, webhook_verify_token,
business_account_id) se lee de la tabla `whatsapp_config` (activa). Antes vivía
en variables de entorno; ahora se administra desde la UI.
"""
import hashlib
import hmac
import re
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.whatsapp_config import WhatsappConfig

WA_API_BASE = "https://graph.facebook.com/v21.0"


# ─────────────────────────────────────────────────────────────────────────────
# Acceso a la configuración persistida
# ─────────────────────────────────────────────────────────────────────────────
def get_active_config(db: Session) -> WhatsappConfig:
    cfg = db.query(WhatsappConfig).filter(WhatsappConfig.is_active == True).first()
    if not cfg:
        raise RuntimeError(
            "WhatsApp no está configurado. Cargá la configuración en "
            "Comunicación → Configuración → WhatsApp."
        )
    return cfg


def _config_or_new_session(db: Optional[Session]) -> tuple[WhatsappConfig, Optional[Session]]:
    """Acepta una sesión opcional. Si no hay, abre una propia y la devuelve para cerrarla."""
    if db is not None:
        return get_active_config(db), None
    own = SessionLocal()
    try:
        return get_active_config(own), own
    except Exception:
        own.close()
        raise


def _close(own: Optional[Session]) -> None:
    if own is not None:
        own.close()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _api_url(cfg: WhatsappConfig, suffix: str = "messages") -> str:
    return f"{WA_API_BASE}/{cfg.phone_number_id}/{suffix}"


def _headers(cfg: WhatsappConfig, json: bool = True) -> dict:
    h = {"Authorization": f"Bearer {cfg.access_token}"}
    if json:
        h["Content-Type"] = "application/json"
    return h


def normalize_ar_phone(phone: str) -> str:
    """Convierte numeros argentinos del formato webhook (549...) al formato API (5411...)."""
    m = re.match(r"^549(\d{2,4})(\d{8})$", phone)
    if m:
        return f"54{m.group(1)}15{m.group(2)}"
    return phone


async def _post_message(cfg: WhatsappConfig, payload: dict, timeout: float = 15.0) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(_api_url(cfg), json=payload, headers=_headers(cfg), timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return {
            "wa_message_id": data.get("messages", [{}])[0].get("id"),
            "status": "SENT",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Operaciones
# ─────────────────────────────────────────────────────────────────────────────
async def send_text_message(to: str, text: str, db: Optional[Session] = None) -> dict | None:
    cfg, own = _config_or_new_session(db)
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": normalize_ar_phone(to),
            "type": "text",
            "text": {"body": text},
        }
        return await _post_message(cfg, payload)
    except Exception as e:
        print(f"[whatsapp] Error sending text to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    finally:
        _close(own)


async def send_document_message(to: str, filename: str, caption: str = None,
                                media_url: str = None, media_id: str = None,
                                db: Optional[Session] = None) -> dict | None:
    cfg, own = _config_or_new_session(db)
    try:
        document = {"filename": filename}
        if media_id: document["id"] = media_id
        elif media_url: document["link"] = media_url
        if caption: document["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "to": normalize_ar_phone(to),
            "type": "document",
            "document": document,
        }
        return await _post_message(cfg, payload, timeout=30.0)
    except Exception as e:
        print(f"[whatsapp] Error sending document to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    finally:
        _close(own)


async def send_image_message(to: str, caption: str = None, media_url: str = None,
                             media_id: str = None, db: Optional[Session] = None) -> dict | None:
    cfg, own = _config_or_new_session(db)
    try:
        image = {}
        if media_id: image["id"] = media_id
        elif media_url: image["link"] = media_url
        if caption: image["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "to": normalize_ar_phone(to),
            "type": "image",
            "image": image,
        }
        return await _post_message(cfg, payload, timeout=30.0)
    except Exception as e:
        print(f"[whatsapp] Error sending image to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    finally:
        _close(own)


async def send_interactive_list(to: str, header_text: str, body_text: str,
                                sections: list[dict], db: Optional[Session] = None) -> dict | None:
    cfg, own = _config_or_new_session(db)
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": normalize_ar_phone(to),
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header_text},
                "body": {"text": body_text},
                "action": {"button": "Ver opciones", "sections": sections},
            },
        }
        return await _post_message(cfg, payload)
    except httpx.HTTPStatusError as e:
        print(f"[whatsapp] Error sending interactive list to {to}: {e}\n  body: {e.response.text}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    except Exception as e:
        print(f"[whatsapp] Error sending interactive list to {to}: {e}")
        return {"wa_message_id": None, "status": "FAILED", "error": str(e)}
    finally:
        _close(own)


async def upload_media(file_bytes: bytes, mime_type: str, filename: str,
                       db: Optional[Session] = None) -> str | None:
    cfg, own = _config_or_new_session(db)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                _api_url(cfg, "media"),
                headers=_headers(cfg, json=False),
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": (filename, file_bytes, mime_type)},
                timeout=60.0,
            )
            r.raise_for_status()
            return r.json().get("id")
    except Exception as e:
        print(f"[whatsapp] Error uploading media: {e}")
        return None
    finally:
        _close(own)


async def download_media(media_id: str, db: Optional[Session] = None) -> tuple[bytes, str] | None:
    cfg, own = _config_or_new_session(db)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{WA_API_BASE}/{media_id}", headers=_headers(cfg, json=False), timeout=10.0)
            r.raise_for_status()
            media_url = r.json().get("url")
            if not media_url:
                return None
            r2 = await client.get(media_url, headers=_headers(cfg, json=False), timeout=60.0)
            r2.raise_for_status()
            return r2.content, r2.headers.get("content-type", "application/octet-stream")
    except Exception as e:
        print(f"[whatsapp] Error downloading media {media_id}: {e}")
        return None
    finally:
        _close(own)


def verify_webhook_signature(payload: bytes, signature: str, db: Session) -> bool:
    """Verifica la firma HMAC SHA256 del webhook de Meta usando app_secret en DB."""
    try:
        cfg = get_active_config(db)
    except RuntimeError:
        return False
    if not cfg.app_secret:
        return True  # Skip verification si no hay app_secret cargado
    expected = hmac.new(cfg.app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
