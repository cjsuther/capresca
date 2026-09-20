"""Generación automática de asientos contables (partida doble).

Replica los asientos que el VFP producía en `cb-crasientootorga` (otorgamiento)
y en la cobranza. Todo asiento queda balanceado (Σ debe = Σ haber).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, func
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


def empresa_predeterminada_id(db: Session) -> int | None:
    emp = db.scalar(select(models.Empresa).where(models.Empresa.predeterminada == True))  # noqa: E712
    return emp.id if emp else None


def listar_empresas(db: Session) -> list[models.Empresa]:
    return list(db.scalars(select(models.Empresa).order_by(models.Empresa.id)).all())


def crear_empresa(db: Session, codigo: str, nombre: str, cuit: str = "", predeterminada: bool = False) -> models.Empresa:
    codigo = (codigo or "").strip().upper()
    if not codigo or not (nombre or "").strip():
        raise ReglaNegocioError("Código y nombre son obligatorios.")
    if db.scalar(select(models.Empresa).where(models.Empresa.codigo == codigo)):
        raise ReglaNegocioError("Ya existe una empresa con ese código.")
    if predeterminada:
        for e in db.scalars(select(models.Empresa).where(models.Empresa.predeterminada == True)).all():  # noqa: E712
            e.predeterminada = False
    emp = models.Empresa(codigo=codigo, nombre=nombre.strip(), cuit=(cuit or "").strip(),
                         predeterminada=predeterminada, activa=True)
    db.add(emp); db.commit(); db.refresh(emp)
    return emp


def set_empresa_predeterminada(db: Session, empresa_id: int) -> models.Empresa:
    emp = db.get(models.Empresa, empresa_id)
    if not emp:
        raise ReglaNegocioError("Empresa inexistente.")
    for e in db.scalars(select(models.Empresa).where(models.Empresa.predeterminada == True)).all():  # noqa: E712
        e.predeterminada = False
    emp.predeterminada = True
    db.commit(); db.refresh(emp)
    return emp


def _emp(db: Session, empresa_id: int | None) -> int | None:
    """Resuelve la empresa a usar: la indicada, o la predeterminada."""
    return empresa_id if empresa_id is not None else empresa_predeterminada_id(db)


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


def cargar_plan_estandar(db: Session, empresa_id: int | None = None) -> int:
    """Inserta las cuentas del plan estándar que falten (idempotente; no pisa ni duplica) EN LA EMPRESA
    dada. Los grupos quedan no imputables; el saldo normal se deriva del rubro. Devuelve cuántas agregó."""
    emp = _emp(db, empresa_id)
    existentes = {c for (c,) in db.execute(select(models.CuentaContable.codigo)
                                           .where(models.CuentaContable.empresa_id == emp)).all()}
    agregadas = 0
    for cod, nom, rubro, imp in PLAN_ESTANDAR:
        if cod in existentes:
            continue
        saldo = "deudor" if rubro in ("activo", "egreso") else "acreedor"
        db.add(models.CuentaContable(empresa_id=emp, codigo=cod, nombre=nom, tipo=rubro,
                                     imputable=imp, saldo_normal=saldo))
        agregadas += 1
    if agregadas:
        db.commit()
    return agregadas


def restaurar_plan_cuentas(db: Session, empresa_id: int | None = None) -> int:
    """Agrega al Plan de cuentas de la empresa las cuentas base (plantilla) que falten. Idempotente."""
    emp = _emp(db, empresa_id)
    existentes = {c for (c,) in db.execute(select(models.CuentaContable.codigo)
                                           .where(models.CuentaContable.empresa_id == emp)).all()}
    agregadas = 0
    for cod, nom, tipo in PLAN_CUENTAS:
        if cod not in existentes:
            db.add(models.CuentaContable(empresa_id=emp, codigo=cod, nombre=nom, tipo=tipo)); agregadas += 1
    if agregadas:
        db.commit()
    return agregadas


def _nombre_cuenta(db: Session | None, cod: str) -> str:
    """Nombre de la cuenta: el del Plan de cuentas en la DB (editable) o el base como fallback."""
    if db is not None:
        n = db.scalar(select(models.CuentaContable.nombre).where(models.CuentaContable.codigo == cod))
        if n:
            return n
    return _NOMBRE.get(cod, cod)


# ---------------- Reportes: sumas y saldos + estados contables ----------------
def _cod_key(cod: str):
    return tuple(int(x) if x.isdigit() else x for x in cod.split("."))


def balances_por_cuenta(db: Session, desde: date | None = None, hasta: date | None = None,
                        empresa_id: int | None = None) -> dict:
    """Σdebe y Σhaber por cuenta (código) en el rango, para la empresa dada (o la predeterminada). Incluye
    TODOS los asientos (auto + manuales + reversas): la reversa neutraliza a su original, como corresponde."""
    emp = _emp(db, empresa_id)
    q = (select(models.AsientoLinea.cuenta_codigo,
                func.sum(models.AsientoLinea.debe), func.sum(models.AsientoLinea.haber))
         .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
         .where(models.Asiento.estado != "borrador",   # los borradores NO impactan el mayor (Odoo: sólo posted)
                models.Asiento.empresa_id == emp)
         .group_by(models.AsientoLinea.cuenta_codigo))
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    return {cod: {"debe": d or CERO, "haber": h or CERO} for cod, d, h in db.execute(q).all()}


def _cuentas_empresa(db: Session, empresa_id: int | None = None) -> dict:
    """Mapa {codigo: CuentaContable} de la empresa (para resolver nombre/rubro sin mezclar planes)."""
    emp = _emp(db, empresa_id)
    return {c.codigo: c for c in db.scalars(
        select(models.CuentaContable).where(models.CuentaContable.empresa_id == emp)).all()}


def sumas_y_saldos(db: Session, desde: date | None = None, hasta: date | None = None,
                   empresa_id: int | None = None) -> dict:
    """Balance de comprobación: por cuenta con movimiento — Σdebe, Σhaber y saldo deudor/acreedor.
    Los totales balancean (Σdebe=Σhaber y Σsaldo deudor=Σsaldo acreedor)."""
    bal = balances_por_cuenta(db, desde, hasta, empresa_id)
    ctas = _cuentas_empresa(db, empresa_id)
    filas, td, th, tsd, tsa = [], CERO, CERO, CERO, CERO
    for cod in sorted(bal, key=_cod_key):
        b = bal[cod]; c = ctas.get(cod)
        saldo = b["debe"] - b["haber"]
        sd = saldo if saldo > CERO else CERO
        sa = -saldo if saldo < CERO else CERO
        td += b["debe"]; th += b["haber"]; tsd += sd; tsa += sa
        filas.append({"codigo": cod, "nombre": c.nombre if c else cod, "tipo": c.tipo if c else "",
                      "debe": b["debe"], "haber": b["haber"], "saldo_deudor": sd, "saldo_acreedor": sa})
    return {"filas": filas, "totales": {"debe": td, "haber": th, "saldo_deudor": tsd, "saldo_acreedor": tsa},
            "balanceado": td == th}


# rubros que naturalmente tienen saldo DEUDOR (activo, egreso); el resto es acreedor.
_DEUDORAS = ("activo", "egreso")


# ---------------- Flujo de efectivo (cash flow, método directo) ----------------
CUENTAS_EFECTIVO_DEFAULT = ["1.1.01", "1.1.02"]   # Caja + Banco (configurable en Parámetros)


def cuentas_efectivo(db: Session) -> list[str]:
    """Códigos de las cuentas consideradas 'efectivo' (Caja/Banco). Configurable: Parámetro
    CUENTAS_EFECTIVO (coma-separado); si falta, cae al default."""
    p = db.query(models.Parametro).filter(models.Parametro.clave == "CUENTAS_EFECTIVO").first()
    if p and (p.valor or "").strip():
        cods = [c.strip() for c in p.valor.split(",") if c.strip()]
        if cods:
            return cods
    return list(CUENTAS_EFECTIVO_DEFAULT)


def seed_parametros_contables(db: Session) -> None:
    """Siembra los parámetros contables si faltan (idempotente)."""
    if not db.query(models.Parametro).filter(models.Parametro.clave == "CUENTAS_EFECTIVO").first():
        db.add(models.Parametro(clave="CUENTAS_EFECTIVO", valor=",".join(CUENTAS_EFECTIVO_DEFAULT), ambito="contabilidad",
                                descripcion="Cuentas consideradas efectivo (Caja/Banco) para el flujo de efectivo."))
        db.commit()


# ---------------- Conciliación bancaria ----------------
def _linea_signo(l: "models.AsientoLinea") -> Decimal:
    return (l.debe or CERO) - (l.haber or CERO)


def movimientos_banco(db: Session, cuenta: str, desde: date | None = None, hasta: date | None = None,
                      empresa_id: int | None = None) -> list:
    """Líneas del MAYOR (asientos publicados) en la cuenta banco, con su importe con signo (debe−haber)
    y si ya están conciliadas (referenciadas por alguna línea de extracto)."""
    emp = _emp(db, empresa_id)
    q = (select(models.AsientoLinea, models.Asiento)
         .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
         .where(models.Asiento.estado != "borrador", models.Asiento.empresa_id == emp,
                models.AsientoLinea.cuenta_codigo == cuenta))
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    concil = {e.asiento_linea_id for e in db.scalars(
        select(models.ExtractoBancarioLinea).where(models.ExtractoBancarioLinea.asiento_linea_id.isnot(None))).all()}
    out = []
    for l, a in db.execute(q).all():
        out.append({"asiento_linea_id": l.id, "asiento_id": a.id, "numero": a.numero, "fecha": a.fecha.isoformat(),
                    "concepto": a.concepto, "importe": _linea_signo(l), "conciliada": l.id in concil})
    out.sort(key=lambda x: (x["fecha"], x["asiento_linea_id"]))
    return out


def conciliacion_bancaria(db: Session, cuenta: str, desde: date | None = None, hasta: date | None = None,
                          empresa_id: int | None = None) -> dict:
    """Estado de conciliación: líneas del extracto vs movimientos del mayor en la cuenta banco, con saldos
    y diferencia. La diferencia 0 con todo conciliado = extracto y mayor cuadran."""
    emp = _emp(db, empresa_id)
    q = select(models.ExtractoBancarioLinea).where(models.ExtractoBancarioLinea.cuenta_codigo == cuenta,
                                                   models.ExtractoBancarioLinea.empresa_id == emp)
    if desde:
        q = q.where(models.ExtractoBancarioLinea.fecha >= desde)
    if hasta:
        q = q.where(models.ExtractoBancarioLinea.fecha <= hasta)
    ext = [{"id": e.id, "fecha": e.fecha.isoformat(), "descripcion": e.descripcion, "referencia": e.referencia,
            "importe": e.importe, "conciliada": e.conciliada, "asiento_linea_id": e.asiento_linea_id}
           for e in db.scalars(q).all()]
    ext.sort(key=lambda x: (x["fecha"], x["id"]))
    mayor = movimientos_banco(db, cuenta, desde, hasta, empresa_id)
    saldo_ext = sum((e["importe"] for e in ext), CERO)
    saldo_may = sum((m["importe"] for m in mayor), CERO)
    cta = db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == cuenta,
                                                        models.CuentaContable.empresa_id == emp))
    return {
        "cuenta": cuenta, "cuenta_nombre": cta.nombre if cta else cuenta,
        "extracto": ext, "mayor": mayor,
        "saldo_extracto": saldo_ext, "saldo_mayor": saldo_may, "diferencia": saldo_ext - saldo_may,
        "pendientes_extracto": sum(1 for e in ext if not e["conciliada"]),
        "pendientes_mayor": sum(1 for m in mayor if not m["conciliada"]),
    }


def crear_extracto_linea(db: Session, cuenta: str, fecha: date, descripcion: str, importe: Decimal,
                         referencia: str = "", empresa_id: int | None = None) -> models.ExtractoBancarioLinea:
    emp = _emp(db, empresa_id)
    cta = db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == cuenta,
                                                        models.CuentaContable.empresa_id == emp))
    if not cta:
        raise ReglaNegocioError("La cuenta banco no existe en el plan.")
    e = models.ExtractoBancarioLinea(empresa_id=emp, cuenta_codigo=cuenta, fecha=fecha, descripcion=descripcion,
                                     referencia=referencia, importe=Decimal(str(importe)))
    db.add(e); db.commit(); db.refresh(e)
    return e


def eliminar_extracto_linea(db: Session, extracto_id: int) -> None:
    e = db.get(models.ExtractoBancarioLinea, extracto_id)
    if not e:
        raise ReglaNegocioError("Línea de extracto inexistente.")
    db.delete(e); db.commit()


def conciliar(db: Session, extracto_id: int, asiento_linea_id: int) -> models.ExtractoBancarioLinea:
    """Concilia una línea del extracto con un movimiento del mayor (misma cuenta, mismo importe con signo,
    ambos sin conciliar)."""
    e = db.get(models.ExtractoBancarioLinea, extracto_id)
    if not e:
        raise ReglaNegocioError("Línea de extracto inexistente.")
    if e.conciliada:
        raise ReglaNegocioError("La línea del extracto ya está conciliada.")
    l = db.get(models.AsientoLinea, asiento_linea_id)
    if not l or l.cuenta_codigo != e.cuenta_codigo:
        raise ReglaNegocioError("El movimiento del mayor no corresponde a esta cuenta banco.")
    if db.scalar(select(models.ExtractoBancarioLinea).where(models.ExtractoBancarioLinea.asiento_linea_id == asiento_linea_id)):
        raise ReglaNegocioError("Ese movimiento del mayor ya fue conciliado con otra línea.")
    if _linea_signo(l) != e.importe:
        raise ReglaNegocioError(f"Los importes no coinciden (extracto {e.importe} vs mayor {_linea_signo(l)}).")
    e.asiento_linea_id = asiento_linea_id; e.conciliada = True
    db.commit(); db.refresh(e)
    return e


def desconciliar(db: Session, extracto_id: int) -> models.ExtractoBancarioLinea:
    e = db.get(models.ExtractoBancarioLinea, extracto_id)
    if not e:
        raise ReglaNegocioError("Línea de extracto inexistente.")
    e.asiento_linea_id = None; e.conciliada = False
    db.commit(); db.refresh(e)
    return e


def conciliar_automatico(db: Session, cuenta: str, empresa_id: int | None = None) -> dict:
    """Sugerencia/aplicación automática: empareja líneas de extracto sin conciliar con movimientos del
    mayor sin conciliar del MISMO importe (con signo), 1 a 1, prefiriendo la fecha más cercana."""
    est = conciliacion_bancaria(db, cuenta, empresa_id=empresa_id)
    ext_pend = [e for e in est["extracto"] if not e["conciliada"]]
    may_pend = [m for m in est["mayor"] if not m["conciliada"]]
    usados = set(); conciliadas = 0
    for e in ext_pend:
        cands = [m for m in may_pend if m["asiento_linea_id"] not in usados and m["importe"] == e["importe"]]
        if not cands:
            continue
        cands.sort(key=lambda m: abs((date.fromisoformat(m["fecha"]) - date.fromisoformat(e["fecha"])).days))
        elegido = cands[0]
        conciliar(db, e["id"], elegido["asiento_linea_id"])
        usados.add(elegido["asiento_linea_id"]); conciliadas += 1
    return {"conciliadas": conciliadas}


def flujo_efectivo(db: Session, desde: date | None = None, hasta: date | None = None,
                   empresa_id: int | None = None) -> dict:
    """Flujo de efectivo por método directo: saldo inicial de las cuentas de efectivo, entradas y salidas
    del período agrupadas por la cuenta de CONTRAPARTIDA (de dónde vino / a dónde fue la plata) y saldo
    final. Sólo asientos publicados (no borradores). El neto = Σentradas − Σsalidas = saldo final − inicial."""
    emp = _emp(db, empresa_id)
    cash = cuentas_efectivo(db)
    ctas = _cuentas_empresa(db, empresa_id)

    def _saldo_cash(hasta_excl: date | None = None, desde_incl: date | None = None,
                    hasta_incl: date | None = None) -> Decimal:
        q = (select(func.coalesce(func.sum(models.AsientoLinea.debe - models.AsientoLinea.haber), CERO))
             .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
             .where(models.Asiento.estado != "borrador", models.Asiento.empresa_id == emp,
                    models.AsientoLinea.cuenta_codigo.in_(cash)))
        if hasta_excl is not None:
            q = q.where(models.Asiento.fecha < hasta_excl)
        if desde_incl is not None:
            q = q.where(models.Asiento.fecha >= desde_incl)
        if hasta_incl is not None:
            q = q.where(models.Asiento.fecha <= hasta_incl)
        return db.execute(q).scalar() or CERO

    saldo_inicial = _saldo_cash(hasta_excl=desde) if desde else CERO

    # Asientos (publicados, en rango) que tocan alguna cuenta de efectivo.
    sub = (select(models.AsientoLinea.asiento_id)
           .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
           .where(models.Asiento.estado != "borrador", models.Asiento.empresa_id == emp,
                  models.AsientoLinea.cuenta_codigo.in_(cash)))
    if desde:
        sub = sub.where(models.Asiento.fecha >= desde)
    if hasta:
        sub = sub.where(models.Asiento.fecha <= hasta)
    sub = sub.distinct()

    # Líneas de CONTRAPARTIDA (no-efectivo) de esos asientos: (haber − debe) = aporte al efectivo.
    q = (select(models.AsientoLinea.cuenta_codigo,
                func.sum(models.AsientoLinea.haber - models.AsientoLinea.debe))
         .where(models.AsientoLinea.asiento_id.in_(sub),
                models.AsientoLinea.cuenta_codigo.notin_(cash))
         .group_by(models.AsientoLinea.cuenta_codigo))

    entradas, salidas, te, ts = [], [], CERO, CERO
    for cod, monto in db.execute(q).all():
        monto = monto or CERO
        if monto == CERO:
            continue
        c = ctas.get(cod)
        fila = {"codigo": cod, "nombre": c.nombre if c else cod, "tipo": c.tipo if c else "",
                "monto": abs(monto)}
        if monto > CERO:
            entradas.append(fila); te += monto
        else:
            salidas.append(fila); ts += -monto
    entradas.sort(key=lambda f: f["monto"], reverse=True)
    salidas.sort(key=lambda f: f["monto"], reverse=True)
    neto = te - ts
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "cuentas_efectivo": [{"codigo": c, "nombre": ctas[c].nombre if c in ctas else c} for c in cash],
        "saldo_inicial": saldo_inicial,
        "entradas": entradas, "total_entradas": te,
        "salidas": salidas, "total_salidas": ts,
        "neto": neto, "saldo_final": saldo_inicial + neto,
    }


def estados_contables(db: Session, desde: date | None = None, hasta: date | None = None,
                      empresa_id: int | None = None) -> dict:
    """Situación patrimonial (Activo = Pasivo + PN) y Estado de resultados (Ingresos − Egresos), armados
    desde los saldos por cuenta agrupados por rubro del plan."""
    bal = balances_por_cuenta(db, desde, hasta, empresa_id)
    ctas = _cuentas_empresa(db, empresa_id)
    grupos: dict[str, list] = {"activo": [], "pasivo": [], "patrimonio": [], "ingreso": [], "egreso": [], "otros": []}
    for cod in sorted(bal, key=_cod_key):
        b = bal[cod]; c = ctas.get(cod)
        rubro = (c.tipo if c else "").lower()
        saldo = b["debe"] - b["haber"]                       # deudor > 0
        if rubro not in grupos or rubro == "otros":
            # cuenta sin rubro clasificado (p.ej. asientos con códigos fuera del plan): se muestran aparte
            if saldo != CERO:
                grupos["otros"].append({"codigo": cod, "nombre": (c.nombre if c else cod), "valor": saldo})
            continue
        valor = saldo if rubro in _DEUDORAS else -saldo      # valor natural del rubro
        if valor != CERO:
            grupos[rubro].append({"codigo": cod, "nombre": c.nombre if c else cod, "valor": valor})
    tot = {r: sum((x["valor"] for x in grupos[r]), CERO) for r in grupos}
    resultado = tot["ingreso"] - tot["egreso"]
    patrimonio_total = tot["patrimonio"] + resultado
    total_activo_lado = tot["activo"] + tot["otros"]         # las 'otras' (deudor neto) van del lado del activo
    return {
        "situacion": {
            "activo": {"cuentas": grupos["activo"], "total": tot["activo"]},
            "pasivo": {"cuentas": grupos["pasivo"], "total": tot["pasivo"]},
            "patrimonio": {"cuentas": grupos["patrimonio"], "total_cuentas": tot["patrimonio"],
                           "resultado_ejercicio": resultado, "total": patrimonio_total},
            "otros": {"cuentas": grupos["otros"], "total": tot["otros"]},
            "total_activo": total_activo_lado, "total_pasivo_pn": tot["pasivo"] + patrimonio_total,
            "balanceado": total_activo_lado == tot["pasivo"] + patrimonio_total,
        },
        "resultados": {
            "ingresos": {"cuentas": grupos["ingreso"], "total": tot["ingreso"]},
            "egresos": {"cuentas": grupos["egreso"], "total": tot["egreso"]},
            "resultado": resultado,
        },
    }


# ---------------- Ejercicios contables (períodos: abierto/cerrado, apertura/cierre) ----------------
RESULTADO_EJERCICIO = "3.3"   # cuenta de PN donde se refunde el resultado al cierre


def crear_ejercicio(db: Session, *, nombre: str, fecha_desde: date, fecha_hasta: date,
                    empresa_id: int | None = None) -> models.EjercicioContable:
    if not (nombre or "").strip():
        raise ReglaNegocioError("El nombre del ejercicio es obligatorio.")
    if fecha_hasta < fecha_desde:
        raise ReglaNegocioError("La fecha hasta no puede ser anterior a la desde.")
    emp = _emp(db, empresa_id)
    # no permitir solapamiento con otro ejercicio DE LA MISMA EMPRESA
    solapa = db.scalar(select(models.EjercicioContable).where(
        models.EjercicioContable.empresa_id == emp,
        models.EjercicioContable.fecha_desde <= fecha_hasta,
        models.EjercicioContable.fecha_hasta >= fecha_desde).limit(1))
    if solapa:
        raise ReglaNegocioError(f"El período se solapa con '{solapa.nombre}'.")
    e = models.EjercicioContable(empresa_id=emp, nombre=nombre.strip()[:40],
                                 fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    db.add(e); db.commit(); db.refresh(e)
    return e


def ejercicio_cerrado_en(db: Session, fecha: date, empresa_id: int | None = None) -> models.EjercicioContable | None:
    """Ejercicio CERRADO de la empresa que cubre esa fecha (para bloquear la carga de asientos)."""
    emp = _emp(db, empresa_id)
    return db.scalar(select(models.EjercicioContable).where(
        models.EjercicioContable.empresa_id == emp,
        models.EjercicioContable.estado == "cerrado",
        models.EjercicioContable.fecha_desde <= fecha,
        models.EjercicioContable.fecha_hasta >= fecha).limit(1))


def _guard_periodo_abierto(db: Session, fecha: date, empresa_id: int | None = None) -> None:
    ej = ejercicio_cerrado_en(db, fecha, empresa_id)
    if ej:
        raise ReglaNegocioError(f"El ejercicio '{ej.nombre}' está cerrado: no se pueden cargar asientos en ese período.")


def cerrar_ejercicio(db: Session, ejercicio_id: int, usuario: str = "") -> models.EjercicioContable:
    """Cierra el ejercicio: genera el ASIENTO DE CIERRE que refunde ingresos/egresos en 'Resultado del
    ejercicio' (3.3) y bloquea el período. El resultado = Σingresos − Σegresos."""
    e = db.get(models.EjercicioContable, ejercicio_id)
    if not e:
        raise ReglaNegocioError("Ejercicio inexistente.")
    if e.estado == "cerrado":
        raise ReglaNegocioError("El ejercicio ya está cerrado.")
    bal = balances_por_cuenta(db, e.fecha_desde, e.fecha_hasta, e.empresa_id)
    ctas = _cuentas_empresa(db, e.empresa_id)
    objs: list[models.AsientoLinea] = []
    tot_ing = tot_egr = CERO
    for cod, b in bal.items():
        c = ctas.get(cod)
        rubro = (c.tipo if c else "").lower()
        saldo = b["debe"] - b["haber"]
        if rubro == "ingreso" and saldo != CERO:
            # ingreso tiene saldo acreedor (−) → lo cancelo por el DEBE
            objs.append(models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=c.nombre, debe=-saldo, haber=CERO))
            tot_ing += -saldo
        elif rubro == "egreso" and saldo != CERO:
            objs.append(models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=c.nombre, debe=CERO, haber=saldo))
            tot_egr += saldo
    resultado = tot_ing - tot_egr
    if resultado != CERO:
        cta_res = ctas.get(RESULTADO_EJERCICIO)
        nom = cta_res.nombre if cta_res else "Resultado del ejercicio"
        if resultado > CERO:   # ganancia → acredita PN
            objs.append(models.AsientoLinea(cuenta_codigo=RESULTADO_EJERCICIO, cuenta_nombre=nom, debe=CERO, haber=resultado))
        else:                  # pérdida → debita PN
            objs.append(models.AsientoLinea(cuenta_codigo=RESULTADO_EJERCICIO, cuenta_nombre=nom, debe=-resultado, haber=CERO))
    if objs:
        a = models.Asiento(empresa_id=e.empresa_id, fecha=e.fecha_hasta,
                           concepto=f"Cierre {e.nombre} — refundición de resultados"[:120],
                           origen="cierre", estado="publicado", diario_codigo="VAR",
                           numero=_prox_numero_asiento(db, e.fecha_hasta.year), usuario=usuario, lineas=objs)
        db.add(a); db.flush()
        e.asiento_cierre_id = a.id
    e.estado = "cerrado"; e.resultado = resultado; e.cerrado_en = datetime.now()
    db.commit(); db.refresh(e)
    return e


