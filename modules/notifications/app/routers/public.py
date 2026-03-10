from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.notification import NotificationsListResponse, NotificationResponse, UnreadCountResponse
from app.services import notification_service

router = APIRouter(tags=["notifications"])


def get_current_user_id(x_user_id: str = Header(...)) -> int:
    try:
        return int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Header X-User-Id inválido")


@router.get("", response_model=NotificationsListResponse)
def list_notifications(
    limit: int = 10,
    offset: int = 0,
    unread_only: bool = False,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data, unread_count, total = notification_service.get_notifications(db, user_id, limit, offset, unread_only)
    return {"data": data, "unread_count": unread_count, "total": total}


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return {"count": notification_service.get_unread_count(db, user_id)}


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    n = notification_service.mark_as_read(db, notification_id, user_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return n


@router.put("/read-all")
def mark_all_read(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    count = notification_service.mark_all_as_read(db, user_id)
    return {"marked": count}
