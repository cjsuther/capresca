"""Archivo de alta de cuentas de terceros para Interbanking, desde el lote."""
from datetime import date

from tests.conftest import gateway, pago
from app.services import alta_cuentas, interbanking

CUIT_A, CUIT_B = "20301234563", "27222222228"
CBU_A, CBU_B = "2850590940090418135201", "0110012330001234567891"


def _lote(lote_creditos, **extra):
    return lote_creditos(pagos=[pago("cto-1", 500000, documento=CUIT_A, beneficiario="PÉREZ, Juan José"),
                                pago("cto-2", 300000, cbu=CBU_B, documento=CUIT_B, beneficiario="GOMEZ ANA"),
                                pago("cto-3", 100000, documento=CUIT_A)], **extra)


def _archivo(client, lid, headers, **body):
    return client.post(f"/api/tesoreria/lotes/{lid}/archivo-alta-cuentas", headers=headers, json=body or None)


def test_reproduce_el_ejemplo_de_la_planilla_de_interbanking():
    """El ejemplo que trae la planilla 'UPLOAD DE CUENTAS', carácter por carácter (uso TER)."""
    txt = alta_cuentas.generar([{"cbu": "3220020902000028321808", "cuit": "20116071437", "denominacion": "PEPE"}],
                               "B00220A", date(2022, 7, 21))
    lineas = txt.split("\r\n")
    assert txt.endswith("\r\n") and lineas[-1] == ""
    assert lineas[0] == "1B00220ATERCEROS ALTA        20220721".ljust(200)
    assert lineas[1] == "2322002090200002832180820116071437PEPE".ljust(200)
    assert lineas[2] == "3TER           "
    assert lineas[3] == "5B00220A000001".ljust(200)
    assert [len(x) for x in lineas[:-1]] == [200, 200, 15, 200]


def test_valida_cuit():
    assert alta_cuentas.cuit_valido(CUIT_A) and alta_cuentas.cuit_valido("20116071437")
    assert not alta_cuentas.cuit_valido("20301234569") and not alta_cuentas.cuit_valido("12345678")


def test_archivo_con_todas_las_cuentas_del_lote(client, lote_creditos, teso):
    lid = _lote(lote_creditos)["id"]
    r = _archivo(client, lid, teso)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cuentas"] == 2 and d["omitidas"] == []            # el CBU repetido va una sola vez
    assert d["nombre"].startswith("ALTA_CUENTAS_LOT-") and d["nombre"].endswith(".txt")
    lineas = d["contenido"].split("\r\n")
    assert lineas[0].startswith("1X79555ATERCEROS ALTA        ")
    assert lineas[1].startswith(f"2{CBU_A}{CUIT_A}PEREZ JUAN JOSE ")       # sin acentos ni comas
    assert lineas[3].startswith(f"2{CBU_B}{CUIT_B}GOMEZ ANA ")
    assert lineas[5].startswith("5X79555A000002")
    eventos = client.get(f"/api/tesoreria/lotes/{lid}", headers=teso).json()["eventos"]
    assert eventos[-1]["accion"] == "ARCHIVO_ALTA_CUENTAS" and eventos[-1]["detalle"] == "2 cuenta(s)"


def test_omite_las_cuentas_sin_cuit_valido(client, lote_creditos, teso):
    lid = lote_creditos(pagos=[pago("cto-1", 1000, documento=CUIT_A),
                               pago("cto-2", 1000, cbu=CBU_B, documento="20301234569", beneficiario="GOMEZ ANA")])["id"]
    d = _archivo(client, lid, teso).json()
    assert d["cuentas"] == 1
    assert d["omitidas"] == [{"beneficiario": "GOMEZ ANA", "cbu": CBU_B, "documento": "20301234569",
                              "motivo": "Sin CUIT/CUIL válido"}]
    assert "5X79555A000001" in d["contenido"]


def test_solo_las_cuentas_de_los_pagos_fallidos(client, lote_creditos, teso, banco):
    lid = _lote(lote_creditos)["id"]
    assert _archivo(client, lid, teso, solo_fallidos=True).status_code == 409      # todavía no se envió
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    banco.respuestas = [{"status": "ACREDITADA"}, interbanking.EnvioRechazado("1078 cuenta crédito"),
                        {"status": "ACREDITADA"}]
    client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso)
    d = _archivo(client, lid, teso, solo_fallidos=True).json()
    assert d["cuentas"] == 1 and f"2{CBU_B}{CUIT_B}" in d["contenido"] and CBU_A not in d["contenido"]
    assert "_FALLIDOS_" in d["nombre"]


def test_exige_permiso_de_envio(client, lote_creditos):
    lid = _lote(lote_creditos)["id"]
    assert _archivo(client, lid, gateway("lotes:read", "lotes:write")).status_code == 403
