import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_current_username
from app.schemas.conversation import (
    ConversationCreate,
    ConversationLinkClient,
    ConversationListResponse,
    ConversationResponse,
)
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services import conversation_service, message_service, whatsapp_service, media_service, clientes_client

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    search: Optional[str] = None,
    status: Optional[str] = None,
    linked: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
):
    data, total = conversation_service.get_conversations(db, search, status, linked, page, per_page)
    return {"data": data, "total": total, "page": page, "per_page": per_page}


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")
    return conv


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Get client info from Clientes module
    client_info = await clientes_client.get_client_by_id(data.client_id)
    client_name = None
    if client_info:
        client_name = client_info.get("client_name")

    conv = conversation_service.get_or_create_conversation(
        db, client_phone=data.phone, client_id=data.client_id, client_name=client_name
    )
    db.commit()
    db.refresh(conv)
    return conv


@router.put("/conversations/{conversation_id}/link-client", response_model=ConversationResponse)
async def link_client_to_conversation(
    conversation_id: int,
    data: ConversationLinkClient,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    client_info = await clientes_client.get_client_by_id(data.client_id)
    if not client_info:
        raise HTTPException(404, "Cliente no encontrado")

    conv = conversation_service.link_client(
        db, conversation_id, data.client_id, client_info.get("client_name", "")
    )
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")
    return conv


@router.put("/conversations/{conversation_id}/read")
def mark_conversation_read(conversation_id: int, db: Session = Depends(get_db)):
    conv = conversation_service.mark_as_read(db, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")
    return {"ok": True}


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(
    conversation_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    conv = conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")
    data, total = message_service.get_messages(db, conversation_id, limit, before_id)
    return {"data": data, "total": total}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    data: MessageCreate,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    conv = conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")

    # Send via WhatsApp
    wa_result = await whatsapp_service.send_text_message(conv.client_phone, data.content)
    wa_message_id = wa_result.get("wa_message_id") if wa_result else None
    wa_status = wa_result.get("status", "FAILED") if wa_result else "FAILED"

    msg = message_service.create_message(
        db,
        conversation_id=conversation_id,
        direction="OUTBOUND",
        message_type="TEXT",
        content=data.content,
        wa_message_id=wa_message_id,
        wa_status=wa_status,
        sent_by_user_id=user_id,
        sent_by_username=username,
    )
    conversation_service.update_last_message(db, conv, data.content)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/conversations/{conversation_id}/messages/media", response_model=MessageResponse)
async def send_media_message(
    conversation_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    conv = conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversacion no encontrada")

    file_bytes = await file.read()
    local_path = media_service.store_outbound_file(file_bytes, conversation_id, file.filename)

    # Upload to WhatsApp and send
    media_id = await whatsapp_service.upload_media(file_bytes, file.content_type, file.filename)
    wa_result = None
    if media_id:
        if file.content_type and file.content_type.startswith("image/"):
            wa_result = await whatsapp_service.send_image_message(conv.client_phone, caption=caption, media_id=media_id)
        else:
            wa_result = await whatsapp_service.send_document_message(
                conv.client_phone, file.filename, caption=caption, media_id=media_id
            )

    wa_message_id = wa_result.get("wa_message_id") if wa_result else None
    wa_status = wa_result.get("status", "FAILED") if wa_result else "FAILED"

    msg_type = "IMAGE" if file.content_type and file.content_type.startswith("image/") else "DOCUMENT"
    preview = caption or f"[{msg_type}: {file.filename}]"

    msg = message_service.create_message(
        db,
        conversation_id=conversation_id,
        direction="OUTBOUND",
        message_type=msg_type,
        content=caption,
        media_mime_type=file.content_type,
        media_filename=file.filename,
        media_local_path=local_path,
        wa_message_id=wa_message_id,
        wa_status=wa_status,
        sent_by_user_id=user_id,
        sent_by_username=username,
    )
    conversation_service.update_last_message(db, conv, preview)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/messages/{message_id}/media")
def get_message_media(message_id: int, db: Session = Depends(get_db)):
    msg = message_service.get_message_by_id(db, message_id)
    if not msg or not msg.media_local_path:
        raise HTTPException(404, "Media no encontrado")
    if not os.path.exists(msg.media_local_path):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(
        msg.media_local_path,
        media_type=msg.media_mime_type or "application/octet-stream",
        filename=msg.media_filename,
    )