def reabrir_ejercicio(db: Session, ejercicio_id: int) -> models.EjercicioContable:
    """Reabre un ejercicio cerrado: elimina el asiento de cierre y libera el período."""
    e = db.get(models.EjercicioContable, ejercicio_id)
    if not e:
        raise ReglaNegocioError("Ejercicio inexistente.")
    if e.estado != "cerrado":
        raise ReglaNegocioError("El ejercicio no está cerrado.")
    if e.asiento_cierre_id:
        ac = db.get(models.Asiento, e.asiento_cierre_id)
        if ac:
            db.delete(ac)
    e.estado = "abierto"; e.resultado = CERO; e.asiento_cierre_id = None; e.cerrado_en = None
    db.commit(); db.refresh(e)
    return e


def generar_apertura(db: Session, ejercicio_id: int, usuario: str = "") -> models.Asiento:
    """Genera el ASIENTO DE APERTURA del ejercicio con los saldos patrimoniales (activo/pasivo/PN) al día
    anterior al inicio. Ingresos/egresos no se arrastran (se cerraron en el ejercicio previo)."""
    e = db.get(models.EjercicioContable, ejercicio_id)
    if not e:
        raise ReglaNegocioError("Ejercicio inexistente.")
    if e.asiento_apertura_id:
        raise ReglaNegocioError("El ejercicio ya tiene asiento de apertura.")
    bal = balances_por_cuenta(db, None, e.fecha_desde - timedelta(days=1), e.empresa_id)
    ctas = _cuentas_empresa(db, e.empresa_id)
    objs: list[models.AsientoLinea] = []
    for cod, b in bal.items():
        c = ctas.get(cod)
        rubro = (c.tipo if c else "").lower()
        if rubro not in ("activo", "pasivo", "patrimonio"):
            continue
        saldo = b["debe"] - b["haber"]
        if saldo == CERO:
            continue
        if saldo > CERO:
            objs.append(models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=c.nombre, debe=saldo, haber=CERO))
        else:
            objs.append(models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=c.nombre, debe=CERO, haber=-saldo))
    if not objs:
        raise ReglaNegocioError("No hay saldos patrimoniales del período anterior para la apertura.")
    a = models.Asiento(empresa_id=e.empresa_id, fecha=e.fecha_desde, concepto=f"Apertura {e.nombre}"[:120],
                       origen="apertura", estado="publicado", diario_codigo="VAR",
                       numero=_prox_numero_asiento(db, e.fecha_desde.year), usuario=usuario, lineas=objs)
    db.add(a); db.flush()
    e.asiento_apertura_id = a.id
    db.commit(); db.refresh(a)
    return a


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


