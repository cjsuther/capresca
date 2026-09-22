"""Clientes HTTP hacia los otros módulos. Nada sale a la red: se falsea httpx."""
import asyncio
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.models.batch import LiquidacionBatch
from app.models.procesada import LiquidacionProcesada
from app.services import clientes_client, conciliacion_client, legacy_client
from app.services import notifications_client as notif_mod


class RespuestaFalsa:
    def __init__(self, datos=None, error=None):
        self._datos = datos
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._datos


class ClienteFalso:
    """Doble de httpx.Client/AsyncClient que registra las llamadas."""

    llamadas = []
    respuesta = RespuestaFalsa([])
    explota = None

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _registrar(self, metodo, url, **kw):
        type(self).llamadas.append({"metodo": metodo, "url": url, **kw})
        if type(self).explota:
            raise type(self).explota
        return type(self).respuesta

    def get(self, url, **kw):
        return self._registrar("GET", url, **kw)

    def post(self, url, **kw):
        return self._registrar("POST", url, **kw)


@pytest.fixture
def http(monkeypatch):
    """Instala el doble de httpx.Client (los tres clientes comparten el módulo httpx)."""
    class Doble(ClienteFalso):
        llamadas = []
        respuesta = RespuestaFalsa([])
        explota = None

    monkeypatch.setattr(httpx, "Client", Doble)
    return Doble


# ───────────────────────── clientes ─────────────────────────

def test_pide_las_agencias_registradas_al_modulo_clientes(http):
    http.respuesta = RespuestaFalsa([{"agency_number": "000123"}, {"agency_number": "000456"},
                                     {"agency_number": None}, {}])
    agencias = clientes_client.get_registered_agency_numbers()

    assert agencias == {"000123", "000456"}   # descarta los vacíos
    assert http.llamadas[0]["url"].endswith("/internal/clientes/agencies")
    assert "clientes-test" in http.llamadas[0]["url"]


def test_si_clientes_responde_con_error_la_excepcion_sube(http):
    http.respuesta = RespuestaFalsa(error=httpx.HTTPStatusError(
        "500", request=None, response=None))
    with pytest.raises(httpx.HTTPStatusError):
        clientes_client.get_registered_agency_numbers()


def test_si_clientes_esta_caido_la_excepcion_sube(http):
    http.explota = httpx.ConnectError("sin ruta al host")
    with pytest.raises(httpx.ConnectError):
        clientes_client.get_registered_agency_numbers()


# ───────────────────────── conciliación ─────────────────────────

def _lote_con_procesadas(db):
    lote = LiquidacionBatch(zip_filename="LIQ.zip", status="VALIDADO", created_by=7,
                            operation_date=date(2025, 3, 15), resumen_number="777")
    db.add(lote)
    db.flush()
    for i, (agen, total, premios) in enumerate([("000123", "1000.00", "200.00"),
                                                ("000123", "500.00", "0.00"),
                                                ("000456", "300.00", "0.00")]):
        db.add(LiquidacionProcesada(batch_id=lote.id, n_agen=agen, c_juego=7, n_sorteo=i,
                                    modalidad=0, moneda="$", recaudacion="10.00",
                                    premios=premios, comision="5.00", fdo_gtia="0",
                                    ing_brutos="0", debitos="0", creditos="0", total=total,
                                    no_recibo=1))
    db.commit()
    return lote


def test_envia_a_conciliacion_los_totales_agregados_por_agencia(http, db):
    lote = _lote_con_procesadas(db)
    conciliacion_client.send_to_conciliacion(db, lote)

    llamada = http.llamadas[0]
    assert llamada["url"].endswith("/internal/conciliacion/liquidaciones")
    payload = llamada["json"]
    assert payload["batch_id"] == lote.id and payload["created_by"] == 7
    assert payload["operation_date"] == "2025-03-15"

    por_agencia = {a["agency_number"]: a for a in payload["agencies"]}
    assert set(por_agencia) == {"000123", "000456"}
    assert por_agencia["000123"]["importe_adeudado"] == 1300.0   # (1000-200) + (500-0)
    assert por_agencia["000123"]["importe_premios"] == 200.0
    assert por_agencia["000123"]["recaudacion_total"] == 20.0
    assert por_agencia["000123"]["comision_total"] == 10.0
    assert por_agencia["000123"]["resumen_number"] == "777"
    assert por_agencia["000123"]["batch_source"] == "liquidaciones"


