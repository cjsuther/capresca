"""Datos de la persona derivados de lo declarado."""
from datetime import date


def edad_de(nacimiento: date | None, al: date | None = None) -> int | None:
    """Años cumplidos a la fecha (hoy si no se indica). La solicitud pide fecha de nacimiento y la edad
    se calcula: así no envejece sola una solicitud vieja ni hay que pedir el dato dos veces."""
    if not nacimiento:
        return None
    hoy = al or date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
