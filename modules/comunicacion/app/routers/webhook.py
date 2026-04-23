from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db
from app.services import (
    conversation_service,
    message_service,
    whatsapp_service,
    menu_service,
    media_service,
    clientes_client,
)

router = APIRouter(tags=["webhook"])


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """Verificacion del webhook requerida por Meta."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.whatsapp_webhook_verify_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Recibe mensajes entrantes y status updates de WhatsApp."""
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not whatsapp_service.verify_webhook_signature(body, signature):
        return Response(status_code=403)

    payload = await request.json()
    print(f"[webhook] Payload keys: {list(payload.keys())}")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            print(f"[webhook] value keys: {list(value.keys())}")

            # Process status updates
            for status_update in value.get("statuses", []):
                _process_status_update(db, status_update)

            # Process incoming messages
            messages_list = value.get("messages", [])
            print(f"[webhook] messages count: {len(messages_list)}")
            for wa_message in messages_list:
                contacts = value.get("contacts", [])
                try:
                    await _process_incoming_message(db, wa_message, contacts)
                    print(f"[webhook] Message processed OK: {wa_message.get('id')}")
                except Exception as e:
                    print(f"[webhook] Error processing message: {e}")
                    import traceback
                    traceback.print_exc()

    db.commit()
    return {"status": "ok"}


def _process_status_update(db: Session, status_update: dict):
    """Actualiza el estado de entrega de un mensaje."""
    wa_message_id = status_update.get("id")
    status = status_update.get("status", "").upper()
    status_map = {"sent": "SENT", "delivered": "DELIVERED", "read": "READ", "failed": "FAILED"}
    mapped = status_map.get(status.lower())
    if wa_message_id and mapped:
        message_service.update_wa_status(db, wa_message_id, mapped)


async def _process_incoming_message(db: Session, wa_message: dict, contacts: list):
    """Procesa un mensaje entrante de WhatsApp."""
    phone = wa_message.get("from", "")
    wa_message_id = wa_message.get("id")
    msg_type = wa_message.get("type", "text")

    # Look up or create conversation
    client_info = await clientes_client.get_client_by_phone(phone)
    client_id = client_info.get("client_id") if client_info else None
    client_name = client_info.get("client_name") if client_info else None

    # Use contact name from WhatsApp as fallback
    if not client_name and contacts:
        wa_profile = contacts[0].get("profile", {})
        client_name = wa_profile.get("name")

    conv = conversation_service.get_or_create_conversation(db, phone, client_id, client_name)

    # Extract message content
    content = None
    media_url = None
    media_mime_type = None
    media_filename = None
    media_local_path = None
    interactive_reply_id = None
    interactive_reply_title = None
    message_type = "TEXT"

    if msg_type == "text":
        content = wa_message.get("text", {}).get("body", "")
        message_type = "TEXT"

    elif msg_type in ("image", "document", "audio", "video"):
        message_type = msg_type.upper()
        media_data = wa_message.get(msg_type, {})
        media_id = media_data.get("id")
        media_mime_type = media_data.get("mime_type")
        media_filename = media_data.get("filename", f"{msg_type}_{wa_message_id}")
        content = media_data.get("caption")

        if media_id:
            media_local_path = await media_service.download_and_store_inbound(
                media_id, conv.id, wa_message_id, media_filename
            )

    elif msg_type == "interactive":
        interactive = wa_message.get("interactive", {})
        reply_type = interactive.get("type")
        if reply_type == "list_reply":
            reply = interactive.get("list_reply", {})
            interactive_reply_id = reply.get("id")
            interactive_reply_title = reply.get("title")
            content = interactive_reply_title
            message_type = "INTERACTIVE"
        elif reply_type == "button_reply":
            reply = interactive.get("button_reply", {})
            interactive_reply_id = reply.get("id")
            interactive_reply_title = reply.get("title")
            content = interactive_reply_title
            message_type = "INTERACTIVE"

    # Save the inbound message
    msg = message_service.create_message(
        db,
        conversation_id=conv.id,
        direction="INBOUND",
        message_type=message_type,
        content=content,
        media_url=media_url,
        media_mime_type=media_mime_type,
        media_filename=media_filename,
        media_local_path=media_local_path,
        wa_message_id=wa_message_id,
        wa_status="RECEIVED",
        interactive_reply_id=interactive_reply_id,
        interactive_reply_title=interactive_reply_title,
    )

    preview = content or f"[{message_type}]"
    conversation_service.update_last_message(db, conv, preview, increment_unread=True)

    # Handle interactive reply (menu selection)
    if interactive_reply_id:
        response_text = await menu_service.process_menu_reply(db, conv, interactive_reply_id)
        if response_text:
            wa_result = await whatsapp_service.send_text_message(phone, response_text)
            message_service.create_message(
                db,
                conversation_id=conv.id,
                direction="OUTBOUND",
                message_type="TEXT",
                content=response_text,
                wa_message_id=wa_result.get("wa_message_id") if wa_result else None,
                wa_status=wa_result.get("status", "FAILED") if wa_result else "FAILED",
                sent_by_module="comunicacion",
            )
            conversation_service.update_last_message(db, conv, response_text)

    # Handle greeting → send interactive menu
    elif msg_type == "text" and content and menu_service.is_greeting(content):
        menu_result = await menu_service.send_interactive_menu(db, phone, conv)
        if menu_result and menu_result.get("wa_message_id"):
            message_service.create_message(
                db,
                conversation_id=conv.id,
                direction="OUTBOUND",
                message_type="INTERACTIVE",
                content="[Menu interactivo enviado]",
                wa_message_id=menu_result.get("wa_message_id"),
                wa_status=menu_result.get("status", "FAILED"),
                sent_by_module="comunicacion",
            )
            conversation_service.update_last_message(db, conv, "[Menu interactivo]")
