"""Margen de afectación y validación de CUIL. Portado de `calcpres` / `valida_cuil`."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

MARGEN_MINIMO = Decimal("200")


@dataclass
class ResultadoMargen:
    margen_disponible: Decimal
    puede_tomar_credito: bool


def margen_disponible(
    sueldo: Decimal,
    por_afecta: Decimal,
    total_afectado: Decimal,
) -> ResultadoMargen:
    """margen = ROUND(sueldo * (por_afecta/100) - total_afectado, 0).

    Si margen < 200 el cliente no puede tomar el crédito (regla de calcpres).
    """
    margen = (Decimal(sueldo) * Decimal(por_afecta) * Decimal("0.01") - Decimal(total_afectado))
    margen = margen.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return ResultadoMargen(margen, margen >= MARGEN_MINIMO)


def valida_cuil(cuil: str) -> bool:
    """Valida el dígito verificador de un CUIL/CUIT argentino (11 dígitos)."""
    c = "".join(ch for ch in str(cuil) if ch.isdigit())
    if len(c) != 11:
        return False
    mult = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(c[i]) * mult[i] for i in range(10))
    resto = suma % 11
    verif = 11 - resto
    if verif == 11:
        verif = 0
    elif verif == 10:
        verif = 9
    return verif == int(c[10])
