"""Matriz de carteras de crédito y reglas de compatibilidad.

Portado de la lógica de `calcpres` en set_class.prg (sistema VFP CCyPP).
Los códigos y nombres provienen de los comentarios del código original.
"""
from __future__ import annotations

from enum import IntEnum


class Cartera(IntEnum):
    PERSONALES = 1
    CONSORCIOS = 2
    PERSONALES_AGJS = 4
    SISMO = 5
    POLICIAS_RETIRO = 6
    PRODUCIR = 7
    JUBILADOS = 8
    TURISMO_STA_MARIA = 9
    FORTALECIMIENTO = 10
    GAS = 11
    MUNICIPIOS = 12
    AGAP = 14
    DEUDA_SALARIAL = 17


CARTERA_NOMBRE = {
    1: "Personales",
    2: "Consorcios",
    4: "Personales AGJS",
    5: "Sismo",
    6: "Policías retiro obligatorio",
    7: "Producir / Min. Producción",
    8: "Jubilados",
    9: "Turismo Santa María",
    10: "Fortalecimiento y promoción regional/municipal",
    11: "Gas",
    12: "Municipios",
    14: "AGAP",
    17: "Deuda salarial",
}

# Carteras que NO consumen margen de afectación (excepción de calcpres).
CARTERAS_SIN_MARGEN = frozenset({6, 10, 17})

# Carteras que requieren N° de Historia Clínica cuando el motivo es salud.
CARTERAS_SALUD = frozenset({1, 14})

# Pares (cartera_existente, cartera_nueva) explícitamente permitidos a convivir.
COMBINACIONES_PERMITIDAS = frozenset(
    {(c, 5) for c in (1, 4, 7, 8, 9, 10, 12)}
    | {(c, 2) for c in (1, 4, 7, 8, 9, 10, 12)}
    | {(12, 11), (4, 7), (6, 5), (1, 7), (1, 11), (1, 14)}
)

# Pares explícitamente bloqueados.
COMBINACIONES_BLOQUEADAS = frozenset({(6, 2)})


def requiere_historia_clinica(cartera: int, motivo_salud: bool) -> bool:
    return motivo_salud and cartera in CARTERAS_SALUD


def afecta_margen(cartera: int) -> bool:
    return cartera not in CARTERAS_SIN_MARGEN


def compatibilidad(cartera_existente: int, cartera_nueva: int) -> str:
    """Devuelve 'permitido', 'bloqueado' o 'previo_pago' (misma cartera con PP)."""
    if (cartera_existente, cartera_nueva) in COMBINACIONES_BLOQUEADAS:
        return "bloqueado"
    if cartera_existente == cartera_nueva:
        return "previo_pago"
    if (cartera_existente, cartera_nueva) in COMBINACIONES_PERMITIDAS:
        return "permitido"
    # Por defecto, distintas carteras conviven salvo bloqueo explícito.
    return "permitido"
