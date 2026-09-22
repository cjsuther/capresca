"""Calendario de feriados: fuente oficial pública (Nager.Date) con cálculo local de respaldo para AR
(feriados de fecha fija + los que dependen de Pascua)."""
import json
import urllib.request
from datetime import date, timedelta

# Países soportados por el maestro (código ISO alpha-2 + nombre).
PAISES = [
    {"codigo": "AR", "nombre": "Argentina"},
    {"codigo": "UY", "nombre": "Uruguay"},
    {"codigo": "CL", "nombre": "Chile"},
    {"codigo": "BR", "nombre": "Brasil"},
    {"codigo": "MX", "nombre": "México"},
    {"codigo": "ES", "nombre": "España"},
]

# Feriados nacionales argentinos de FECHA FIJA (mes, día, nombre).
_AR_FIJOS = [
    (1, 1, "Año Nuevo"), (3, 24, "Día de la Memoria"), (4, 2, "Malvinas"),
    (5, 1, "Día del Trabajador"), (5, 25, "Revolución de Mayo"),
    (7, 9, "Día de la Independencia"), (12, 8, "Inmaculada Concepción"),
    (12, 25, "Navidad"),
]


def pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo de Butcher/Meeus, calendario gregoriano)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * mm + 114) // 31
    dia = ((h + l - 7 * mm + 114) % 31) + 1
    return date(anio, mes, dia)


def ar_calculados(anio: int) -> list[tuple[date, str, str]]:
    """(fecha, nombre, tipo) de feriados AR: fijos + basados en Pascua."""
    out = [(date(anio, m, d), n, "INAMOVIBLE") for m, d, n in _AR_FIJOS]
    p = pascua(anio)
    out.append((p - timedelta(days=2), "Viernes Santo", "TRASLADABLE"))
    out.append((p - timedelta(days=48), "Carnaval (lunes)", "TRASLADABLE"))
    out.append((p - timedelta(days=47), "Carnaval (martes)", "TRASLADABLE"))
    return out


def desde_nager(pais: str, anio: int) -> list[tuple[date, str, str]] | None:
    """Intenta la fuente oficial pública Nager.Date. None si no está disponible."""
    url = f"https://date.nager.at/api/v3/PublicHolidays/{anio}/{pais}"
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        out = []
        for h in data:
            f = date.fromisoformat(h["date"])
            nombre = h.get("localName") or h.get("name") or "Feriado"
            tipo = "INAMOVIBLE" if h.get("fixed") else "TRASLADABLE"
            out.append((f, nombre, tipo))
        return out or None
    except Exception:
        return None
