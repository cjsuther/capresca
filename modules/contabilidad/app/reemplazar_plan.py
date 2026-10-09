"""Reemplaza el plan de cuentas entero por el de `plan_cuentas.csv` y vacía la contabilidad.

    docker compose exec contabilidad python -m app.reemplazar_plan            # muestra qué borraría
    docker compose exec contabilidad python -m app.reemplazar_plan --confirmar

Es para el arranque, con datos de prueba: un asiento registrado no se borra nunca en un libro real
(se anula), y acá se van todos. Por eso borra junto con el plan todo lo que apunta a sus cuentas —
asientos, transacciones, definiciones de asiento, comprobantes de IVA, extracto bancario y
ejercicios— y deja un ejercicio abierto del año en curso. Se conservan el ente contable, los diarios
y los centros de costo. Las transacciones que los módulos manden después quedan pendientes de
configuración hasta que se carguen las definiciones con las cuentas nuevas.
"""
import sys

from sqlalchemy import delete, func, select

from app import models
from app.db.session import SessionLocal
from app.seed import PLAN, sembrar

# En orden: primero lo que referencia a lo siguiente.
TABLAS = [models.LineaExtracto, models.ComprobanteIva, models.AsientoLinea, models.Transaccion,
          models.Asiento, models.DefinicionAsiento, models.Ejercicio, models.Cuenta]


def main(confirmar: bool) -> None:
    with SessionLocal() as db:
        for t in TABLAS:
            print(f"{t.__tablename__:22} {db.scalar(select(func.count()).select_from(t)):>7} filas")
        if not confirmar:
            print(f"\nNo se tocó nada. Con --confirmar se borra lo de arriba y se cargan {len(PLAN)} cuentas.")
            return
        for t in TABLAS:
            db.execute(delete(t))
        sembrar(db)
        print(f"\nListo: {db.scalar(select(func.count()).select_from(models.Cuenta))} cuentas cargadas.")


if __name__ == "__main__":
    main("--confirmar" in sys.argv[1:])