def analisis_por_centro(db: Session, desde: date | None = None, hasta: date | None = None,
                        empresa_id: int | None = None) -> dict:
    """Debe/haber/saldo por centro de costo (sólo asientos publicados). Las líneas sin centro van a
    'Sin centro'."""
    emp = _emp(db, empresa_id)
    q = (select(models.AsientoLinea.centro_codigo,
                func.sum(models.AsientoLinea.debe), func.sum(models.AsientoLinea.haber))
         .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
         .where(models.Asiento.estado != "borrador", models.Asiento.empresa_id == emp)
         .group_by(models.AsientoLinea.centro_codigo))
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    nombres = {c.codigo: c.nombre for c in db.scalars(select(models.CentroCosto)).all()}
    filas, td, th = [], CERO, CERO
    for cod, d, h in db.execute(q).all():
        d, h = d or CERO, h or CERO
        td += d; th += h
        filas.append({"codigo": cod or "", "nombre": nombres.get(cod, "Sin centro") if cod else "Sin centro",
                      "debe": d, "haber": h, "saldo": d - h})
    filas.sort(key=lambda f: (f["codigo"] == "", f["codigo"]))
    return {"filas": filas, "totales": {"debe": td, "haber": th}}


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


# ---------------- Asientos manuales (contabilidad general, doble partida) ----------------
def _prox_numero_asiento(db: Session, anio: int) -> int:
    """Correlativo de asientos manuales por año (max+1). Volumen bajo (carga manual)."""
    n = db.scalar(select(func.max(models.Asiento.numero)).where(
        func.extract("year", models.Asiento.fecha) == anio))
    return int(n or 0) + 1


