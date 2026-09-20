"""Pruebas del motor de cálculo.

Estas pruebas fijan el comportamiento del motor portado. Los valores de
referencia definitivos deben provenir de créditos reales corridos en el
sistema VFP (pruebas de equivalencia). Por ahora validan invariantes
financieras y el tipo 5 (tomado literal del código fuente).
"""
from datetime import date
from decimal import Decimal

import pytest

from app.domain.cuotas import ParametrosLinea, generar_plan, gomonth
from app.domain.mora import calcular_mora
from app.domain.margen import margen_disponible, valida_cuil
from app.domain import carteras


D = Decimal


def test_gomonth_fin_de_mes():
    assert gomonth(date(2024, 1, 31), 1) == date(2024, 2, 29)  # bisiesto
    assert gomonth(date(2024, 1, 15), 12) == date(2025, 1, 15)


# ---------- Sistema francés ----------
def test_frances_amortiza_todo_el_capital():
    linea = ParametrosLinea(tipo_calculo=1, tna=D("36"))
    plan = generar_plan(D("120000"), 12, linea, date(2024, 2, 1))
    assert len(plan.cuotas) == 12
    total_amort = sum(c.amortizacion for c in plan.cuotas)
    assert total_amort == D("120000.00")
    # el saldo final debe cerrar en cero
    assert plan.cuotas[-1].saldo_capital - plan.cuotas[-1].amortizacion == D("0.00")


def test_frances_cuota_constante_capital_interes_iva():
    # En el francés CCyPP la constante es capital + interés + IVA-interés.
    linea = ParametrosLinea(tipo_calculo=1, tna=D("24"))
    plan = generar_plan(D("100000"), 6, linea, date(2024, 1, 1))
    consts = [c.amortizacion + c.interes + c.iva_interes for c in plan.cuotas[:-1]]
    assert len(set(consts)) == 1


def test_iva_se_aplica_sobre_interes():
    linea = ParametrosLinea(tipo_calculo=1, tna=D("36"), iva=D("21"))
    plan = generar_plan(D("50000"), 3, linea, date(2024, 1, 1))
    c = plan.cuotas[0]
    assert c.iva_interes == (c.interes * D("21") * D("0.01")).quantize(D("0.01"))


# ---------- Sistema alemán ----------
def test_aleman_amortizacion_constante():
    linea = ParametrosLinea(tipo_calculo=2, tna=D("30"))
    plan = generar_plan(D("90000"), 9, linea, date(2024, 1, 1))
    amorts = [c.amortizacion for c in plan.cuotas[:-1]]
    assert all(a == D("10000.00") for a in amorts)


# ---------- Tipo 5: cuota fija sin interés ----------
def test_tipo5_sin_interes_plazo_por_cuota():
    linea = ParametrosLinea(tipo_calculo=5, tna=D("0"))
    plan = generar_plan(D("120000"), 0, linea, date(2024, 1, 1), cuota_fija=D("10000"))
    assert len(plan.cuotas) == 12
    assert all(c.interes == D("0.00") for c in plan.cuotas)
    assert all(c.iva_interes == D("0.00") for c in plan.cuotas)
    assert sum(c.amortizacion for c in plan.cuotas) == D("120000.00")


def test_tipo5_requiere_cuota_fija():
    linea = ParametrosLinea(tipo_calculo=5, tna=D("0"))
    with pytest.raises(ValueError):
        generar_plan(D("120000"), 0, linea, date(2024, 1, 1))


# ---------- Mora ----------
def test_mora_punitorios():
    r = calcular_mora(
        cuota=D("10000"), saldo=D("50000"), dias=30,
        tasa_punitoria_diaria=D("0.1"), tasa_iva=D("21"),
    )
    # int_pun = 10000 * 0.1 * 30 / 100 = 300
    assert r.interes_punitorio == D("300.00")
    assert r.iva_punitorio == D("63.00")  # 300 * 21%
    assert r.total_vencido == D("10363.00")


def test_mora_sin_dias_no_agrega():
    r = calcular_mora(D("10000"), D("50000"), 0, D("0.1"))
    assert r.total_vencido == D("10000.00")
    assert r.interes_punitorio == D("0.00")


# ---------- Margen ----------
def test_margen_disponible_ok():
    r = margen_disponible(sueldo=D("500000"), por_afecta=D("30"), total_afectado=D("50000"))
    assert r.margen_disponible == D("100000")  # 500000*0.30 - 50000
    assert r.puede_tomar_credito is True


def test_margen_insuficiente_bloquea():
    r = margen_disponible(sueldo=D("100000"), por_afecta=D("30"), total_afectado=D("29900"))
    assert r.margen_disponible == D("100")  # < 200
    assert r.puede_tomar_credito is False


# ---------- CUIL ----------
@pytest.mark.parametrize("cuil,ok", [
    ("20-12345678-6", True),   # dígito verificador válido
    ("20123456786", True),
    ("20123456780", False),
    ("123", False),
])
def test_valida_cuil(cuil, ok):
    assert valida_cuil(cuil) is ok


# ---------- Carteras ----------
def test_carteras_sin_margen():
    assert carteras.afecta_margen(6) is False   # policías retiro
    assert carteras.afecta_margen(1) is True     # personales


def test_cartera_bloqueada():
    assert carteras.compatibilidad(6, 2) == "bloqueado"


def test_cartera_misma_previo_pago():
    assert carteras.compatibilidad(1, 1) == "previo_pago"
