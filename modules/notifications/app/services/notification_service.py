from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate


def create_notifications(db: Session, items: list[NotificationCreate]) -> list[Notification]:
    objs = [Notification(**item.model_dump()) for item in items]
    db.add_all(objs)
    db.commit()
    for obj in objs:
        db.refresh(obj)
    return objs


def get_notifications(db: Session, user_id: int, limit: int = 10, offset: int = 0, unread_only: bool = False):
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    total = q.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()
    data = q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    return data, unread_count, total


def get_unread_count(db: Session, user_id: int) -> int:
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()


def mark_as_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()
    if n and not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n


def mark_all_as_read(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).update({"is_read": True, "read_at": now})
    db.commit()
    return count