def _lineas_asiento(db: Session, lineas: list[dict], empresa_id: int | None = None) -> list[models.AsientoLinea]:
    """Valida y arma las líneas de un asiento manual (doble partida balanceada, cuentas imputables de la
    empresa)."""
    emp = _emp(db, empresa_id)
    lineas = [l for l in (lineas or []) if (Decimal(str(l.get("debe") or 0)) != CERO or Decimal(str(l.get("haber") or 0)) != CERO)]
    if len(lineas) < 2:
        raise ReglaNegocioError("El asiento necesita al menos 2 líneas con importe.")
    tot_d = tot_h = CERO
    objs: list[models.AsientoLinea] = []
    for l in lineas:
        cod = str(l.get("cuenta_codigo") or "").strip()
        cta = db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == cod,
                                                            models.CuentaContable.empresa_id == emp))
        if not cta:
            raise ReglaNegocioError(f"La cuenta {cod or '(vacía)'} no existe en el plan.")
        if not cta.imputable:
            raise ReglaNegocioError(f"La cuenta {cod} ({cta.nombre}) es de agrupación (no imputable).")
        debe, haber = Decimal(str(l.get("debe") or 0)), Decimal(str(l.get("haber") or 0))
        if debe < CERO or haber < CERO:
            raise ReglaNegocioError("No se permiten importes negativos.")
        if debe > CERO and haber > CERO:
            raise ReglaNegocioError(f"La cuenta {cod} no puede tener debe y haber a la vez.")
        centro = str(l.get("centro_codigo") or "").strip()[:12]
        if centro and not db.scalar(select(models.CentroCosto.id).where(models.CentroCosto.codigo == centro, models.CentroCosto.activo.is_(True))):
            raise ReglaNegocioError(f"El centro de costo {centro} no existe o está inactivo.")
        tot_d += debe; tot_h += haber
        objs.append(models.AsientoLinea(cuenta_codigo=cod, cuenta_nombre=cta.nombre, debe=debe, haber=haber, centro_codigo=centro))
    if tot_d != tot_h:
        raise ReglaNegocioError(f"El asiento no balancea: Σdebe {tot_d} ≠ Σhaber {tot_h}.")
    if tot_d == CERO:
        raise ReglaNegocioError("El asiento no puede ser por importe cero.")
    return objs


