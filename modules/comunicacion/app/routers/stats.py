from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.whatsapp import StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    total_conversations = db.query(sa_func.count(Conversation.id)).scalar() or 0
    active_conversations = (
        db.query(sa_func.count(Conversation.id))
        .filter(Conversation.status == "ACTIVE")
        .scalar() or 0
    )
    unlinked_conversations = (
        db.query(sa_func.count(Conversation.id))
        .filter(Conversation.client_id.is_(None))
        .scalar() or 0
    )

    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    messages_today = (
        db.query(sa_func.count(Message.id))
        .filter(Message.created_at >= today_start)
        .scalar() or 0
    )

    unread_total = (
        db.query(sa_func.coalesce(sa_func.sum(Conversation.unread_count), 0)).scalar() or 0
    )

    return {
        "total_conversations": total_conversations,
        "active_conversations": active_conversations,
        "unlinked_conversations": unlinked_conversations,
        "messages_today": messages_today,
        "unread_total": int(unread_total),
    }
