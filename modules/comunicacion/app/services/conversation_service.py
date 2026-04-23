from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from app.models.conversation import Conversation


def get_conversations(
    db: Session,
    search: str | None = None,
    status: str | None = None,
    linked: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Conversation], int]:
    q = db.query(Conversation)

    if status:
        q = q.filter(Conversation.status == status)
    if linked == "true":
        q = q.filter(Conversation.client_id.isnot(None))
    elif linked == "false":
        q = q.filter(Conversation.client_id.is_(None))
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (Conversation.client_name.ilike(pattern))
            | (Conversation.client_phone.ilike(pattern))
        )

    total = q.count()
    data = (
        q.order_by(Conversation.last_message_at.desc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return data, total


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def get_or_create_conversation(
    db: Session, client_phone: str, client_id: int | None = None, client_name: str | None = None
) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.client_phone == client_phone).first()
    if conv:
        # Update client info if we now have it and didn't before
        if client_id and not conv.client_id:
            conv.client_id = client_id
            conv.client_name = client_name
            db.flush()
        if conv.status == "CLOSED":
            conv.status = "ACTIVE"
            db.flush()
        return conv

    conv = Conversation(
        client_id=client_id,
        client_name=client_name,
        client_phone=client_phone,
        status="ACTIVE",
        unread_count=0,
    )
    db.add(conv)
    db.flush()
    return conv


def link_client(db: Session, conversation_id: int, client_id: int, client_name: str) -> Conversation | None:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        return None
    conv.client_id = client_id
    conv.client_name = client_name
    db.commit()
    db.refresh(conv)
    return conv


def update_last_message(db: Session, conv: Conversation, preview: str, increment_unread: bool = False):
    conv.last_message_at = datetime.now(timezone.utc)
    conv.last_message_preview = preview[:255] if preview else None
    if increment_unread:
        conv.unread_count = (conv.unread_count or 0) + 1
    db.flush()


def mark_as_read(db: Session, conversation_id: int):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.unread_count = 0
        db.commit()
    return conv
