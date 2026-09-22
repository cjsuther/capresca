"""ETL: carga los usuarios reales del sistema (General/usuarios).

Las claves reales NO se migran (seguridad): se asigna una temporal que el
usuario debe cambiar. El admin del sistema nuevo se preserva.

Uso:
    DATABASE_URL=... python3 -m app.etl.cargar_usuarios "/bases"
"""
from __future__ import annotations

import os
import sys

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.etl.dbf import DbfReader
from app import models

CLAVE_TEMPORAL = "cambiar123"   # el usuario debe cambiarla al ingresar


def S(v):
    return str(v).strip() if v is not None else ""


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "General", "usuarios.dbf")
    if not os.path.exists(p):
        print("  no se encontró usuarios.dbf")
        return
    existentes = {u for (u,) in db.query(models.Usuario.username).all()}
    hash_tmp = hash_password(CLAVE_TEMPORAL)
    n = 0
    # H-016: en usuarios.dbf 'nombre' es el login corto y 'usuario' el nombre real.
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            login = S(x.get("nombre")).upper()[:30]
            if not login or login in existentes:
                continue
            existentes.add(login)
            db.add(models.Usuario(
                username=login, nombre=S(x.get("usuario"))[:80],
                password_hash=hash_tmp,
                perfil=(S(x.get("perfil")) or "XCR").upper()[:6],
                activo=True))
            n += 1
    db.commit()
    print(f"  usuarios: {n} (clave temporal '{CLAVE_TEMPORAL}')")
    print("ETL usuarios OK")


if __name__ == "__main__":
    cargar(sys.argv[1] if len(sys.argv) > 1 else "/bases")
