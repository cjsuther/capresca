"""Clasificación de códigos FoxPro y armado de los registros procesados."""
from datetime import date
from decimal import Decimal

import pytest

from app.services.processing import (
    _extract_operation_date, _extract_resumen_number, _parse_date, aggregate_details,
)
from factories import detalle


def _uno(**kwargs):
    """Agrega un único registro de detalle y devuelve el grupo resultante."""
    return aggregate_details([detalle(**kwargs)])[0]


@pytest.mark.parametrize("codigo,campo,signo_campo,signo_total", [
    ("1", "recaudacion", 1, 1),      # recaudación
    ("581", "recaudacion", -1, -1),  # anulación de recaudación
    ("3", "ing_brutos", 1, 1),
    ("583", "ing_brutos", -1, -1),
    ("550", "comision", 1, -1),      # la comisión se descuenta del total
    ("30", "comision", -1, 1),
    ("23", "fdo_gtia", 1, 1),
    ("24", "debitos", 1, 1),
    ("99", "debitos", 1, 1),         # código suelto < 500 → débito
    ("777", "creditos", 1, -1),      # código suelto >= 500 → crédito
])
def test_cada_codigo_impacta_en_su_columna(codigo, campo, signo_campo, signo_total):
    g = _uno(c_codigo=codigo, c_juego="7", importe="100.00")
    assert g[campo] == Decimal("100.00") * signo_campo
    assert g["total"] == Decimal("100.00") * signo_total


@pytest.mark.parametrize("codigo", ["551", "570"])
def test_los_premios_suman_aparte_y_no_tocan_el_total(codigo):
    g = _uno(c_codigo=codigo, importe="250.00")
    assert g["premios"] == Decimal("250.00")
    assert g["total"] == Decimal("0")


def test_juego_50_codigo_43_es_recaudacion_y_marca_modalidad():
    g = _uno(c_juego="50", c_codigo="43", d_codigo="TELEKINO", importe="80.00")
    assert g["modalidad"] == 43
    assert g["recaudacion"] == Decimal("80.00") and g["total"] == Decimal("80.00")
    assert g["d_juego"] == "TELEKINO"   # el d_juego se pisa con la descripción del código


def test_codigo_43_en_otro_juego_cae_como_debito():
    g = _uno(c_juego="7", c_codigo="43", importe="80.00")
    assert g["modalidad"] == 0 and g["debitos"] == Decimal("80.00")


def test_agrupa_por_agencia_juego_y_sorteo():
    filas = aggregate_details([
        detalle(n_agen="000123", c_juego="7", n_sorteo="1", c_codigo="1", importe="100.00"),
        detalle(n_agen="000123", c_juego="7", n_sorteo="1", c_codigo="550", importe="10.00"),
        detalle(n_agen="000123", c_juego="7", n_sorteo="2", c_codigo="1", importe="50.00"),
        detalle(n_agen="000456", c_juego="7", n_sorteo="1", c_codigo="1", importe="70.00"),
    ])
    assert len(filas) == 3
    primero = [f for f in filas if f["n_agen"] == "000123" and f["n_sorteo"] == 1][0]
    assert primero["recaudacion"] == Decimal("100.00")
    assert primero["comision"] == Decimal("10.00")
    assert primero["total"] == Decimal("90.00")


def test_metadatos_se_toman_del_primer_registro_del_grupo():
    filas = aggregate_details([
        detalle(d_juego="QUINIELA", c_moneda="$", c_resumen="777", c_codigo="1"),
        detalle(d_juego="OTRO", c_moneda="U$", c_resumen="888", c_codigo="1"),
    ])
    assert filas[0]["d_juego"] == "QUINIELA" and filas[0]["moneda"] == "$"
    # el nro. de recibo, en cambio, se pisa con el último resumen no vacío
    assert filas[0]["no_recibo"] == 888


def test_resumen_no_numerico_no_rompe_el_numero_de_recibo():
    assert _uno(c_resumen="AB/12").get("no_recibo") == 0


def test_campos_vacios_caen_a_valores_por_defecto():
    g = aggregate_details([{"IMPORTE": "10.00", "C_CODIGO": "1"}])[0]
    assert g["n_agen"] == "" and g["c_juego"] == 0 and g["n_sorteo"] == 0
    assert g["moneda"] == "$"   # moneda vacía → "$"


def test_codigo_vacio_se_trata_como_cero():
    g = _uno(c_codigo="", c_juego="7", importe="40.00")
    assert g["debitos"] == Decimal("40.00")   # 0 < 500 → débito


def test_lista_vacia_no_produce_grupos():
    assert aggregate_details([]) == []


# ───────────────────────── fechas y resumen ─────────────────────────

def test_parse_date_acepta_dd_mm_yyyy():
    assert _parse_date("15/03/2025") == date(2025, 3, 15)


@pytest.mark.parametrize("valor", ["", "2025-03-15", "31/31/2025", "15/03"])
def test_parse_date_devuelve_none_ante_formatos_invalidos(valor):
    assert _parse_date(valor) is None


def test_fecha_y_resumen_del_lote_salen_del_primer_registro():
    regs = [detalle(d_operac="02/01/2025", c_resumen="991")]
    assert _extract_operation_date(regs) == date(2025, 1, 2)
    assert _extract_resumen_number(regs) == "991"


def test_sin_registros_no_hay_fecha_ni_resumen():
    assert _extract_operation_date([]) is None
    assert _extract_resumen_number([]) is None


def test_resumen_vacio_es_none():
    assert _extract_resumen_number([detalle(c_resumen="")]) is None
