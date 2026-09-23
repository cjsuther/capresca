"""Siembra inicial: ente contable, diarios, plan de cuentas y el ejercicio en curso.

El plan es **el mismo del sistema anterior** (plan estándar argentino de Ca.Pre.S.Ca.), con su misma
codificación: así las definiciones de asiento usan las cuentas que ya venían usando los asientos de
Créditos (1.2.01 préstamos, 4.1.01 intereses, 2.1.01 IVA débito…). Se le sumaron las cuentas que
faltaban para cumplir con lo que pide una contabilidad argentina (retenciones y percepciones,
amortizaciones, fondos de terceros y el RECPAM del ajuste por inflación).
"""
import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models

log = logging.getLogger("contabilidad.seed")

DIARIOS = [("VAR", "Varios"), ("CAJA", "Caja"), ("BANCO", "Banco"), ("VTA", "Ventas"), ("CMP", "Compras")]
CENTROS = [("ADM", "Administración"), ("COM", "Comercial / Créditos"), ("FIN", "Financiero"),
           ("SEG", "Seguros")]

CUENTA_RESULTADO = "3.3"        # donde se refunde el resultado al cerrar (igual que el sistema anterior)

# (código, nombre, rubro, imputable, saldo normal, ajustable por inflación)
PLAN = [
    ("1", "Activo", "ACTIVO", False, "DEUDOR", False),
    ("1.1", "Activo corriente", "ACTIVO", False, "DEUDOR", False),
    ("1.1.01", "Caja", "ACTIVO", True, "DEUDOR", False),
    ("1.1.02", "Banco", "ACTIVO", True, "DEUDOR", False),
    ("1.1.03", "Recaudaciones a depositar", "ACTIVO", True, "DEUDOR", False),
    ("1.1.04", "Inversiones transitorias", "ACTIVO", True, "DEUDOR", False),
    ("1.1.05", "Préstamos", "ACTIVO", False, "DEUDOR", False),
    ("1.1.05.01", "Préstamos otorgados", "ACTIVO", True, "DEUDOR", False),
    ("1.2", "Créditos", "ACTIVO", False, "DEUDOR", False),
    ("1.2.01", "Créditos a cobrar", "ACTIVO", True, "DEUDOR", False),
    ("1.2.02", "Deudores por préstamos", "ACTIVO", True, "DEUDOR", False),
    ("1.2.03", "Deudores morosos", "ACTIVO", True, "DEUDOR", False),
    ("1.2.04", "IVA crédito fiscal", "ACTIVO", True, "DEUDOR", False),
    ("1.2.05", "Intereses a devengar", "ACTIVO", True, "ACREEDOR", False),
    ("1.2.06", "Retenciones y percepciones sufridas", "ACTIVO", True, "DEUDOR", False),
    ("1.2.07", "Previsión para deudores incobrables", "ACTIVO", True, "ACREEDOR", False),
    ("1.3", "Bienes de cambio", "ACTIVO", False, "DEUDOR", False),
    ("1.4", "Activo no corriente", "ACTIVO", False, "DEUDOR", False),
    ("1.4.01", "Muebles y útiles", "ACTIVO", True, "DEUDOR", True),
    ("1.4.02", "Rodados", "ACTIVO", True, "DEUDOR", True),
    ("1.4.03", "Inmuebles", "ACTIVO", True, "DEUDOR", True),
    ("1.4.04", "Amortización acumulada de bienes de uso", "ACTIVO", True, "ACREEDOR", True),
    ("2", "Pasivo", "PASIVO", False, "ACREEDOR", False),
    ("2.1", "Pasivo corriente", "PASIVO", False, "ACREEDOR", False),
    ("2.1.01", "IVA débito fiscal", "PASIVO", True, "ACREEDOR", False),
    ("2.1.02", "Proveedores", "PASIVO", True, "ACREEDOR", False),
    ("2.1.03", "Cargas sociales a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.04", "Sueldos a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.05", "Fondos de terceros a rendir", "PASIVO", True, "ACREEDOR", False),
    ("2.1.06", "Retenciones y percepciones a depositar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.07", "IVA débito fiscal (Créditos)", "PASIVO", True, "ACREEDOR", False),
    ("2.1.08", "Ingresos brutos a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.1.09", "Sellado provincial a pagar", "PASIVO", True, "ACREEDOR", False),
    ("2.2", "Pasivo no corriente", "PASIVO", False, "ACREEDOR", False),
    ("2.2.01", "Deudas bancarias", "PASIVO", True, "ACREEDOR", False),
    ("3", "Patrimonio neto", "PATRIMONIO", False, "ACREEDOR", False),
    ("3.1", "Capital", "PATRIMONIO", True, "ACREEDOR", True),
    ("3.2", "Resultados acumulados", "PATRIMONIO", True, "ACREEDOR", True),
    ("3.3", "Resultado del ejercicio", "PATRIMONIO", True, "ACREEDOR", True),
    ("4", "Ingresos", "INGRESO", False, "ACREEDOR", False),
    ("4.1", "Ingresos financieros y por servicios", "INGRESO", False, "ACREEDOR", False),
    ("4.1.01", "Intereses ganados", "INGRESO", True, "ACREEDOR", False),
    ("4.1.02", "Intereses punitorios ganados", "INGRESO", True, "ACREEDOR", False),
    ("4.1.03", "Seguros", "INGRESO", True, "ACREEDOR", False),
    ("4.1.04", "Gastos administrativos", "INGRESO", True, "ACREEDOR", False),
    ("5", "Egresos", "EGRESO", False, "DEUDOR", False),
    ("5.1", "Gastos de administración", "EGRESO", False, "DEUDOR", False),
    ("5.1.01", "Sueldos y jornales", "EGRESO", True, "DEUDOR", False),
    ("5.1.02", "Cargas sociales", "EGRESO", True, "DEUDOR", False),
    ("5.1.03", "Servicios", "EGRESO", True, "DEUDOR", False),
    ("5.1.04", "Impuestos y tasas", "EGRESO", True, "DEUDOR", False),
    ("5.1.05", "Amortizaciones", "EGRESO", True, "DEUDOR", False),
    ("5.1.06", "Deudores incobrables", "EGRESO", True, "DEUDOR", False),
    ("5.2", "Gastos financieros", "EGRESO", False, "DEUDOR", False),
    ("5.2.01", "Intereses perdidos", "EGRESO", True, "DEUDOR", False),
    ("5.2.02", "Comisiones y gastos bancarios", "EGRESO", True, "DEUDOR", False),
    ("5.2.03", "Resultado por exposición a la inflación (RECPAM)", "EGRESO", True, "DEUDOR", False),
]
CODIGOS = {c[0] for c in PLAN}


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
    for codigo, nombre, rubro, imputable, saldo, ajustable in PLAN:
        cuenta = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == codigo))
        if cuenta is None:
            db.add(models.Cuenta(codigo=codigo, nombre=nombre, rubro=rubro, imputable=imputable,
                                 saldo_normal=saldo, ajustable=ajustable))
            continue
        # El código ya existe (siembra anterior): se alinea con el plan. Renombrar es siempre seguro;
        # el rubro y el "imputable" sólo se tocan si la cuenta todavía no tiene movimientos.
        cuenta.nombre, cuenta.saldo_normal, cuenta.ajustable = nombre, saldo, ajustable
        if not _tiene_movimientos(db, codigo):
            cuenta.rubro, cuenta.imputable = rubro, imputable
    db.flush()
    _limpiar_cuentas_ajenas(db)
    anio = date.today().year
    if not db.scalar(select(models.Ejercicio).where(models.Ejercicio.numero == anio)):
        db.add(models.Ejercicio(numero=anio, desde=date(anio, 1, 1), hasta=date(anio, 12, 31),
                                estado="ABIERTO", cuenta_resultado=CUENTA_RESULTADO))
    # Un ejercicio que apunte a una cuenta de resultado que ya no existe no se podría cerrar.
    for ej in db.scalars(select(models.Ejercicio).where(models.Ejercicio.estado == "ABIERTO")).all():
        if not db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == ej.cuenta_resultado)):
            ej.cuenta_resultado = CUENTA_RESULTADO
    db.commit()


def _tiene_movimientos(db: Session, codigo: str) -> bool:
    return bool(db.scalar(select(func.count()).select_from(models.AsientoLinea)
                          .where(models.AsientoLinea.cuenta_codigo == codigo)) or 0)


def _limpiar_cuentas_ajenas(db: Session) -> None:
    """Saca las cuentas de una siembra anterior que ya no están en el plan, si nadie las usa.

    Una cuenta con movimientos o usada por una definición NO se toca: se avisa en el log y la resuelve
    el contador desde la pantalla (una cuenta con asientos se da de baja, no se borra)."""
    definidas = {l.get("cuenta") for d in db.scalars(select(models.DefinicionAsiento)).all()
                 for l in (d.lineas or [])}
    for c in db.scalars(select(models.Cuenta).where(models.Cuenta.codigo.notin_(CODIGOS))).all():
        if _tiene_movimientos(db, c.codigo) or c.codigo in definidas:
            log.warning("Contabilidad: la cuenta %s (%s) no está en el plan estándar pero está en uso.",
                        c.codigo, c.nombre)
            continue
        db.delete(c)
