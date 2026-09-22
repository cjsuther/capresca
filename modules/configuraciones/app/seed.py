"""Datos iniciales (idempotente): impuestos e índices por defecto, calendario AR y reglas del workflow.

Los impuestos y los índices sólo se siembran con la tabla vacía: una base migrada desde Créditos
(`python -m app.etl.migrar_configuraciones` en Créditos) trae los suyos y los pisa por código.
"""
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import models
from app.db.session import SessionLocal
from app.services.feriados import ar_calculados
from app.services.workflow import sembrar_reglas

IMPUESTOS = [
    dict(codigo="IVA21", nombre="IVA 21%", tipo="IVA", alicuota=Decimal("21"), base="INTERES", cuenta_contable="2.1.07.01"),
    dict(codigo="IVA105", nombre="IVA 10,5%", tipo="IVA", alicuota=Decimal("10.5"), base="INTERES", cuenta_contable="2.1.07.02"),
    dict(codigo="IIBB-CAT", nombre="Ingresos Brutos Catamarca", tipo="IIBB", alicuota=Decimal("4"), base="TOTAL",
         cuenta_contable="2.1.08", jurisdiccion="Catamarca"),
    dict(codigo="SELLOS", nombre="Sellado provincial", tipo="SELLADO", alicuota=Decimal("1.2"), base="CUOTA", cuenta_contable="2.1.09"),
]

INDICES = [
    dict(codigo="BADLAR", nombre="BADLAR bancos privados", valor=Decimal("45"), fuente="BCRA"),
    dict(codigo="TPM", nombre="Tasa de política monetaria", valor=Decimal("40"), fuente="BCRA"),
    dict(codigo="UVA", nombre="Unidad de Valor Adquisitivo (equiv. anual)", valor=Decimal("30"), fuente="INDEC"),
]


def sembrar_feriados_ar(db: Session, hoy: date | None = None) -> int:
    """Calendario AR calculado del año actual y los dos siguientes (lo que falte)."""
    hoy = hoy or date.today()
    nuevos = 0
    for anio in (hoy.year, hoy.year + 1, hoy.year + 2):
        existentes = {f for (f,) in db.query(models.Feriado.fecha).filter(
            models.Feriado.pais == "AR", models.Feriado.fecha >= date(anio, 1, 1),
            models.Feriado.fecha <= date(anio, 12, 31)).all()}
        for fecha, nombre, tipo in ar_calculados(anio):
            if fecha not in existentes:
                db.add(models.Feriado(pais="AR", fecha=fecha, nombre=nombre, tipo=tipo, origen="OFICIAL"))
                nuevos += 1
    db.commit()
    return nuevos


def sembrar(db: Session) -> None:
    if not db.query(models.Impuesto).first():
        db.add_all(models.Impuesto(**i) for i in IMPUESTOS)
    if not db.query(models.IndiceReferencia).first():
        db.add_all(models.IndiceReferencia(**i) for i in INDICES)
    db.commit()
    sembrar_feriados_ar(db)
    sembrar_reglas(db)


def run() -> None:
    db = SessionLocal()
    try:
        sembrar(db)
        print("[seed] Configuraciones iniciales cargadas.")
    except Exception as e:  # pragma: no cover - el arranque del contenedor lo reporta
        db.rollback()
        print(f"[seed] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
