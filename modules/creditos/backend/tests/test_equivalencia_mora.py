"""Equivalencia del motor de MORA contra cobranzas reales (ivacob.DBF, 29.084 filas).

Qué valida esta tabla (tiene INTERES_PU, IVA_PUNI, INTERES_RE, IVA_RESAR, fechas):
  1. La regla de IVA sobre punitorios: IVA_PUNI = round(INTERES_PU * 21%).
  2. Que en producción los resarcitorios son 0 (coincide con `lntasres = 0` del VFP).
  3. Que el punitorio es lineal en los días (forma  base * tasa * dias / 100).
  4. Invariantes internas de `calcular_mora`.

Lo que NO puede validar esta tabla: la tasa punitoria diaria y la base exactas
(no están en ivacob; viven en `lineacred.nmoradia`). Eso se cerrará al centavo
cuando se disponga del backup de los DBC.
"""
import json
import os
import statistics
from collections import defaultdict
from decimal import Decimal as D, ROUND_HALF_UP

import pytest

from app.domain.mora import calcular_mora

FIXT = os.path.join(os.path.dirname(__file__), "fixtures_mora_real.json")


def _q(x):
    return x.quantize(D("0.01"), ROUND_HALF_UP)


def _data():
    with open(FIXT, encoding="utf-8") as f:
        return json.load(f)


def test_iva_punitorio_regla_21_pct_en_todos():
    """IVA_PUNI real == round(INTERES_PU * 21%) — la regla del motor, en 863 casos."""
    data = _data()
    assert data, "fixture vacío"
    fallos = [r for r in data
              if _q(D(r["interes_pu"]) * D("21") / 100) != _q(D(r["iva_puni"]))]
    assert not fallos, f"{len(fallos)} registros no cumplen la regla de IVA"


def test_resarcitorios_cero_en_produccion():
    data = _data()
    assert all(D(r["interes_re"]) == 0 and D(r["iva_resar"]) == 0 for r in data)


def test_punitorio_lineal_en_dias():
    """Dentro de un crédito, INTERES_PU / dias es constante (forma * dias)."""
    data = _data()
    g = defaultdict(list)
    for r in data:
        g[r["cred"]].append(r)
    multi = {c: xs for c, xs in g.items() if len(xs) >= 3}
    consistentes = 0
    for xs in multi.values():
        ks = [float(x["interes_pu"]) / x["dias"] for x in xs]
        m = statistics.mean(ks)
        cv = statistics.pstdev(ks) / m if m else 1.0
        if cv < 0.02:
            consistentes += 1
    # la gran mayoría debe ser lineal (permitimos algún crédito con pago parcial)
    assert consistentes >= 0.75 * len(multi)


def test_calcular_mora_reproduce_forma_real():
    """El motor reproduce el punitorio de un crédito real para distintos días.

    Crédito 110705: base*tasa/100 ≈ 0.9083/día. Con base=90.83 y tasa=1%/día,
    el motor debe dar los punitorios reales (±1 centavo por redondeo de la base).
    """
    casos = [(91, D("82.65")), (60, D("54.50")), (29, D("26.34"))]
    base = D("90.83")
    for dias, real_pun in casos:
        r = calcular_mora(cuota=base, saldo=D("0"), dias=dias,
                          tasa_punitoria_diaria=D("1"), tasa_iva=D("21"))
        assert abs(r.interes_punitorio - real_pun) <= D("0.01")
        # IVA y total siempre consistentes
        assert r.iva_punitorio == _q(r.interes_punitorio * D("21") / 100)
        assert r.total_vencido == _q(base + r.interes_punitorio + r.iva_punitorio)


def test_calcular_mora_invariantes():
    r = calcular_mora(cuota=D("10000"), saldo=D("50000"), dias=45,
                      tasa_punitoria_diaria=D("0.1"), tasa_iva=D("21"))
    assert r.interes_punitorio == D("450.00")   # 10000*0.1*45/100
    assert r.iva_punitorio == D("94.50")
    assert r.total_vencido == D("10544.50")


def test_piso_minimo_interes_como_cresegu1():
    """Piso `vl_minint` del cobro en caja (frm225150000cresegu1): si el punitorio
    calculado es positivo pero menor al mínimo, se eleva al mínimo; el IVA se
    recalcula sobre el interés elevado. Default 0 no altera nada."""
    # sin piso: interés chico queda como está
    base, tasa = D("100"), D("0.01")   # 100*0.01*1/100 = 0.01
    r0 = calcular_mora(cuota=base, saldo=D("0"), dias=1, tasa_punitoria_diaria=tasa)
    assert r0.interes_punitorio == D("0.01")
    # con piso de 5.00: se eleva el interés y el IVA se recalcula sobre 5.00
    r = calcular_mora(cuota=base, saldo=D("0"), dias=1, tasa_punitoria_diaria=tasa,
                      minimo_interes=D("5.00"))
    assert r.interes_punitorio == D("5.00")
    assert r.iva_punitorio == D("1.05")          # 5.00 * 21%
    assert r.total_vencido == D("106.05")
    # el piso no crea mora donde no la hay (interés 0 se mantiene 0)
    r_cero = calcular_mora(cuota=base, saldo=D("0"), dias=0,
                           tasa_punitoria_diaria=tasa, minimo_interes=D("5.00"))
    assert r_cero.interes_punitorio == D("0.00")
