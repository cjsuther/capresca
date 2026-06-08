"""
Verificación de salud del montaje SMB/CIFS del share legacy.

No falla nunca con excepción hacia el caller: devuelve un dict describiendo el
estado, para que el módulo degrade con elegancia (estado DEGRADED) en vez de romper.
"""
import os

from app.config import settings
from app.legacy_catalog import LEGACY_CATALOG, relative_path, TABLE_DATABASE


def check_mount() -> dict:
    """Estado del montaje: existe la raíz y los subdirectorios de cada base de datos."""
    root = settings.smb_mount_root
    result = {
        "mount_root": root,
        "mounted": False,
        "databases": {},
        "tables_present": 0,
        "tables_total": len(TABLE_DATABASE),
    }

    if not os.path.isdir(root):
        result["error"] = f"El montaje {root} no está accesible"
        return result

    result["mounted"] = True
    present = 0
    for db, meta in LEGACY_CATALOG.items():
        subdir = os.path.join(root, meta["subdir"])
        db_info = {"subdir_exists": os.path.isdir(subdir), "tables": {}}
        for table in meta["tables"]:
            path = os.path.join(root, relative_path(table))
            exists = os.path.isfile(path)
            db_info["tables"][table] = exists
            if exists:
                present += 1
        result["databases"][db] = db_info

    result["tables_present"] = present
    return result


def is_available() -> bool:
    """True si el share está montado y accesible (no implica que todas las tablas existan)."""
    return os.path.isdir(settings.smb_mount_root)
