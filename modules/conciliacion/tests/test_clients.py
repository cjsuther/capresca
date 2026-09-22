"""Clientes HTTP hacia los módulos vecinos: respuesta feliz y degradación si están caídos.

Acá se ejercitan las funciones REALES (las de `reales`), con `httpx` falseado:
ningún test toca la red.
"""
import asyncio

import pytest

from app.config import settings
from conftest import RespuestaFalsa, cae


def ok(data):
    return lambda metodo, url, kw: RespuestaFalsa(data)


def con_estado(status):
    return lambda metodo, url, kw: RespuestaFalsa(None, status_code=status)


# ─────────────────────────────────────────────────────────────────────────────
# clientes
# ─────────────────────────────────────────────────────────────────────────────
def test_listado_de_agencias(http_falso, reales):
    llamadas = http_falso(ok([{"client_id": 1, "agency_number": "A001"}]))

    resultado = asyncio.run(reales["clientes.get_agencies"]())

    assert resultado == [{"client_id": 1, "agency_number": "A001"}]
    assert llamadas[0]["url"] == f"{settings.clientes_service_url}/internal/clientes/agencies"


def test_clientes_caido_devuelve_lista_vacia(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["clientes.get_agencies"]()) == []


def test_clientes_con_error_500_devuelve_lista_vacia(http_falso, reales):
    http_falso(con_estado(500))
    assert asyncio.run(reales["clientes.get_agencies"]()) == []


def test_buscar_agencia_por_cbu(http_falso, reales):
    http_falso(ok({"client_id": 3}))
    assert asyncio.run(reales["clientes.get_agency_by_cbu"]("072...")) == {"client_id": 3}


def test_buscar_agencia_por_cbu_inexistente_devuelve_none(http_falso, reales):
    http_falso(con_estado(404))
    assert asyncio.run(reales["clientes.get_agency_by_cbu"]("072...")) is None


def test_buscar_agencia_por_cbu_con_el_servicio_caido_devuelve_none(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["clientes.get_agency_by_cbu"]("072...")) is None


# ─────────────────────────────────────────────────────────────────────────────
# interbanking
# ─────────────────────────────────────────────────────────────────────────────
def test_transacciones_del_dia(http_falso, reales):
    llamadas = http_falso(ok([{"id": 1, "type": "transfer"}]))

    resultado = asyncio.run(reales["ib.get_transactions"]("2026-03-10"))

    assert resultado == [{"id": 1, "type": "transfer"}]
    assert llamadas[0]["params"] == {"date": "2026-03-10"}


def test_interbanking_caido_devuelve_sin_transacciones(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["ib.get_transactions"]("2026-03-10")) == []


@pytest.mark.parametrize("clave", ["ib.get_consolidation_account", "ib.get_payment_account"])
def test_cuentas_configuradas(http_falso, reales, clave):
    http_falso(ok({"account_number": "123456"}))
    assert asyncio.run(reales[clave]()) == {"account_number": "123456"}


@pytest.mark.parametrize("clave", ["ib.get_consolidation_account", "ib.get_payment_account"])
def test_cuentas_configuradas_con_el_servicio_caido(http_falso, reales, clave):
    http_falso(cae)
    assert asyncio.run(reales[clave]()) is None


def test_movimientos_arman_los_parametros_de_la_cuenta(http_falso, reales):
    llamadas = http_falso(ok([{"id": 7}]))
    cuenta = {"account_number": "123456", "account_type": "CA",
              "bank_number": "072", "currency": "USD"}

    resultado = asyncio.run(reales["ib.get_movements"]("2026-03-10", cuenta))

    assert resultado == [{"id": 7}]
    assert llamadas[0]["params"] == {"date": "2026-03-10", "account_number": "123456",
                                     "account-type": "CA", "bank-number": "072",
                                     "currency": "USD"}


def test_movimientos_usan_valores_por_defecto_de_cuenta(http_falso, reales):
    llamadas = http_falso(ok([]))
    asyncio.run(reales["ib.get_movements"]("2026-03-10", {"account_number": "999"}))
    assert llamadas[0]["params"]["account-type"] == "CC"
    assert llamadas[0]["params"]["bank-number"] == "011"
    assert llamadas[0]["params"]["currency"] == "ARS"