def crear_asiento_manual(db: Session, *, fecha: date | None, concepto: str, lineas: list[dict],
                         diario_codigo: str = "VAR", usuario: str = "", empresa_id: int | None = None) -> models.Asiento:
    """Alta de un asiento manual en los libros de la empresa. Nace en BORRADOR (no impacta el mayor hasta
    publicarlo, como Odoo)."""
    if not (concepto or "").strip():
        raise ReglaNegocioError("El concepto es obligatorio.")
    emp = _emp(db, empresa_id)
    f = fecha or date.today()
    _guard_periodo_abierto(db, f, emp)
    objs = _lineas_asiento(db, lineas, emp)
    dcod = (diario_codigo or "VAR").upper()
    if not db.scalar(select(models.DiarioContable.id).where(models.DiarioContable.codigo == dcod)):
        dcod = "VAR"
    a = models.Asiento(empresa_id=emp, fecha=f, concepto=concepto.strip()[:120], origen="manual", estado="borrador",
                       diario_codigo=dcod, numero=_prox_numero_asiento(db, f.year), usuario=usuario, lineas=objs)
    db.add(a); db.commit(); db.refresh(a)
    return a


def editar_asiento_borrador(db: Session, asiento_id: int, *, fecha: date | None, concepto: str,
                            lineas: list[dict], diario_codigo: str | None = None) -> models.Asiento:
    """Edita un asiento en BORRADOR (un publicado es inmutable: se corrige por reversa)."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise ReglaNegocioError("Asiento inexistente.")
    if a.origen != "manual" or a.estado != "borrador":
        raise ReglaNegocioError("Sólo se editan asientos manuales en borrador.")
    if not (concepto or "").strip():
        raise ReglaNegocioError("El concepto es obligatorio.")
    _guard_periodo_abierto(db, fecha or a.fecha, a.empresa_id)
    objs = _lineas_asiento(db, lineas, a.empresa_id)
    for l in list(a.lineas):
        db.delete(l)
    db.flush()
    a.fecha = fecha or a.fecha
    a.concepto = concepto.strip()[:120]
    if diario_codigo:
        dcod = diario_codigo.upper()
        if db.scalar(select(models.DiarioContable.id).where(models.DiarioContable.codigo == dcod)):
            a.diario_codigo = dcod
    a.lineas = objs
    db.commit(); db.refresh(a)
    return a


def publicar_asiento(db: Session, asiento_id: int) -> models.Asiento:
    """Publica (asienta) un borrador: recién ahí impacta el mayor. Es irreversible salvo por reversa."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise ReglaNegocioError("Asiento inexistente.")
    if a.estado != "borrador":
        raise ReglaNegocioError("El asiento ya está publicado.")
    _guard_periodo_abierto(db, a.fecha)
    a.estado = "publicado"
    db.commit(); db.refresh(a)
    return a


