from sqlalchemy.orm import Session
from app.models.message import Message


def create_message(
    db: Session,
    conversation_id: int,
    direction: str,
    message_type: str,
    content: str | None = None,
    media_url: str | None = None,
    media_mime_type: str | None = None,
    media_filename: str | None = None,
    media_local_path: str | None = None,
    wa_message_id: str | None = None,
    wa_status: str | None = None,
    sent_by_user_id: int | None = None,
    sent_by_username: str | None = None,
    sent_by_module: str | None = None,
    interactive_reply_id: str | None = None,
    interactive_reply_title: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        direction=direction,
        message_type=message_type,
        content=content,
        media_url=media_url,
        media_mime_type=media_mime_type,
        media_filename=media_filename,
        media_local_path=media_local_path,
        wa_message_id=wa_message_id,
        wa_status=wa_status,
        sent_by_user_id=sent_by_user_id,
        sent_by_username=sent_by_username,
        sent_by_module=sent_by_module,
        interactive_reply_id=interactive_reply_id,
        interactive_reply_title=interactive_reply_title,
    )
    db.add(msg)
    db.flush()
    return msg


def get_messages(
    db: Session, conversation_id: int, limit: int = 50, before_id: int | None = None
) -> tuple[list[Message], int]:
    q = db.query(Message).filter(Message.conversation_id == conversation_id)
    total = q.count()
    if before_id:
        q = q.filter(Message.id < before_id)
    data = q.order_by(Message.created_at.desc()).limit(limit).all()
    data.reverse()  # Return in chronological order
    return data, total


def get_message_by_id(db: Session, message_id: int) -> Message | None:
    return db.query(Message).filter(Message.id == message_id).first()


def update_wa_status(db: Session, wa_message_id: str, status: str):
    msg = db.query(Message).filter(Message.wa_message_id == wa_message_id).first()
    if msg:
        msg.wa_status = status
        db.flush()
    return msg
