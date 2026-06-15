"""
Coerción de valores leídos de DBF a tipos Postgres.

Las DBF de FoxPro suelen guardar casi todo como carácter (importes como
"113400.00000", fechas como "09/02/2026"), pero algunas columnas pueden venir
ya tipadas (N=Decimal, D=date, L=bool) según dbfread. Estas funciones aceptan
ambos casos y devuelven None ante vacío/None.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y", "%m/%d/%Y")
_TRUE = {"T", ".T.", "TRUE", "S", "SI", "1", "Y", "YES"}
_FALSE = {"F", ".F.", "FALSE", "N", "NO", "0", ""}


def to_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def to_decimal(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if isinstance(v, (int, float)):
        return Decimal(str(v)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    s = str(v).strip()
    if not s:
        return None
    # algunos legacy usan coma decimal
    s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s
    try:
        return Decimal(s).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def to_int(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


def to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().upper()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None