def eliminar_asiento_borrador(db: Session, asiento_id: int) -> None:
    """Borra un asiento en borrador (un publicado no se borra: se reversa)."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise ReglaNegocioError("Asiento inexistente.")
    if a.estado != "borrador":
        raise ReglaNegocioError("Sólo se elimina un borrador; un asiento publicado se reversa.")
    db.delete(a); db.commit()


def reversar_asiento(db: Session, asiento_id: int, usuario: str = "") -> models.Asiento:
    """Contra-asiento (reversa) de un asiento manual: invierte debe/haber, marca el original como
    reversado. No borra (event-sourcing/contabilidad: se contra-asienta, no se elimina)."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise ReglaNegocioError("Asiento inexistente.")
    if a.origen not in ("manual",):
        raise ReglaNegocioError("Sólo se pueden reversar asientos manuales.")
    if a.estado == "borrador":
        raise ReglaNegocioError("Un borrador no se reversa: editalo o eliminalo.")
    if a.reversado:
        raise ReglaNegocioError("El asiento ya fue reversado.")
    f = date.today()
    rev = models.Asiento(
        fecha=f, concepto=f"Reversa asiento N° {a.numero or a.id}: {a.concepto}"[:120],
        origen="reversa", estado="publicado", diario_codigo=a.diario_codigo,
        numero=_prox_numero_asiento(db, f.year), usuario=usuario, reversa_de=a.id,
        lineas=[models.AsientoLinea(cuenta_codigo=l.cuenta_codigo, cuenta_nombre=l.cuenta_nombre,
                                    centro_codigo=l.centro_codigo, debe=l.haber, haber=l.debe)
                for l in a.lineas])
    a.reversado = True
    db.add(rev); db.commit(); db.refresh(rev)
    return rev


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


def balanceado(asiento: models.Asiento) -> bool:
    debe = sum((l.debe for l in asiento.lineas), CERO)
    haber = sum((l.haber for l in asiento.lineas), CERO)
    return debe == haber