def test_lote_sin_fecha_de_operacion_viaja_con_null(http, db):
    lote = LiquidacionBatch(zip_filename="LIQ.zip", status="VALIDADO", created_by=7)
    db.add(lote)
    db.commit()
    conciliacion_client.send_to_conciliacion(db, lote)
    assert http.llamadas[0]["json"]["operation_date"] is None
    assert http.llamadas[0]["json"]["agencies"] == []


def test_si_conciliacion_responde_error_la_excepcion_sube(http, db):
    http.respuesta = RespuestaFalsa(error=httpx.HTTPStatusError("503", request=None,
                                                                response=None))
    lote = _lote_con_procesadas(db)
    with pytest.raises(httpx.HTTPStatusError):
        conciliacion_client.send_to_conciliacion(db, lote)


# ───────────────────────── notificaciones ─────────────────────────

def test_la_notificacion_viaja_con_el_sobre_que_espera_el_modulo(http):
    cliente = notif_mod.NotificationsClient()
    cliente.notify(user_id=7, title="Liquidación procesada", message="ok",
                   module="liquidaciones", entity_type="batch", entity_id=5,
                   redirect_path="/modules/liquidaciones/batches/5")

    llamada = http.llamadas[0]
    assert llamada["url"].endswith("/internal/notifications")
    (n,) = llamada["json"]["notifications"]
    assert n["user_id"] == 7 and n["entity_id"] == 5
    assert n["created_by_module"] == "liquidaciones"


def test_si_notifications_esta_caido_no_rompe_el_flujo(http):
    http.explota = httpx.ConnectError("notifications caído")
    # No debe propagar: notificar es fire-and-forget.
    notif_mod.NotificationsClient().notify(user_id=7, title="t", message="m",
                                           module="liquidaciones")


# ───────────────────────── legacy (degradación elegante) ─────────────────────────

class AsyncClienteFalso:
    ultima = None
    respuesta = None
    explota = None

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        type(self).ultima = {"url": url, **kw}
        if type(self).explota:
            raise type(self).explota
        return type(self).respuesta


@pytest.fixture
def http_async(monkeypatch):
    class Doble(AsyncClienteFalso):
        ultima = None
        respuesta = RespuestaFalsa([])
        explota = None

    monkeypatch.setattr(legacy_client.httpx, "AsyncClient", Doble)
    return Doble


def test_trae_los_juegos_del_legacy(http_async):
    http_async.respuesta = RespuestaFalsa([{"c_juego": 7, "d_juego": "QUINIELA"}])
    juegos = asyncio.run(legacy_client.get_juegos())

    assert juegos == [{"c_juego": 7, "d_juego": "QUINIELA"}]
    assert http_async.ultima["url"].endswith("/internal/legacy/juegos")
    assert http_async.ultima["headers"]["X-Api-Key"] == "clave-legacy-test"


def test_cajaliq_arma_los_filtros_como_query_params(http_async):
    http_async.respuesta = RespuestaFalsa([{"agencia": "000123"}])
    asyncio.run(legacy_client.get_cajaliq(agencia="000123", pagado=False))
    assert http_async.ultima["params"] == {"agencia": "000123", "pagado": "false"}


def test_cajaliq_sin_filtros_no_manda_params(http_async):
    asyncio.run(legacy_client.get_cajaliq())
    assert http_async.ultima["params"] is None


def test_legacy_caido_devuelve_vacio_en_vez_de_romper(http_async):
    http_async.explota = httpx.ConnectError("legacy apagado")
    assert asyncio.run(legacy_client.get_juegos()) == []
    assert asyncio.run(legacy_client.get_cajaliq(agencia="000123")) == []


def test_legacy_con_error_http_tambien_degrada(http_async):
    http_async.respuesta = RespuestaFalsa(error=httpx.HTTPStatusError("500", request=None,
                                                                      response=None))
    assert asyncio.run(legacy_client.get_juegos()) == []