@pytest.mark.parametrize("cuenta", [None, {}, {"account_number": None}])
def test_sin_numero_de_cuenta_no_se_piden_movimientos(http_falso, reales, cuenta):
    llamadas = http_falso(ok([]))
    assert asyncio.run(reales["ib.get_movements"]("2026-03-10", cuenta)) == []
    assert llamadas == []


def test_movimientos_con_el_servicio_caido(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["ib.get_movements"]("2026-03-10", {"account_number": "1"})) == []


def test_ejecutar_un_pago_devuelve_la_transferencia(http_falso, reales):
    llamadas = http_falso(ok({"id": 555}))

    resultado = asyncio.run(reales["ib.create_payment"]("072...", 1500.0, "Pago Capresca"))

    assert resultado == {"id": 555}
    assert llamadas[0]["json"] == {"cbu_destino": "072...", "monto": 1500.0,
                                   "concepto": "Pago Capresca"}


def test_un_pago_fallido_propaga_el_error(http_falso, reales):
    """A diferencia de las lecturas, el pago NO degrada en silencio: debe explotar."""
    http_falso(cae)
    with pytest.raises(Exception):
        asyncio.run(reales["ib.create_payment"]("072...", 1500.0, "Pago Capresca"))


# ─────────────────────────────────────────────────────────────────────────────
# legacy (capa anti-corrupción opcional)
# ─────────────────────────────────────────────────────────────────────────────
def test_lecturas_del_legacy(http_falso, reales):
    llamadas = http_falso(ok([{"agencia": "A001"}]))

    assert asyncio.run(reales["legacy.get_agencias"]()) == [{"agencia": "A001"}]
    assert asyncio.run(reales["legacy.get_pagos"]("2026-03-10", "A001")) == [{"agencia": "A001"}]
    assert asyncio.run(reales["legacy.get_formas_pago"](12)) == [{"agencia": "A001"}]
    assert asyncio.run(reales["legacy.get_creditos_seguros"]("2026-03-10")) == [{"agencia": "A001"}]
    assert asyncio.run(reales["legacy.get_creditos_seguros"]()) == [{"agencia": "A001"}]

    assert llamadas[1]["params"] == {"fecha": "2026-03-10", "agencia": "A001"}
    assert llamadas[2]["params"] == {"no_recibo": 12}
    assert llamadas[4]["params"] is None
    assert llamadas[0]["headers"]["X-Api-Key"] == settings.legacy_internal_api_key


def test_el_legacy_apagado_degrada_a_vacio(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["legacy.get_agencias"]()) == []
    assert asyncio.run(reales["legacy.get_pagos"]()) == []


def test_escrituras_al_legacy_van_al_outbox(http_falso, reales):
    llamadas = http_falso(ok({"outbox_id": 4}))

    assert asyncio.run(reales["legacy.enqueue_aplicar_pago"]({"monto": 10}, user_id=7)) == \
        {"outbox_id": 4}
    assert asyncio.run(reales["legacy.enqueue_anular_pago"](33, "error de carga")) == \
        {"outbox_id": 4}

    assert llamadas[0]["headers"]["X-Origin-Module"] == "conciliacion"
    assert llamadas[0]["headers"]["X-User-Id"] == "7"
    assert "X-User-Id" not in llamadas[1]["headers"]
    assert llamadas[1]["json"] == {"motivo": "error de carga"}


def test_una_escritura_al_legacy_caido_devuelve_none(http_falso, reales):
    http_falso(cae)
    assert asyncio.run(reales["legacy.enqueue_aplicar_pago"]({"monto": 10})) is None


# ─────────────────────────────────────────────────────────────────────────────
# notificaciones (fire-and-forget)
# ─────────────────────────────────────────────────────────────────────────────
def test_la_notificacion_arma_el_payload_del_modulo(http_falso, reales):
    llamadas = http_falso(ok({"created": 1}))

    reales["notif.notify"](user_id=7, title="Hola", message="m", module="conciliacion",
                           entity_type="liquidacion_batch", entity_id=42,
                           redirect_path="/modules/conciliacion")

    enviado = llamadas[0]["json"]["notifications"][0]
    assert enviado["user_id"] == 7 and enviado["created_by_module"] == "conciliacion"
    assert enviado["entity_id"] == 42
    assert llamadas[0]["url"] == f"{settings.notifications_service_url}/internal/notifications"


def test_si_notificaciones_esta_caido_no_se_propaga_el_error(http_falso, reales):
    http_falso(cae)
    reales["notif.notify"](user_id=7, title="Hola", message="m", module="conciliacion")