def balance_sumas_saldos(db: Session, desde=None, hasta=None) -> dict:
    """Balance de sumas y saldos de la contabilidad de la APP (doble partida): por cuenta, total
    debe/haber y saldo deudor/acreedor. Cuadra por diseño (sumas iguales, saldos iguales).
    Excluye el mayor plano legacy migrado de VFP (origen='legacy', de una sola pierna) — ese se
    consulta en el Mayor. Filtrar la app deja el balance cuadrado e instantáneo (H-113)."""
    L = models.AsientoLinea
    q = (select(L.cuenta_codigo, L.cuenta_nombre,
                func.coalesce(func.sum(L.debe), 0), func.coalesce(func.sum(L.haber), 0))
         .join(models.Asiento, models.Asiento.id == L.asiento_id)
         .where(models.Asiento.origen != "legacy")   # sólo contabilidad de la app
         .group_by(L.cuenta_codigo, L.cuenta_nombre)
         .order_by(L.cuenta_codigo))
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)

    filas = []
    tot = {"debe": CERO, "haber": CERO, "deudor": CERO, "acreedor": CERO}
    for cod, nom, debe, haber in db.execute(q).all():
        debe, haber = Decimal(debe), Decimal(haber)
        saldo = debe - haber
        deudor = saldo if saldo > 0 else CERO
        acreedor = -saldo if saldo < 0 else CERO
        filas.append({"cuenta_codigo": cod, "cuenta_nombre": nom,
                      "debe": debe, "haber": haber,
                      "saldo_deudor": deudor, "saldo_acreedor": acreedor})
        tot["debe"] += debe; tot["haber"] += haber
        tot["deudor"] += deudor; tot["acreedor"] += acreedor
    return {"cuentas": filas, "total": tot,
            "cuadra": tot["debe"] == tot["haber"] and tot["deudor"] == tot["acreedor"]}


def iva_periodo(db: Session, desde, hasta) -> dict:
    """IVA débito fiscal (a pagar) del período, a partir de los asientos.

    Informe VFP: cb-iva-a-pagar-periodo. Suma la cuenta 2.1.01 (IVA débito)
    de los asientos de cobranza dentro del rango de fechas.
    """
    q = (
        select(func.coalesce(func.sum(models.AsientoLinea.haber), 0),
               func.count(func.distinct(models.Asiento.id)))
        .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
        .where(models.AsientoLinea.cuenta_codigo == "2.1.01",
               models.Asiento.fecha >= desde, models.Asiento.fecha <= hasta)
    )
    iva, n = db.execute(q).one()
    return {"desde": desde, "hasta": hasta,
            "iva_debito": Decimal(iva), "cantidad_asientos": n}


def iva_egresos(db: Session, desde, hasta) -> dict:
    """IVA de egresos de créditos (VFP: cb-egivaegresos) — desbloqueado por H-011."""
    q = (select(func.coalesce(func.sum(models.OrdenPago.iva), 0),
                func.count(models.OrdenPago.id))
         .where(models.OrdenPago.fecha >= desde, models.OrdenPago.fecha <= hasta))
    iva, n = db.execute(q).one()
    return {"desde": desde, "hasta": hasta, "iva_egresos": Decimal(iva),
            "cantidad_op": n}


def iva_gsoq_periodo(db: Session, desde, hasta) -> dict:
    """IVA de gastos de originación y quebranto por período (VFP: cb-iva-gsoq-periodo)."""
    q = (select(func.coalesce(func.sum(models.Solicitud.iva_gastos_originacion), 0),
                func.coalesce(func.sum(models.Solicitud.iva_quebranto), 0),
                func.count(models.Solicitud.id))
         .where(models.Solicitud.fecha_solicitud >= desde,
                models.Solicitud.fecha_solicitud <= hasta))
    iva_ori, iva_qeb, n = db.execute(q).one()
    return {"desde": desde, "hasta": hasta,
            "iva_gastos_originacion": Decimal(iva_ori),
            "iva_quebranto": Decimal(iva_qeb),
            "iva_total": Decimal(iva_ori) + Decimal(iva_qeb),
            "cantidad_solicitudes": n}


def op_devengadas(db: Session, desde, hasta) -> dict:
    """Órdenes de pago devengadas en el período, por tipo (VFP: cb-op-dev-periodo)."""
    from collections import defaultdict
    ops = db.scalars(select(models.OrdenPago).where(
        models.OrdenPago.fecha >= desde, models.OrdenPago.fecha <= hasta)
        .order_by(models.OrdenPago.fecha)).all()
    por_tipo = defaultdict(lambda: {"cantidad": 0, "total": Decimal("0")})
    total = Decimal("0")
    for o in ops:
        por_tipo[o.tipo]["cantidad"] += 1
        por_tipo[o.tipo]["total"] += o.importe
        total += o.importe
    return {"desde": desde, "hasta": hasta, "cantidad": len(ops), "total": total,
            "por_tipo": [{"tipo": t, "cantidad": v["cantidad"], "total": v["total"]}
                         for t, v in por_tipo.items()]}


def solicitudes_baja(db: Session) -> list[dict]:
    """Solicitudes dadas de baja/rechazadas, para revisión (VFP: cb-crevicredborra)."""
    q = (
        select(models.Solicitud, models.Cliente)
        .join(models.Cliente, models.Cliente.id == models.Solicitud.cliente_id)
        .where(models.Solicitud.estado == "B")
        .order_by(models.Solicitud.id.desc())
    )
    return [{"solicitud_id": s.id, "cliente": c.apellido_nombre, "cuil": c.cuil,
             "monto": s.monto_solicitado, "fecha": s.fecha_solicitud,
             "observaciones": s.observaciones}
            for s, c in db.execute(q).all()]


# ---------------- Reportes sobre el MAYOR REAL (movimientos_contables) ----------------
def balance_mayor(db: Session, *, desde: date | None = None,
                  hasta: date | None = None, periodo: str | None = None) -> dict:
    """Balance de sumas y saldos sobre el libro mayor real (VFP: asientos). Agrupa por
    cuenta: suma débitos y créditos y calcula el saldo (deudor/acreedor). Filtra por
    rango de fechas o por período (YYYYMM)."""
    M = models.MovimientoContable
    q = select(M.cuenta,
               func.coalesce(func.sum(M.debito), 0),
               func.coalesce(func.sum(M.credito), 0),
               func.count(M.id)).group_by(M.cuenta).order_by(M.cuenta)
    if periodo:
        q = q.where(M.periodo == periodo)
    if desde:
        q = q.where(M.fecha >= desde)
    if hasta:
        q = q.where(M.fecha <= hasta)
    filas = []
    tot_deb = tot_cred = CERO
    for cuenta, deb, cred, n in db.execute(q).all():
        deb, cred = Decimal(deb), Decimal(cred)
        saldo = deb - cred
        tot_deb += deb; tot_cred += cred
        filas.append({"cuenta": cuenta, "movimientos": n, "debito": deb,
                      "credito": cred,
                      "saldo_deudor": saldo if saldo > 0 else CERO,
                      "saldo_acreedor": -saldo if saldo < 0 else CERO})
    return {"cantidad_cuentas": len(filas), "total_debito": tot_deb,
            "total_credito": tot_cred, "cuadra": tot_deb == tot_cred, "cuentas": filas}


