import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationsClient:
    """Cliente fire-and-forget hacia el módulo de notificaciones.

    Nunca propaga excepciones: una falla al notificar no debe interrumpir el
    flujo de negocio que la originó.
    """

    def __init__(self):
        self.base_url = settings.notifications_service_url

    def notify(self, user_id: int, title: str, message: str, module: str,
               entity_type: str | None = None, entity_id: int | None = None,
               redirect_path: str | None = None) -> None:
        try:
            with httpx.Client() as client:
                client.post(
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
            logger.warning("No se pudo enviar notificación a %s", user_id, exc_info=True)


notifications_client = NotificationsClient()
