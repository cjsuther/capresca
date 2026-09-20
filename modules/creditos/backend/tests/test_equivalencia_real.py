"""Pruebas de equivalencia del motor contra créditos REALES del sistema VFP.

Fuente: prgs/tmpdev.DBF (2,6M cuotas de producción). Se extrajeron créditos
completos a tests/fixtures_creditos_reales.json. El motor debe reproducir,
al centavo, el interés, el IVA-interés y el capital (amortización) de cada cuota.

El TOTAL real incluye además seguro y gastos (ngseg/ngadm), parámetros de línea
que no modelamos por crédito individual; por eso se comparan los tres conceptos
del núcleo y su suma, no el TOTAL con seguro/gastos.
"""
import json
import os
from decimal import Decimal

import pytest

from app.domain.cuotas import ParametrosLinea, generar_plan

FIXT = os.path.join(os.path.dirname(__file__), "fixtures_creditos_reales.json")
D = Decimal


def _casos():
    with open(FIXT, encoding="utf-8") as f:
        data = json.load(f)
    # Sistema francés: créditos con tasa mensual real > 0.01%.
    # Las líneas con tasa ~0 (p.ej. GAS, tasa 0.0001%) NO amortizan por anualidad
    # sino por CAPITAL CONSTANTE (capital/plazo); son otro tipo_calculo y se
    # validan aparte cuando dispongamos de la tabla lineacred. Ver test_zero_interes.
    return [c for c in data if D(c["tasa"]) > D("0.01")]


@pytest.mark.parametrize("cred", _casos(), ids=lambda c: f"cred{c['no_credito']}")
def test_equivalencia_frances(cred):
    capital = D(cred["capital_inicial"])
    tasa_mensual = D(cred["tasa"])           # tasa mensual real almacenada
    n = len(cred["cuotas"])
    linea = ParametrosLinea(tipo_calculo=1, tna=D(cred["tna"]),
                            tasa_mensual=tasa_mensual, iva=D("21"))
    plan = generar_plan(capital, n, linea, __import__("datetime").date(2020, 1, 1))

    assert len(plan.cuotas) == n
    max_dif = D("0")
    for calc, real in zip(plan.cuotas, cred["cuotas"]):
        for campo_calc, campo_real in [
            (calc.interes, real["interes"]),
            (calc.iva_interes, real["iva_interes"]),
            (calc.amortizacion, real["capital"]),
        ]:
            dif = abs(campo_calc - D(campo_real))
            max_dif = max(max_dif, dif)
    # tolerancia: 1 centavo por acumulación de redondeo en la última cuota
    assert max_dif <= D("0.01"), f"credito {cred['no_credito']}: dif máx {max_dif}"


def test_zero_interes_amortiza_capital_constante():
    """Créditos de tasa ~0 (p.ej. GAS): capital = capital_inicial / plazo (flat)."""
    with open(FIXT, encoding="utf-8") as f:
        data = json.load(f)
    casos = [c for c in data if D(c["tasa"]) <= D("0.01")]
    for c in casos:
        cap = D(c["capital_inicial"])
        n = len(c["cuotas"])
        esperado = (cap / n).quantize(D("0.01"))
        # todas las cuotas (salvo la última) amortizan ~capital/plazo
        for q in c["cuotas"][:-1]:
            assert abs(D(q["capital"]) - esperado) <= D("0.01")
        # el interés real es prácticamente nulo
        assert all(D(q["interes"]) <= D("0.01") for q in c["cuotas"])
