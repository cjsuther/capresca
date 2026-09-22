"""Tests del cliente HTTP hacia el módulo legacy (sin red) y del seed de demo."""
import asyncio

import httpx
import pytest

from app.services import legacy_client


class _RespuestaFalsa:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._data


class _ClienteFalso:
    """Reemplazo de httpx.AsyncClient: registra la llamada y no toca la red."""

    llamadas = []
    respuesta = None
    excepcion = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None, timeout=None):
        type(self).llamadas.append({"url": url, "params": params, "headers": headers,
                                    "timeout": timeout})
        if type(self).excepcion:
            raise type(self).excepcion
        return type(self).respuesta


@pytest.fixture
def legacy_falso(monkeypatch):
    _ClienteFalso.llamadas = []
    _ClienteFalso.respuesta = _RespuestaFalsa([])
    _ClienteFalso.excepcion = None
    monkeypatch.setattr(httpx, "AsyncClient", _ClienteFalso)
    return _ClienteFalso


def test_agencias_del_legacy(legacy_falso):
    legacy_falso.respuesta = _RespuestaFalsa([{"nroage": "001", "nombre": "El Dorado"}])
    resultado = asyncio.run(legacy_client.get_agencias())

    assert resultado == [{"nroage": "001", "nombre": "El Dorado"}]
    # La URL y la API key salen de la config del módulo (el entorno puede definirlas).
    from app.config import settings

    llamada = legacy_falso.llamadas[0]
    assert llamada["url"] == f"{settings.legacy_service_url}/internal/legacy/agencias"
    assert llamada["params"] is None
    assert llamada["headers"] == {"X-Api-Key": settings.legacy_internal_api_key}
    assert llamada["timeout"] == 8.0


def test_maeclientes_sin_filtro_no_manda_params(legacy_falso):
    legacy_falso.respuesta = _RespuestaFalsa([{"cuil": "20304050"}])
    resultado = asyncio.run(legacy_client.get_maeclientes())

    assert resultado == [{"cuil": "20304050"}]
    assert legacy_falso.llamadas[0]["params"] is None


def test_maeclientes_filtra_por_cuil(legacy_falso):
    legacy_falso.respuesta = _RespuestaFalsa([])
    asyncio.run(legacy_client.get_maeclientes(cuil="20-30304050-3"))
    assert legacy_falso.llamadas[0]["params"] == {"cuil": "20-30304050-3"}


def test_legacy_caido_degrada_a_lista_vacia(legacy_falso):
    """Degradación elegante: si el legacy no responde, no rompe al llamador."""
    legacy_falso.excepcion = httpx.ConnectError("connection refused")
    assert asyncio.run(legacy_client.get_agencias()) == []
    assert asyncio.run(legacy_client.get_maeclientes(cuil="x")) == []


def test_legacy_con_error_http_degrada_a_lista_vacia(legacy_falso):
    legacy_falso.respuesta = _RespuestaFalsa(None, status_code=500)
    assert asyncio.run(legacy_client.get_agencias()) == []


def test_legacy_con_timeout_degrada_a_lista_vacia(legacy_falso):
    legacy_falso.excepcion = httpx.ReadTimeout("timeout")
    assert asyncio.run(legacy_client.get_maeclientes()) == []


# ── Seed de demo ────────────────────────────────────────────────
def test_seed_demo_carga_las_agencias_y_es_idempotente(client, db, monkeypatch, capsys):
    from app import seed_demo

    # El seed abre su propia sesión: la apuntamos a la de test (SQLite en memoria).
    monkeypatch.setattr(seed_demo, "SessionLocal", lambda: db)
    seed_demo.run()

    agencias = client.get("/internal/clientes/agencies").json()
    assert len(agencias) == len(seed_demo.AGENCIES)
    assert {a["agency_number"] for a in agencias} == {a["agency_number"] for a in seed_demo.AGENCIES}
    # la agencia A003 del seed trae dos CBUs
    a003 = next(a for a in agencias if a["agency_number"] == "A003")
    assert len(a003["cbus"]) == 2

    # segunda corrida: no duplica nada
    capsys.readouterr()
    seed_demo.run()
    assert "ya existe" in capsys.readouterr().out
    assert len(client.get("/internal/clientes/agencies").json()) == len(seed_demo.AGENCIES)


def test_seed_demo_aborta_si_falla_la_carga(monkeypatch):
    from app import seed_demo

    class _SesionRota:
        def query(self, *a, **kw):
            raise RuntimeError("base caída")

        def rollback(self):
            self.rollback_llamado = True

        def close(self):
            self.close_llamado = True

    rota = _SesionRota()
    monkeypatch.setattr(seed_demo, "SessionLocal", lambda: rota)

    with pytest.raises(SystemExit) as exc:
        seed_demo.run()
    assert exc.value.code == 1
    assert rota.rollback_llamado is True
    assert rota.close_llamado is True
