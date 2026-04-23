from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.schemas.message import InternalSendRequest, InternalSendResponse
from app.services import (
    conversation_service,
    message_service,
    whatsapp_service,
    media_service,
    clientes_client,
)

router = APIRouter(tags=["internal"])


@router.post("/internal/comunicacion/send", response_model=InternalSendResponse)
async def internal_send_message(data: InternalSendRequest, db: Session = Depends(get_db)):
    """Endpoint interno para que otros modulos envien mensajes a clientes."""
    phone = data.phone
    client_name = None

    # If no phone provided, look up client's phone
    if not phone:
        client_info = await clientes_client.get_client_by_id(data.client_id)
        if not client_info:
            return {"message_id": 0, "wa_message_id": None, "status": "FAILED_NO_CLIENT"}
        phone = client_info.get("phone")
        client_name = client_info.get("client_name")
        if not phone:
            return {"message_id": 0, "wa_message_id": None, "status": "FAILED_NO_PHONE"}
    else:
        client_info = await clientes_client.get_client_by_id(data.client_id)
        if client_info:
            client_name = client_info.get("client_name")

    conv = conversation_service.get_or_create_conversation(
        db, client_phone=phone, client_id=data.client_id, client_name=client_name
    )

    # Send via WhatsApp
    wa_result = await whatsapp_service.send_text_message(phone, data.message)
    wa_message_id = wa_result.get("wa_message_id") if wa_result else None
    wa_status = wa_result.get("status", "FAILED") if wa_result else "FAILED"

    msg = message_service.create_message(
        db,
        conversation_id=conv.id,
        direction="OUTBOUND",
        message_type=data.message_type,
        content=data.message,
        wa_message_id=wa_message_id,
        wa_status=wa_status,
        sent_by_module=data.sent_by_module,
    )
    conversation_service.update_last_message(db, conv, data.message)
    db.commit()
    db.refresh(msg)

    return {
        "message_id": msg.id,
        "wa_message_id": wa_message_id,
        "status": wa_status,
    }


@router.post("/internal/comunicacion/send-file", response_model=InternalSendResponse)
async def internal_send_file(
    client_id: int = Form(...),
    file: UploadFile = File(...),
    phone: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    sent_by_module: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Endpoint interno para que otros modulos envien archivos a clientes."""
    actual_phone = phone
    client_name = None

    if not actual_phone:
        client_info = await clientes_client.get_client_by_id(client_id)
        if not client_info:
            return {"message_id": 0, "wa_message_id": None, "status": "FAILED_NO_CLIENT"}
        actual_phone = client_info.get("phone")
        client_name = client_info.get("client_name")
        if not actual_phone:
            return {"message_id": 0, "wa_message_id": None, "status": "FAILED_NO_PHONE"}
    else:
        client_info = await clientes_client.get_client_by_id(client_id)
        if client_info:
            client_name = client_info.get("client_name")

    conv = conversation_service.get_or_create_conversation(
        db, client_phone=actual_phone, client_id=client_id, client_name=client_name
    )

    file_bytes = await file.read()
    local_path = media_service.store_outbound_file(file_bytes, conv.id, file.filename)

    # Upload and send via WhatsApp
    media_id = await whatsapp_service.upload_media(file_bytes, file.content_type, file.filename)
    wa_result = None
    if media_id:
        if file.content_type and file.content_type.startswith("image/"):
            wa_result = await whatsapp_service.send_image_message(actual_phone, caption=caption, media_id=media_id)
        else:
            wa_result = await whatsapp_service.send_document_message(
                actual_phone, file.filename, caption=caption, media_id=media_id
            )

    wa_message_id = wa_result.get("wa_message_id") if wa_result else None
    wa_status = wa_result.get("status", "FAILED") if wa_result else "FAILED"

    msg_type = "IMAGE" if file.content_type and file.content_type.startswith("image/") else "DOCUMENT"
    preview = caption or f"[{msg_type}: {file.filename}]"

    msg = message_service.create_message(
        db,
        conversation_id=conv.id,
        direction="OUTBOUND",
        message_type=msg_type,
        content=caption,
        media_mime_type=file.content_type,
        media_filename=file.filename,
        media_local_path=local_path,
        wa_message_id=wa_message_id,
        wa_status=wa_status,
        sent_by_module=sent_by_module,
    )
    conversation_service.update_last_message(db, conv, preview)
    db.commit()
    db.refresh(msg)

    return {
        "message_id": msg.id,
        "wa_message_id": wa_message_id,
        "status": wa_status,
    }
