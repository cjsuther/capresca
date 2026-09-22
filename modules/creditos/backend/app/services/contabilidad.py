"""Generación automática de asientos contables (partida doble).

Replica los asientos que el VFP producía en `cb-crasientootorga` (otorgamiento)
y en la cobranza. Todo asiento queda balanceado (Σ debe = Σ haber).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")


class ReglaNegocioError(Exception):
    """Regla de negocio contable violada (se mapea a HTTP 422 en la API)."""

# Plan de cuentas mínimo (código, nombre, tipo).
PLAN_CUENTAS = [
    ("1.1.01", "Caja", "activo"),
    ("1.1.02", "Banco", "activo"),
    ("1.2.01", "Créditos a cobrar", "activo"),
    ("2.1.01", "IVA débito fiscal", "pasivo"),
    ("4.1.01", "Intereses ganados", "ingreso"),
    ("4.1.02", "Intereses punitorios ganados", "ingreso"),
    ("4.1.03", "Seguros", "ingreso"),
    ("4.1.04", "Gastos administrativos", "ingreso"),
]
_NOMBRE = {c: n for c, n, _ in PLAN_CUENTAS}


# Tipos válidos de cuenta (para la ABM del Plan de cuentas).
TIPOS_CUENTA = ["activo", "pasivo", "patrimonio", "ingreso", "egreso"]


def seed_empresa_predeterminada(db: Session) -> models.Empresa:
    """Garantiza la empresa predeterminada (ente contable por defecto). Idempotente. H-188."""
    emp = db.scalar(select(models.Empresa).where(models.Empresa.predeterminada == True))  # noqa: E712
    if emp:
        return emp
    emp = db.scalar(select(models.Empresa).order_by(models.Empresa.id).limit(1))
    if emp:
        emp.predeterminada = True
    else:
        emp = models.Empresa(codigo="GRAL", nombre="Ca.Pre.S.Ca. (general)", predeterminada=True, activa=True)
        db.add(emp)
    db.commit(); db.refresh(emp)
    return emp


def seed_plan_cuentas(db: Session) -> None:
    seed_empresa_predeterminada(db)   # H-188: la empresa debe existir antes que sus cuentas
    if db.scalar(select(models.CuentaContable).limit(1)):
        return
    for cod, nom, tipo in PLAN_CUENTAS:
        db.add(models.CuentaContable(codigo=cod, nombre=nom, tipo=tipo))


# Plan de cuentas ESTÁNDAR (ejemplo argentino) para poblar el árbol de una. Incluye las cuentas del motor
# (mismos códigos) más los grupos y hojas típicas. Los grupos no son imputables.
PLAN_ESTANDAR = [
    ("1", "Activo", "activo", False),
    ("1.1", "Activo corriente", "activo", False),
    ("1.1.01", "Caja", "activo", True), ("1.1.02", "Banco", "activo", True),
    ("1.1.03", "Recaudaciones a depositar", "activo", True), ("1.1.04", "Inversiones transitorias", "activo", True),
    ("1.1.05", "Préstamos", "activo", False), ("1.1.05.01", "Préstamos otorgados", "activo", True),
    ("1.2", "Créditos", "activo", False),
    ("1.2.01", "Créditos a cobrar", "activo", True), ("1.2.02", "Deudores por préstamos", "activo", True),
    ("1.2.03", "Deudores morosos", "activo", True), ("1.2.04", "IVA crédito fiscal", "activo", True),
    ("1.3", "Bienes de cambio", "activo", False),
    ("1.4", "Activo no corriente", "activo", False),
    ("1.4.01", "Muebles y útiles", "activo", True), ("1.4.02", "Rodados", "activo", True),
    ("1.4.03", "Inmuebles", "activo", True),
    ("2", "Pasivo", "pasivo", False),
    ("2.1", "Pasivo corriente", "pasivo", False),
    ("2.1.01", "IVA débito fiscal", "pasivo", True), ("2.1.02", "Proveedores", "pasivo", True),
    ("2.1.03", "Cargas sociales a pagar", "pasivo", True), ("2.1.04", "Sueldos a pagar", "pasivo", True),
    ("2.1.07", "IVA débito fiscal (Créditos)", "pasivo", True),
    ("2.2", "Pasivo no corriente", "pasivo", False), ("2.2.01", "Deudas bancarias", "pasivo", True),
    ("3", "Patrimonio neto", "patrimonio", False),
    ("3.1", "Capital", "patrimonio", True), ("3.2", "Resultados acumulados", "patrimonio", True),
    ("3.3", "Resultado del ejercicio", "patrimonio", True),
    ("4", "Ingresos", "ingreso", False),
    ("4.1", "Ingresos financieros y por servicios", "ingreso", False),
    ("4.1.01", "Intereses ganados", "ingreso", True), ("4.1.02", "Intereses punitorios ganados", "ingreso", True),
    ("4.1.03", "Seguros", "ingreso", True), ("4.1.04", "Gastos administrativos", "ingreso", True),
    ("5", "Egresos", "egreso", False),
    ("5.1", "Gastos de administración", "egreso", False),
    ("5.1.01", "Sueldos y jornales", "egreso", True), ("5.1.02", "Cargas sociales", "egreso", True),
    ("5.1.03", "Servicios", "egreso", True),
    ("5.2", "Gastos financieros", "egreso", False),
    ("5.2.01", "Intereses perdidos", "egreso", True), ("5.2.02", "Comisiones y gastos bancarios", "egreso", True),
]


def _nombre_cuenta(db: Session | None, cod: str) -> str:
    """Nombre de la cuenta: el del Plan de cuentas en la DB (editable) o el base como fallback."""
    if db is not None:
        n = db.scalar(select(models.CuentaContable.nombre).where(models.CuentaContable.codigo == cod))
        if n:
            return n
    return _NOMBRE.get(cod, cod)


# rubros que naturalmente tienen saldo DEUDOR (activo, egreso); el resto es acreedor.
_DEUDORAS = ("activo", "egreso")


# ---------------- Flujo de efectivo (cash flow, método directo) ----------------
CUENTAS_EFECTIVO_DEFAULT = ["1.1.01", "1.1.02"]   # Caja + Banco (configurable en Parámetros)


def seed_parametros_contables(db: Session) -> None:
    """Siembra los parámetros contables si faltan (idempotente)."""
    if not db.query(models.Parametro).filter(models.Parametro.clave == "CUENTAS_EFECTIVO").first():
        db.add(models.Parametro(clave="CUENTAS_EFECTIVO", valor=",".join(CUENTAS_EFECTIVO_DEFAULT), ambito="contabilidad",
                                descripcion="Cuentas consideradas efectivo (Caja/Banco) para el flujo de efectivo."))
        db.commit()


# ---------------- Ejercicios contables (períodos: abierto/cerrado, apertura/cierre) ----------------
RESULTADO_EJERCICIO = "3.3"   # cuenta de PN donde se refunde el resultado al cierre


# ---------------- Centros de costo (analítica) ----------------
CENTROS_DEFAULT = [("ADM", "Administración"), ("COM", "Comercial / Créditos"), ("FIN", "Financiero"), ("SEG", "Seguros")]


def seed_centros(db: Session) -> None:
    existentes = {c for (c,) in db.execute(select(models.CentroCosto.codigo)).all()}
    nuevos = 0
    for cod, nom in CENTROS_DEFAULT:
        if cod not in existentes:
            db.add(models.CentroCosto(codigo=cod, nombre=nom)); nuevos += 1
    if nuevos:
        db.commit()


# ---------------- Diarios contables (Odoo: journals) ----------------
DIARIOS_DEFAULT = [("CAJA", "Caja", "caja"), ("BANCO", "Banco", "banco"), ("VAR", "Varios / Ajustes", "varios")]


def seed_diarios(db: Session) -> None:
    existentes = {c for (c,) in db.execute(select(models.DiarioContable.codigo)).all()}
    nuevos = 0
    for cod, nom, tipo in DIARIOS_DEFAULT:
        if cod not in existentes:
            db.add(models.DiarioContable(codigo=cod, nombre=nom, tipo=tipo)); nuevos += 1
    if nuevos:
        db.commit()


def _linea(cod: str, debe=CERO, haber=CERO, db: Session | None = None) -> models.AsientoLinea:
    return models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=_nombre_cuenta(db, cod),
                               debe=debe, haber=haber)


# ---------------- Parametrización contable (evento de operación → cuenta del plan) ----------------
# clave → (grupo, descripción, código por defecto). El código real sale de la config (editable); estos
# defaults reproducen el comportamiento actual y siembran la tabla.
IMPUTACIONES_DEFAULT = [
    ("otorgamiento_creditos", "Otorgamiento de crédito", "Créditos a cobrar (debe)", "1.2.01"),
    ("otorgamiento_caja", "Otorgamiento de crédito", "Caja / desembolso (haber)", "1.1.01"),
    ("cobranza_caja", "Cobranza de crédito", "Caja (debe, total cobrado)", "1.1.01"),
    ("cobranza_capital", "Cobranza de crédito", "Capital / Créditos a cobrar (haber)", "1.2.01"),
    ("cobranza_interes", "Cobranza de crédito", "Intereses ganados (haber)", "4.1.01"),
    ("cobranza_punitorio", "Cobranza de crédito", "Intereses punitorios (haber)", "4.1.02"),
    ("cobranza_seguro", "Cobranza de crédito", "Seguros (haber)", "4.1.03"),
    ("cobranza_gastos", "Cobranza de crédito", "Gastos administrativos (haber)", "4.1.04"),
    ("cobranza_iva", "Cobranza de crédito", "IVA débito fiscal (haber)", "2.1.01"),
]


def seed_imputaciones(db: Session) -> None:
    """Siembra idempotente de la parametrización contable con los códigos actuales."""
    existentes = {c for (c,) in db.execute(select(models.ImputacionContable.clave)).all()}
    nuevas = 0
    for clave, grupo, desc, cod in IMPUTACIONES_DEFAULT:
        if clave not in existentes:
            db.add(models.ImputacionContable(clave=clave, grupo=grupo, descripcion=desc, cuenta_codigo=cod))
            nuevas += 1
    if nuevas:
        db.commit()


def codigo_para(db: Session, clave: str, fallback: str) -> str:
    """Código de cuenta configurado para un evento (o el default si no está parametrizado)."""
    cod = db.scalar(select(models.ImputacionContable.cuenta_codigo).where(models.ImputacionContable.clave == clave))
    return cod or fallback


def asiento_otorgamiento(db: Session, credito: models.Credito) -> models.Asiento:
    """Debe Créditos a cobrar / Haber Caja, por el capital otorgado (cuentas por parametrización)."""
    a = models.Asiento(
        fecha=credito.fecha_otorgamiento or date.today(),
        concepto=f"Otorgamiento crédito N° {credito.id}",
        origen="otorgamiento", ref_id=credito.id, diario_codigo="CAJA",
        lineas=[
            _linea(codigo_para(db, "otorgamiento_creditos", "1.2.01"), debe=credito.capital, db=db),
            _linea(codigo_para(db, "otorgamiento_caja", "1.1.01"), haber=credito.capital, db=db),
        ],
    )
    db.add(a)
    return a


def asiento_cobranza(db: Session, recibo: models.Recibo) -> models.Asiento:
    """Debe Caja (total) / Haber capital, intereses, punitorios, seguros, gastos, IVA (por parametrización)."""
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == recibo.id)).all()
    cap = sum((p.capital for p in pagos), CERO)
    interes = sum((p.interes for p in pagos), CERO)
    pun = sum((p.interes_punitorio for p in pagos), CERO)
    seg = sum((p.seguro for p in pagos), CERO)
    gas = sum((p.gastos_adm for p in pagos), CERO)
    # todo el IVA (interés, seguro, gastos y punitorios) como residual → balancea
    iva = recibo.total - (cap + interes + pun + seg + gas)

    lineas = [_linea(codigo_para(db, "cobranza_caja", "1.1.01"), debe=recibo.total, db=db)]
    for clave, dflt, monto in [("cobranza_capital", "1.2.01", cap), ("cobranza_interes", "4.1.01", interes),
                               ("cobranza_punitorio", "4.1.02", pun), ("cobranza_seguro", "4.1.03", seg),
                               ("cobranza_gastos", "4.1.04", gas), ("cobranza_iva", "2.1.01", iva)]:
        if monto and monto != CERO:
            lineas.append(_linea(codigo_para(db, clave, dflt), haber=monto, db=db))

    a = models.Asiento(
        fecha=recibo.fecha_pago,
        concepto=f"Cobranza recibo N° {recibo.numero}",
        origen="cobranza", ref_id=recibo.id, diario_codigo="CAJA", lineas=lineas,
    )
    db.add(a)
    return a


# ---------------- asientos de contratos pp (Configurar Créditos) ----------------
# Nombres de cuentas usadas por el mapeo contable del componente ACCOUNTING.
CUENTAS_PP_NOMBRE = {
    "1.1.01": "Caja", "1.1.02": "Banco", "1.2.01": "Créditos a cobrar",
    "1.2.02": "Intereses a devengar", "1.1.05.01": "Préstamos otorgados",
    "4.1.01": "Intereses ganados", "4.1.02": "Intereses punitorios ganados",
    "4.1.04": "Gastos administrativos", "2.1.01": "IVA débito fiscal", "2.1.07": "IVA débito fiscal",
}
CAJA_PP = "1.1.01"
INT_A_DEVENGAR = "1.2.02"  # activo: intereses devengados pendientes de cobro


def _nom_pp(cod: str) -> str:
    return CUENTAS_PP_NOMBRE.get(cod, cod)


def _lpp(cod: str, debe=CERO, haber=CERO) -> models.AsientoLinea:
    return models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=_nom_pp(cod), debe=debe, haber=haber)


def _dec(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x or 0))


def asiento_pp_otorgamiento(db: Session, contrato) -> models.Asiento:
    """Debe cuenta de capital / Haber Caja, por el capital desembolsado."""
    ct = (contrato.snapshot_producto or {}).get("contabilidad", {})
    cap = ct.get("cuentaCapital") or "1.2.01"
    monto = _dec(contrato.monto_original)
    a = models.Asiento(fecha=contrato.fecha_valor, origen="pp_otorgamiento", ref_id=None,
                       concepto=f"Otorgamiento contrato {contrato.numero_contrato}",
                       lineas=[_lpp(cap, debe=monto), _lpp(CAJA_PP, haber=monto)])
    db.add(a); db.flush()
    return a


def asiento_pp_devengo(db: Session, contrato, interes: Decimal, fecha, concepto) -> models.Asiento:
    """Devengamiento: Debe Intereses a devengar (activo) / Haber Intereses ganados (ingreso)."""
    ct = (contrato.snapshot_producto or {}).get("contabilidad", {})
    intc = ct.get("cuentaInteres") or "4.1.01"
    monto = _dec(interes)
    a = models.Asiento(fecha=fecha, origen="pp_devengo", ref_id=None, concepto=concepto,
                       lineas=[_lpp(INT_A_DEVENGAR, debe=monto), _lpp(intc, haber=monto)])
    db.add(a); db.flush()
    return a


def asiento_pp_pago(db: Session, contrato, cuota, fecha, concepto,
                    int_punitorio: Decimal = CERO, iva_punitorio: Decimal = CERO,
                    monto: Decimal | None = None) -> models.Asiento:
    """Debe Caja / Haber capital, interés, comisiones, impuestos y punitorios (separados).

    - El interés, si la cuota ya fue devengada, se acredita a Intereses a devengar (salda la
      cuenta a cobrar) en vez de a Intereses ganados, para no reconocer el ingreso dos veces.
    - Las comisiones (cargos de otorgamiento/administrativos) van a la cuenta de comisiones y
      los impuestos (IVA/sellado) a la cuenta de impuestos — NO se mezclan.
    - El interés punitorio (mora) va a 4.1.02 y su IVA a la cuenta de impuestos.
    - `monto`: si se paga menos que el total de la cuota (pago parcial), las porciones
      capital/interés/comisiones/impuestos se imputan **proporcionalmente**.
    """
    ct = (contrato.snapshot_producto or {}).get("contabilidad", {})
    cap = ct.get("cuentaCapital") or "1.2.01"
    intc = INT_A_DEVENGAR if getattr(cuota, "devengada", False) else (ct.get("cuentaInteres") or "4.1.01")
    comisc = ct.get("cuentaComision") or "4.1.04"
    ivac = ct.get("cuentaIva") or "2.1.01"
    int_pun, iva_pun = _dec(int_punitorio), _dec(iva_punitorio)
    total, capital, interes = _dec(cuota.total), _dec(cuota.capital), _dec(cuota.interes)
    impuestos = _dec(getattr(cuota, "impuestos", 0))
    comisiones = total - capital - interes - impuestos  # cargos netos de impuestos
    pagado = _dec(monto) if monto is not None else total
    if total > CERO and pagado < total:                  # pago parcial: imputación proporcional
        f = pagado / total
        capital = (capital * f).quantize(Decimal("0.01"))
        interes = (interes * f).quantize(Decimal("0.01"))
        impuestos = (impuestos * f).quantize(Decimal("0.01"))
        comisiones = pagado - capital - interes - impuestos   # el resto, para que cierre exacto
        total = pagado
    caja = total + int_pun + iva_pun                     # el cliente paga cuota (o parcial) + mora
    lineas = [_lpp(CAJA_PP, debe=caja)]
    for cod, monto in [(cap, capital), (intc, interes), (comisc, comisiones),
                       ("4.1.02", int_pun), (ivac, impuestos + iva_pun)]:
        if monto and monto != CERO:
            lineas.append(_lpp(cod, haber=monto))
    a = models.Asiento(fecha=fecha, origen="pp_cobranza", ref_id=None, concepto=concepto, lineas=lineas)
    db.add(a); db.flush()
    return a


def asiento_pp_payoff(db: Session, contrato, saldo, fecha, concepto) -> models.Asiento:
    """Debe Caja / Haber cuenta de capital, por el capital cancelado."""
    ct = (contrato.snapshot_producto or {}).get("contabilidad", {})
    cap = ct.get("cuentaCapital") or "1.2.01"
    monto = _dec(saldo)
    a = models.Asiento(fecha=fecha, origen="pp_cobranza", ref_id=None, concepto=concepto,
                       lineas=[_lpp(CAJA_PP, debe=monto), _lpp(cap, haber=monto)])
    db.add(a); db.flush()
    return a


def asiento_pp_reversa(db: Session, original: models.Asiento, fecha) -> models.Asiento:
    """Contra-asiento: invierte debe/haber del asiento original (no lo borra)."""
    lineas = [_lpp(l.cuenta_codigo, debe=_dec(l.haber), haber=_dec(l.debe)) for l in original.lineas]
    a = models.Asiento(fecha=fecha, origen="pp_reversa", ref_id=None,
                       concepto=f"Reversa asiento N° {original.id} — {original.concepto}", lineas=lineas)
    db.add(a); db.flush()
    return a
