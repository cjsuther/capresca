from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.notification import BulkNotificationCreate
from app.services import notification_service

router = APIRouter(tags=["internal"])


@router.post("/internal/notifications", status_code=201)
def create_notifications(data: BulkNotificationCreate, db: Session = Depends(get_db)):
    objs = notification_service.create_notifications(db, data.notifications)
    return {"created": len(objs)}
