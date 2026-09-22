"""Cliente HTTP hacia notifications: arma el payload y nunca propaga errores de red."""
import httpx
import pytest

from app.services import notifications_client as modulo


class _RespuestaFalsa:
    status_code = 204


class _ClienteFalso:
    """Reemplaza httpx.AsyncClient: registra los POST en vez de salir a la red."""

    def __init__(self, registro, explota=False):
        self._registro = registro
        self._explota = explota

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, timeout=None):
        if self._explota:
            raise httpx.ConnectError("notifications caído")
        self._registro.append({"url": url, "json": json, "timeout": timeout})
        return _RespuestaFalsa()


@pytest.fixture
def httpx_falso(monkeypatch):
    registro = []

    def _fabrica(*a, **kw):
        return _ClienteFalso(registro)

    monkeypatch.setattr(modulo.httpx, "AsyncClient", _fabrica)
    return registro


@pytest.mark.anyio
async def test_notify_arma_una_notificacion_con_el_formato_de_notifications(httpx_falso):
    cliente = modulo.NotificationsClient()
    await cliente.notify(user_id=7, title="Transacción autorizada", message="detalle",
                         module="cajeros", entity_type="transaction", entity_id=3,
                         redirect_path="/modules/cajeros/transactions/3")

    assert len(httpx_falso) == 1
    llamada = httpx_falso[0]
    assert llamada["url"].endswith("/internal/notifications")
    assert llamada["timeout"] == 3.0
    (notif,) = llamada["json"]["notifications"]
    assert notif["user_id"] == 7 and notif["entity_id"] == 3
    assert notif["created_by_module"] == "cajeros"


@pytest.mark.anyio
async def test_notify_many_manda_el_lote_tal_cual(httpx_falso):
    cliente = modulo.NotificationsClient()
    lote = [{"user_id": 1, "title": "a"}, {"user_id": 2, "title": "b"}]
    await cliente.notify_many(lote)
    assert httpx_falso[0]["json"] == {"notifications": lote}


@pytest.mark.anyio
async def test_un_notifications_caido_no_rompe_la_operacion(monkeypatch):
    monkeypatch.setattr(modulo.httpx, "AsyncClient", lambda *a, **kw: _ClienteFalso([], explota=True))
    cliente = modulo.NotificationsClient()
    # Fire-and-forget: los errores se tragan a propósito.
    await cliente.notify(user_id=1, title="t", message="m", module="cajeros",
                         entity_type="transaction", entity_id=1, redirect_path="/x")
    await cliente.notify_many([{"user_id": 1}])


def test_la_url_base_sale_de_la_config():
    assert modulo.NotificationsClient().base_url == modulo.settings.notifications_service_url
