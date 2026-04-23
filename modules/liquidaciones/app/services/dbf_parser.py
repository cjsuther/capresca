import tempfile
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
from dbfread import DBF


def parse_dbf(dbf_bytes: bytes, encoding: str = "latin-1") -> list[dict]:
    """Parse DBF bytes into a list of dicts with stripped string fields and parsed importes."""
    tmp = tempfile.NamedTemporaryFile(suffix=".dbf", delete=False)
    try:
        tmp.write(dbf_bytes)
        tmp.close()
        table = DBF(tmp.name, encoding=encoding, char_decode_errors="replace")
        records = []
        for record in table:
            row = {}
            for key, value in record.items():
                if isinstance(value, str):
                    row[key] = value.strip()
                else:
                    row[key] = value
            records.append(row)
        return records
    finally:
        os.unlink(tmp.name)


def parse_importe(value) -> Decimal:
    """Parse an importe value to Decimal, quantized to 2 decimal places."""
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return Decimal("0.00")
        try:
            return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return Decimal("0.00")
    return Decimal("0.00")