def mayor_cuenta(db: Session, *, cuenta: str, desde: date | None = None,
                 hasta: date | None = None, limit: int = 200, offset: int = 0) -> dict:
    """Movimientos (mayor) de una cuenta, con saldo acumulado. Paginado."""
    M = models.MovimientoContable
    base = select(M).where(M.cuenta == cuenta)
    if desde:
        base = base.where(M.fecha >= desde)
    if hasta:
        base = base.where(M.fecha <= hasta)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    tot_q = select(func.coalesce(func.sum(M.debito), 0),
                   func.coalesce(func.sum(M.credito), 0)).where(M.cuenta == cuenta)
    if desde:
        tot_q = tot_q.where(M.fecha >= desde)
    if hasta:
        tot_q = tot_q.where(M.fecha <= hasta)
    tot = db.execute(tot_q).one()
    rows = db.scalars(base.order_by(M.fecha, M.norden, M.id)
                      .limit(min(limit, 500)).offset(max(offset, 0))).all()
    items = [{"fecha": m.fecha, "periodo": m.periodo, "referencia": m.referencia,
              "debito": m.debito, "credito": m.credito} for m in rows]
    return {"cuenta": cuenta, "total": total, "limit": limit, "offset": offset,
            "total_debito": Decimal(tot[0]), "total_credito": Decimal(tot[1]),
            "saldo": Decimal(tot[0]) - Decimal(tot[1]), "items": items}


def iva_cuotas_cobradas(db: Session, *, desde: date | None = None,
                        hasta: date | None = None) -> dict:
    """IVA débito fiscal de cuotas de crédito cobradas por período (VFP:
    cb-cjcreditoscobrados / cb-iva-a-pagar-periodo, menú 61005/60505). Suma el IVA de
    las cuotas con `fecha_pago` en el rango (IVA de interés + seguro + gastos adm.),
    agrupado por período (YYYYMM). Fuente real: `maecuotas`."""
    C = models.Cuota
    iva_expr = (C.iva_interes + C.iva_seguro + C.iva_gastos_adm)
    per = func.to_char(C.fecha_pago, "YYYYMM") if db.bind.dialect.name == "postgresql" \
        else func.strftime("%Y%m", C.fecha_pago)
    q = (select(per.label("periodo"), func.count(C.id),
                func.coalesce(func.sum(C.iva_interes), 0),
                func.coalesce(func.sum(C.iva_seguro), 0),
                func.coalesce(func.sum(C.iva_gastos_adm), 0),
                func.coalesce(func.sum(iva_expr), 0))
         .where(C.fecha_pago.isnot(None)).group_by("periodo").order_by("periodo"))
    if desde:
        q = q.where(C.fecha_pago >= desde)
    if hasta:
        q = q.where(C.fecha_pago <= hasta)
    filas, tot = [], CERO
    for periodo, n, ivai, ivas, ivag, ivatot in db.execute(q).all():
        ivatot = Decimal(ivatot)
        tot += ivatot
        filas.append({"periodo": periodo, "cantidad": n,
                      "iva_interes": Decimal(ivai), "iva_seguro": Decimal(ivas),
                      "iva_gastos": Decimal(ivag), "iva_total": ivatot})
    return {"desde": desde, "hasta": hasta, "total_iva": tot,
            "cantidad_periodos": len(filas), "periodos": filas}


def ctacte_contable_credito(db: Session, no_credito: int) -> dict:
    """Cuenta corriente contable de un crédito (VFP: Contabilidad/crctacte.dbf).
    Movimientos con el desglose contable (capital, interés normal/punit/resarc,
    IVA, gastos, sellado) y totales."""
    C = models.CtaCteContableCredito
    filas = db.scalars(select(C).where(C.no_credito == no_credito)
                       .order_by(C.no_cuota, C.fecha_vto)).all()
    items = [{
        "cuenta": c.cuenta, "no_cuota": c.no_cuota, "fecha_vto": c.fecha_vto,
        "fecha_pago": c.fecha_pago, "via_pago": c.via_pago, "capital": c.capital,
        "int_normal": c.int_normal, "iva_normal": c.iva_normal, "gastos": c.gastos,
        "sellado": c.sellado, "int_punit": c.int_punit, "int_resarc": c.int_resarc,
        "debitos": c.debitos, "creditos": c.creditos, "saldo": c.saldo,
        "anulada": c.anulada,
    } for c in filas]
    tot = lambda f: sum((getattr(c, f) for c in filas), CERO)
    return {
        "no_credito": no_credito, "cantidad": len(items),
        "total_debitos": tot("debitos"), "total_creditos": tot("creditos"),
        "total_capital": tot("capital"), "total_int_normal": tot("int_normal"),
        "total_int_punit": tot("int_punit"), "saldo": tot("debitos") - tot("creditos"),
        "items": items,
    }


def contabilidad_general(db: Session, *, desde: date | None = None, hasta: date | None = None,
                         tipo: str | None = None, limit: int = 100, offset: int = 0) -> dict:
    """Contabilidad general de caja/juegos (VFP: Contabilidad/contgral.dbf): por
    asiento/recibo con importes por moneda; totales del filtro."""
    G = models.ContabilidadGeneral
    base = select(G)
    if desde:
        base = base.where(G.fecha >= desde)
    if hasta:
        base = base.where(G.fecha <= hasta)
    if tipo:
        base = base.where(G.tipo == tipo)
    sub = base.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    tp = Decimal(db.scalar(select(func.coalesce(func.sum(sub.c.total_pesos), 0))) or 0)
    tb = Decimal(db.scalar(select(func.coalesce(func.sum(sub.c.total_bonos), 0))) or 0)
    tl = Decimal(db.scalar(select(func.coalesce(func.sum(sub.c.total_lecop), 0))) or 0)
    filas = db.scalars(base.order_by(G.fecha.desc(), G.asiento.desc())
                       .limit(limit).offset(offset)).all()
    items = [{
        "fecha": g.fecha, "periodo": g.periodo, "asiento": g.asiento, "recibo": g.recibo,
        "tipo": g.tipo, "agencia": g.agencia, "destino": g.destino, "origen": g.origen,
        "sorteo": g.sorteo, "moneda": g.moneda, "total_pesos": g.total_pesos,
        "total_bonos": g.total_bonos, "total_lecop": g.total_lecop,
    } for g in filas]
    return {"total": total, "total_pesos": tp, "total_bonos": tb, "total_lecop": tl,
            "limit": limit, "offset": offset, "items": items}
