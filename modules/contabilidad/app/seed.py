"""Siembra inicial: ente contable, diarios, plan de cuentas base y el ejercicio en curso.

El plan es el mínimo que necesita una contabilidad argentina para arrancar (con los rubros y el
tratamiento de IVA); cada organismo lo amplía desde la pantalla Plan de cuentas.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

DIARIOS = [("VAR", "Varios"), ("CAJA", "Caja"), ("BANCO", "Banco"), ("VTA", "Ventas"), ("CMP", "Compras")]

# (código, nombre, rubro, imputable, saldo normal, ajustable por inflación)
PLAN = [
    ("1", "ACTIVO", "ACTIVO", False, "DEUDOR", False),
    ("1.1", "Activo corriente", "ACTIVO", False, "DEUDOR", False),
    ("1.1.01", "Caja", "ACTIVO", True, "DEUDOR", False),
    ("1.1.02", "Bancos", "ACTIVO", True, "DEUDOR", False),
    ("1.1.03", "Créditos por ventas", "ACTIVO", True, "DEUDOR", False),
    ("1.1.04", "Préstamos otorgados", "ACTIVO", True, "DEUDOR", False),
    ("1.1.05", "Intereses a devengar", "ACTIVO", True, "ACREEDOR", False),
    ("1.1.06", "IVA crédito fiscal", "ACTIVO", True, "DEUDOR", False),
    ("1.1.07", "Retenciones y percepciones sufridas", "ACTIVO", True, "DEUDOR", False),
    ("1.1.08", "Deudores incobrables", "ACTIVO", True, "DEUDOR", False),
    ("1.2", "Activo no corriente", "ACTIVO", False, "DEUDOR", False),
    ("1.2.01", "Bienes de uso", "ACTIVO", True, "DEUDOR", True),
    ("1.2.02", "Amortización acumulada bienes de uso", "ACTIVO", True, "ACREEDOR", True),
    ("2", "PASIVO", "PASIVO", False, "ACREEDOR", False),
    ("2.1", "Pasivo corriente", "PASIVO", False, "ACREEDOR", False),
    ("2.1.01", "Proveedores", "PASIVO", True, "ACREEDOR", False),
    ("2.1.02", "IVA débito fiscal", "PASIVO", True, "ACREEDOR", False),
    ("2.1.03", "Ingresos brutos a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.04", "Retenciones y percepciones a depositar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.05", "Sueldos y cargas sociales a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.06", "Fondos de terceros a rendir", "PASIVO", True, "ACREEDOR", False),
    ("3", "PATRIMONIO NETO", "PATRIMONIO", False, "ACREEDOR", False),
    ("3.1.01", "Capital", "PATRIMONIO", True, "ACREEDOR", True),
    ("3.1.02", "Resultados acumulados", "PATRIMONIO", True, "ACREEDOR", True),
    ("3.1.03", "Resultado del ejercicio", "PATRIMONIO", True, "ACREEDOR", True),
    ("4", "INGRESOS", "INGRESO", False, "ACREEDOR", False),
    ("4.1.01", "Intereses ganados", "INGRESO", True, "ACREEDOR", False),
    ("4.1.02", "Intereses punitorios ganados", "INGRESO", True, "ACREEDOR", False),
    ("4.1.03", "Comisiones y cargos", "INGRESO", True, "ACREEDOR", False),
    ("4.1.04", "Ingresos por servicios", "INGRESO", True, "ACREEDOR", False),
    ("5", "EGRESOS", "EGRESO", False, "DEUDOR", False),
    ("5.1.01", "Gastos bancarios", "EGRESO", True, "DEUDOR", False),
    ("5.1.02", "Sueldos y cargas sociales", "EGRESO", True, "DEUDOR", False),
    ("5.1.03", "Impuestos y tasas", "EGRESO", True, "DEUDOR", False),
    ("5.1.04", "Servicios y gastos generales", "EGRESO", True, "DEUDOR", False),
    ("5.1.05", "Intereses perdidos", "EGRESO", True, "DEUDOR", False),
    ("5.1.06", "Deudores incobrables (pérdida)", "EGRESO", True, "DEUDOR", False),
    ("5.1.07", "Resultado por exposición a la inflación (RECPAM)", "EGRESO", True, "DEUDOR", False),
]


def sembrar(db: Session) -> None:
    if not db.scalar(select(models.Empresa).limit(1)):
        db.add(models.Empresa(razon_social="Ca.Pre.S.Ca.", condicion_iva="RESPONSABLE_INSCRIPTO",
                              predeterminada=True))
    for codigo, nombre in DIARIOS:
        if not db.scalar(select(models.Diario).where(models.Diario.codigo == codigo)):
            db.add(models.Diario(codigo=codigo, nombre=nombre))
    for codigo, nombre, rubro, imputable, saldo, ajustable in PLAN:
        if not db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == codigo)):
            db.add(models.Cuenta(codigo=codigo, nombre=nombre, rubro=rubro, imputable=imputable,
                                 saldo_normal=saldo, ajustable=ajustable))
    anio = date.today().year
    if not db.scalar(select(models.Ejercicio).where(models.Ejercicio.numero == anio)):
        db.add(models.Ejercicio(numero=anio, desde=date(anio, 1, 1), hasta=date(anio, 12, 31),
                                estado="ABIERTO", cuenta_resultado="3.1.03"))
    db.commit()
