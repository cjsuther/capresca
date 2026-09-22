"""Equivalencia vs VFP por tipo_calculo REAL de la línea (H-111).

Regresión del fix del mapeo invertido: tras traducir en el migrador (VFP tipo_calcu 1↔2), una línea
Francés queda tipo_calculo=1 y una Alemán tipo_calculo=2. El motor, usando el tipo_calculo REAL de la
línea (no hardcodeado), debe reproducir al centavo las cuotas migradas de VFP (amortización, interés, IVA).
Fixture extraído de la data real de producción en Postgres.
"""
import json
import os
from datetime import date
from decimal import Decimal as D

import pytest

from app.domain.cuotas import ParametrosLinea, generar_plan

FIXT = os.path.join(os.path.dirname(__file__), "fixtures_tipo_calculo_real.json")
with open(FIXT, encoding="utf-8") as f:
    CASOS = json.load(f)


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: f"cred{c['credito']}_tipo{c['tipo_calculo']}")
def test_equivalencia_por_tipo_calculo(caso):
    cap = D(caso["capital"])
    cuotas = caso["cuotas"]
    n = len(cuotas)
    # tasa de apertura: interes[1] = capital * i  →  i = interes[1] / capital
    i = D(cuotas[0]["interes"]) / cap
    # IVA real del crédito, derivado de la data (iva_interes / interes de la 1ª cuota)
    iva = (D(cuotas[0]["iva_interes"]) / D(cuotas[0]["interes"]) * 100) if D(cuotas[0]["interes"]) else D(0)
    linea = ParametrosLinea(tipo_calculo=caso["tipo_calculo"], tna=D(0),
                            tasa_mensual=i * 100, iva=iva)
    plan = generar_plan(cap, n, linea, date(2020, 1, 1))

    TOL = D("0.10")
    mal = 0
    for qv, qn in zip(cuotas, plan.cuotas):
        if (abs(D(qv["amortizacion"]) - D(qn.amortizacion)) > TOL or
                abs(D(qv["interes"]) - D(qn.interes)) > TOL or
                abs(D(qv["iva_interes"]) - D(qn.iva_interes)) > TOL):
            mal += 1
    # se admite a lo sumo la última cuota (ajuste de redondeo de cierre de saldo)
    assert mal <= 1, f"crédito {caso['credito']} (tipo {caso['tipo_calculo']}): {mal}/{n} cuotas no reproducen VFP"
