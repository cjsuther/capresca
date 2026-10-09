"""Siembra inicial: ente contable, diarios, plan de cuentas y el ejercicio en curso.

El plan es **el del sistema anterior** tal como lo exporta a Excel, con su misma codificación de máscara
fija (1.1.1.2.001). Vive en `plan_cuentas.csv`, que se regenera desde el Excel con
`scripts/plan_desde_excel.py`: ahí está cómo se deducen el rubro, el saldo normal y la imputabilidad.
"""
import csv
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

DIARIOS = [("VAR", "Varios"), ("CAJA", "Caja"), ("BANCO", "Banco"), ("VTA", "Ventas"), ("CMP", "Compras")]
CENTROS = [("ADM", "Administración"), ("COM", "Comercial / Créditos"), ("FIN", "Financiero"),
           ("SEG", "Seguros")]

CUENTA_RESULTADO = "3.5.0.0.000"   # Resultado del Ejercicio: ahí se refunde el resultado al cerrar
CUENTA_BANCO = "1.1.1.2.001"       # Banco Nación 1439/83: la que abre la conciliación bancaria
RAMA_DISPONIBILIDADES = "1.1.1."   # Caja y Bancos: lo que mira el flujo de efectivo


def _leer_plan() -> list[tuple[str, str, str, bool, str, bool]]:
    """(código, nombre, rubro, imputable, saldo normal, ajustable por inflación)"""
    with (Path(__file__).parent / "plan_cuentas.csv").open(encoding="utf-8") as f:
        return [(r["codigo"], r["nombre"], r["rubro"], r["imputable"] == "1", r["saldo_normal"],
                 r["ajustable"] == "1") for r in csv.DictReader(f)]


PLAN = _leer_plan()


def sembrar(db: Session) -> None:
    if not db.scalar(select(models.Empresa).limit(1)):
        db.add(models.Empresa(razon_social="Ca.Pre.S.Ca.", condicion_iva="RESPONSABLE_INSCRIPTO",
                              predeterminada=True))
    for codigo, nombre in DIARIOS:
        if not db.scalar(select(models.Diario).where(models.Diario.codigo == codigo)):
            db.add(models.Diario(codigo=codigo, nombre=nombre))
    for codigo, nombre in CENTROS:
        if not db.scalar(select(models.CentroCosto).where(models.CentroCosto.codigo == codigo)):
            db.add(models.CentroCosto(codigo=codigo, nombre=nombre))
    # El plan se carga una sola vez: después es del contador, que lo mantiene desde la pantalla, y un
    # reinicio no le pisa ni le borra nada. Para cambiarlo entero: `python -m app.reemplazar_plan`.
    if not db.scalar(select(models.Cuenta).limit(1)):
        cargar_plan(db)
    anio = date.today().year
    if not db.scalar(select(models.Ejercicio).where(models.Ejercicio.numero == anio)):
        db.add(models.Ejercicio(numero=anio, desde=date(anio, 1, 1), hasta=date(anio, 12, 31),
                                estado="ABIERTO", cuenta_resultado=CUENTA_RESULTADO))
    # Un ejercicio que apunte a una cuenta de resultado que ya no existe no se podría cerrar.
    for ej in db.scalars(select(models.Ejercicio).where(models.Ejercicio.estado == "ABIERTO")).all():
        if not db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == ej.cuenta_resultado)):
            ej.cuenta_resultado = CUENTA_RESULTADO
    db.commit()


def cargar_plan(db: Session) -> None:
    db.add_all(models.Cuenta(codigo=codigo, nombre=nombre, rubro=rubro, imputable=imputable,
                             saldo_normal=saldo, ajustable=ajustable)
               for codigo, nombre, rubro, imputable, saldo, ajustable in PLAN)
    db.flush()
