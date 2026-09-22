"""Cálculo de mora (punitorios y resarcitorios). Portado de `recalculo`."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CERO = Decimal("0.00")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class ResultadoMora:
    dias: int
    interes_punitorio: Decimal
    iva_punitorio: Decimal
    interes_resarcitorio: Decimal
    iva_resarcitorio: Decimal
    total_vencido: Decimal


def calcular_mora(
    cuota: Decimal,
    saldo: Decimal,
    dias: int,
    tasa_punitoria_diaria: Decimal,
    tasa_resarcitoria_diaria: Decimal = CERO,
    tasa_iva: Decimal = Decimal("21"),
    minimo_interes: Decimal = CERO,
) -> ResultadoMora:
    """Reproduce el bloque de mora de `recalculo`.

        int_pun = ROUND(cuota * tasa_pun * dias / 100, 2)
        IF int_pun < minimo AND int_pun > 0: int_pun = minimo   && piso (cresegu1)
        iva_pun = ROUND(int_pun * tasa_iva * 0.01, 2)
        int_res = ROUND(saldo * tasa_res * dias / 100, 2)
        iva_res = ROUND(int_res * tasa_iva * 0.01, 2)
        total   = cuota + int_pun + iva_pun + int_res + iva_res

    donde `cuota = capital + interes + iva_interes - total_pagado`.

    `minimo_interes` reproduce el piso `vl_minint` del cobro en caja
    (`frm225150000cresegu1`): si el punitorio calculado es positivo pero menor al
    mínimo, se eleva al mínimo. Default 0 = sin piso (no altera el histórico).
    """
    cuota = Decimal(cuota)
    saldo = Decimal(saldo)
    if dias <= 0:
        return ResultadoMora(0, CERO, CERO, CERO, CERO, _q(cuota))

    d = Decimal(dias)
    int_pun = _q(cuota * tasa_punitoria_diaria * d / Decimal("100"))
    if CERO < int_pun < Decimal(minimo_interes):
        int_pun = _q(Decimal(minimo_interes))
    iva_pun = _q(int_pun * tasa_iva * Decimal("0.01"))
    int_res = _q(saldo * tasa_resarcitoria_diaria * d / Decimal("100"))
    iva_res = _q(int_res * tasa_iva * Decimal("0.01"))
    total = _q(cuota + int_pun + iva_pun + int_res + iva_res)
    return ResultadoMora(dias, int_pun, iva_pun, int_res, iva_res, total)
