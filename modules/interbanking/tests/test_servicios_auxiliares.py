"""Piezas de soporte: cliente de notificaciones (fire-and-forget) y sesión de base."""
import httpx
import pytest

from app.config import settings
from app.db import session as db_session
from app.services import notifications_client as nc


class _ClienteFalso:
    """Reemplaza httpx.Client dentro del cliente de notificaciones."""

    enviados: list = []
    error: Exception | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json=None, timeout=None):
        if _ClienteFalso.error:
            raise _ClienteFalso.error
        _ClienteFalso.enviados.append({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(201, json={"created": 1},
                              request=httpx.Request("POST", url))


@pytest.fixture
def cliente_notificaciones(monkeypatch):
    _ClienteFalso.enviados = []
    _ClienteFalso.error = None
    monkeypatch.setattr(nc.httpx, "Client", _ClienteFalso)
    return _ClienteFalso


def test_la_notificacion_viaja_con_el_shape_que_espera_el_modulo(cliente_notificaciones):
    nc.NotificationsClient().notify(
        user_id=7, title="Transferencia registrada", message="Detalle",
        module="interbanking", entity_type="transfer", entity_id=42,
        redirect_path="/modules/interbanking/transferencias")

    enviado = cliente_notificaciones.enviados[0]
    assert enviado["url"] == f"{settings.notifications_service_url}/internal/notifications"
    assert enviado["timeout"] == 3.0
    assert enviado["json"]["notifications"] == [{
        "user_id": 7, "title": "Transferencia registrada", "message": "Detalle",
        "module": "interbanking", "entity_type": "transfer", "entity_id": 42,
        "redirect_path": "/modules/interbanking/transferencias",
        "created_by_module": "interbanking",
    }]


def test_si_notificaciones_esta_caido_no_se_propaga_el_error(cliente_notificaciones):
    cliente_notificaciones.error = httpx.ConnectError("conexión rechazada")

    # No debe levantar: notificar nunca puede tumbar la operación de negocio.
    nc.NotificationsClient().notify(user_id=7, title="t", message="m", module="interbanking")

    assert cliente_notificaciones.enviados == []


def test_get_db_entrega_una_sesion_y_la_cierra():
    generador = db_session.get_db()
    sesion = next(generador)
    assert sesion.is_active
    with pytest.raises(StopIteration):
        next(generador)
