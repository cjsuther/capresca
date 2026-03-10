import httpx
from app.config import settings


class NotificationsClient:
    def __init__(self):
        self.base_url = settings.notifications_service_url

    async def notify(self, user_id: int, title: str, message: str,
                     module: str, entity_type: str, entity_id: int,
                     redirect_path: str) -> None:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/internal/notifications",
                    json={
                        "notifications": [{
                            "user_id": user_id,
                            "title": title,
                            "message": message,
                            "module": module,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "redirect_path": redirect_path,
                            "created_by_module": module,
                        }]
                    },
                    timeout=3.0,
                )
        except Exception:
            pass

    async def notify_many(self, notifications: list[dict]) -> None:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/internal/notifications",
                    json={"notifications": notifications},
                    timeout=3.0,
                )
        except Exception:
            pass


notifications_client = NotificationsClient()
