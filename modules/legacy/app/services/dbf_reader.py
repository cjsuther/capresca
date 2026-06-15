"""
Lectura genérica de tablas DBF del legacy vía el share montado (SMB, read-only).

Reutiliza el patrón de modules/liquidaciones (dbfread, latin-1). NO toca los .CDX
(lectura pura). Devuelve filas como dict con claves en MAYÚSCULAS y strings
stripeados; el mapeo a columnas tipadas lo hace sync_service según sync_spec.
"""
import os

from dbfread import DBF

from app.config import settings
from app.legacy_catalog import relative_path


class DbfNotFound(FileNotFoundError):
    pass


def table_path(table_name: str) -> str:
    rel = relative_path(table_name)
    if rel is None:
        raise ValueError(f"Tabla desconocida en el catálogo: {table_name}")
    return os.path.join(settings.smb_mount_root, rel)


def read_table(table_name: str, encoding: str = "latin-1") -> list[dict]:
    """Lee una tabla DBF completa. Lanza DbfNotFound si el archivo no existe."""
    path = table_path(table_name)
    if not os.path.isfile(path):
        raise DbfNotFound(f"No se encontró la DBF: {path}")

    table = DBF(path, encoding=encoding, char_decode_errors="replace")
    rows = []
    for record in table:
        row = {}
        for key, value in record.items():
            k = key.upper()
            row[k] = value.strip() if isinstance(value, str) else value
        rows.append(row)
    return rows


def get_field_ci(row: dict, field_name: str):
    """Lookup case-insensitive de un campo (las filas vienen en MAYÚSCULAS)."""
    return row.get(field_name.upper())
