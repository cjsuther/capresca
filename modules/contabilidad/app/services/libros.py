"""Libros y estados contables: diario, mayor, sumas y saldos, situación patrimonial, resultados y
libro IVA (ventas y compras). Y el cierre del ejercicio.

Los libros son inalterables: un asiento anulado **sigue figurando**, junto a su contra-asiento, que es
el que lo neutraliza. Ocultar sólo el anulado dejaría la reversa suelta y descuadraría el mayor.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services import motor

CERO = Decimal("0.00")


def _f(v) -> float:
    return float(v or 0)


# ── Libro diario ─────────────────────────────────────────────────────────────────────────────────
def diario(db: Session, *, desde: date | None = None, hasta: date | None = None, diario_codigo: str = "",
           solo_vigentes: bool = False, limit: int = 200, offset: int = 0) -> dict:
    q = select(models.Asiento)
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    if diario_codigo:
        q = q.where(models.Asiento.diario_codigo == diario_codigo)
    if solo_vigentes:            # para mirar "lo que quedó", no para los libros
        q = q.where(models.Asiento.estado != "ANULADO")
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    filas = db.scalars(q.order_by(models.Asiento.fecha, models.Asiento.numero)
                        .limit(min(limit, 500)).offset(offset)).all()
    return {"items": [serial_asiento(a) for a in filas], "total": total, "limit": limit, "offset": offset}


def serial_asiento(a: models.Asiento) -> dict:
    return {
        "id": a.id, "numero": a.numero, "fecha": a.fecha.isoformat(), "diario": a.diario_codigo,
        "concepto": a.concepto, "estado": a.estado, "origen": a.origen, "usuario": a.usuario,
        "transaccionId": a.transaccion_id, "definicionId": a.definicion_id,
        "reversaDe": a.reversa_de, "anuladoPorId": a.anulado_por_id,
        "debe": _f(sum((l.debe for l in a.lineas), CERO)),
        "haber": _f(sum((l.haber for l in a.lineas), CERO)),
        "lineas": [{"cuenta": l.cuenta_codigo, "nombre": l.cuenta_nombre, "debe": _f(l.debe),
                    "haber": _f(l.haber), "centro": l.centro_codigo, "detalle": l.detalle}
                   for l in a.lineas],
    }


# ── Mayor ────────────────────────────────────────────────────────────────────────────────────────
def mayor(db: Session, cuenta_codigo: str, *, desde: date | None = None, hasta: date | None = None) -> dict:
    cuenta = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == cuenta_codigo))
    if cuenta is None:
        raise motor.ErrorContable(f"La cuenta {cuenta_codigo} no existe.")
    base = (select(models.AsientoLinea, models.Asiento)
            .join(models.Asiento, models.AsientoLinea.asiento_id == models.Asiento.id)
            .where(models.AsientoLinea.cuenta_codigo == cuenta_codigo))
    anterior = CERO
    if desde:
        for linea, _a in db.execute(base.where(models.Asiento.fecha < desde)).all():
            anterior += linea.debe - linea.haber
    q = base
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    saldo = anterior
    movimientos = []
    for linea, a in db.execute(q.order_by(models.Asiento.fecha, models.Asiento.numero, models.AsientoLinea.id)).all():
        saldo += linea.debe - linea.haber
        movimientos.append({"asientoId": a.id, "numero": a.numero, "fecha": a.fecha.isoformat(),
                            "concepto": a.concepto, "detalle": linea.detalle, "debe": _f(linea.debe),
                            "haber": _f(linea.haber), "saldo": _f(saldo)})
    return {"cuenta": {"codigo": cuenta.codigo, "nombre": cuenta.nombre, "rubro": cuenta.rubro,
                       "saldoNormal": cuenta.saldo_normal},
            "saldoAnterior": _f(anterior), "movimientos": movimientos, "saldoFinal": _f(saldo),
            "debe": _f(sum(Decimal(str(m["debe"])) for m in movimientos)),
            "haber": _f(sum(Decimal(str(m["haber"])) for m in movimientos))}


# ── Sumas y saldos ───────────────────────────────────────────────────────────────────────────────
def sumas_y_saldos(db: Session, *, desde: date | None = None, hasta: date | None = None) -> dict:
    q = (select(models.AsientoLinea.cuenta_codigo, func.sum(models.AsientoLinea.debe),
                func.sum(models.AsientoLinea.haber))
         .join(models.Asiento, models.AsientoLinea.asiento_id == models.Asiento.id)
         .group_by(models.AsientoLinea.cuenta_codigo))
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    cuentas = {c.codigo: c for c in db.scalars(select(models.Cuenta)).all()}
    filas, td, th, tsd, tsa = [], CERO, CERO, CERO, CERO
    for codigo, debe, haber in db.execute(q).all():
        debe, haber = Decimal(str(debe or 0)), Decimal(str(haber or 0))
        saldo = debe - haber
        c = cuentas.get(codigo)
        filas.append({"cuenta": codigo, "nombre": c.nombre if c else "", "rubro": c.rubro if c else "",
                      "debe": _f(debe), "haber": _f(haber),
                      "saldoDeudor": _f(saldo if saldo > 0 else CERO),
                      "saldoAcreedor": _f(-saldo if saldo < 0 else CERO)})
        td += debe; th += haber
        tsd += saldo if saldo > 0 else CERO
        tsa += -saldo if saldo < 0 else CERO
    filas.sort(key=lambda f: f["cuenta"])
    return {"items": filas, "totales": {"debe": _f(td), "haber": _f(th),
                                        "saldoDeudor": _f(tsd), "saldoAcreedor": _f(tsa)},
            "balanceado": td == th}


# ── Estados contables ────────────────────────────────────────────────────────────────────────────
def estados(db: Session, *, desde: date | None = None, hasta: date | None = None) -> dict:
    """Situación patrimonial (activo, pasivo, patrimonio) y resultados (ingresos, egresos)."""
    saldos = sumas_y_saldos(db, desde=desde, hasta=hasta)["items"]
    por_rubro: dict[str, list] = {r: [] for r in models.RUBROS}
    for f in saldos:
        rubro = f["rubro"] or "ACTIVO"
        # Deudor positivo para activo/egreso; acreedor positivo para pasivo/patrimonio/ingreso.
        saldo = f["saldoDeudor"] - f["saldoAcreedor"]
        importe = saldo if rubro in ("ACTIVO", "EGRESO") else -saldo
        if importe == 0:
            continue
        por_rubro.setdefault(rubro, []).append({"cuenta": f["cuenta"], "nombre": f["nombre"], "importe": importe})
    total = lambda r: round(sum(x["importe"] for x in por_rubro.get(r, [])), 2)  # noqa: E731
    activo, pasivo, patrimonio = total("ACTIVO"), total("PASIVO"), total("PATRIMONIO")
    ingresos, egresos = total("INGRESO"), total("EGRESO")
    resultado = round(ingresos - egresos, 2)
    return {
        "situacion": {"activo": {"total": activo, "cuentas": por_rubro.get("ACTIVO", [])},
                      "pasivo": {"total": pasivo, "cuentas": por_rubro.get("PASIVO", [])},
                      "patrimonio": {"total": patrimonio, "cuentas": por_rubro.get("PATRIMONIO", [])},
                      "resultadoDelEjercicio": resultado,
                      # Activo = Pasivo + Patrimonio + Resultado del ejercicio (aún sin refundir).
                      "ecuacionCierra": round(activo - (pasivo + patrimonio + resultado), 2) == 0},
        "resultados": {"ingresos": {"total": ingresos, "cuentas": por_rubro.get("INGRESO", [])},
                       "egresos": {"total": egresos, "cuentas": por_rubro.get("EGRESO", [])},
                       "resultado": resultado},
        "periodo": {"desde": desde.isoformat() if desde else None, "hasta": hasta.isoformat() if hasta else None},
    }


# ── Libro IVA ────────────────────────────────────────────────────────────────────────────────────
def libro_iva(db: Session, libro: str, *, desde: date | None = None, hasta: date | None = None) -> dict:
    q = select(models.ComprobanteIva).where(models.ComprobanteIva.libro == libro.upper())
    if desde:
        q = q.where(models.ComprobanteIva.fecha >= desde)
    if hasta:
        q = q.where(models.ComprobanteIva.fecha <= hasta)
    filas = db.scalars(q.order_by(models.ComprobanteIva.fecha, models.ComprobanteIva.id)).all()
    items = [{"id": c.id, "fecha": c.fecha.isoformat(), "tipoComprobante": c.tipo_comprobante,
              "puntoVenta": c.punto_venta, "numero": c.numero, "cuit": c.cuit,
              "razonSocial": c.razon_social, "condicionIva": c.condicion_iva,
              "netoGravado": _f(c.neto_gravado), "netoNoGravado": _f(c.neto_no_gravado),
              "exento": _f(c.exento), "alicuota": _f(c.alicuota), "iva": _f(c.iva),
              "percepciones": _f(c.percepciones), "retenciones": _f(c.retenciones), "total": _f(c.total),
              "asientoId": c.asiento_id, "transaccionId": c.transaccion_id} for c in filas]
    por_alicuota: dict[str, dict] = {}
    for c in filas:
        k = f"{_f(c.alicuota):.2f}"
        acum = por_alicuota.setdefault(k, {"alicuota": _f(c.alicuota), "neto": 0.0, "iva": 0.0})
        acum["neto"] = round(acum["neto"] + _f(c.neto_gravado), 2)
        acum["iva"] = round(acum["iva"] + _f(c.iva), 2)
    sumar = lambda campo: round(sum(i[campo] for i in items), 2)  # noqa: E731
    return {"libro": libro.upper(), "items": items,
            "totales": {"netoGravado": sumar("netoGravado"), "netoNoGravado": sumar("netoNoGravado"),
                        "exento": sumar("exento"), "iva": sumar("iva"),
                        "percepciones": sumar("percepciones"), "retenciones": sumar("retenciones"),
                        "total": sumar("total")},
            "porAlicuota": sorted(por_alicuota.values(), key=lambda x: x["alicuota"])}


# ── Cierre de ejercicio ──────────────────────────────────────────────────────────────────────────
def cerrar_ejercicio(db: Session, ejercicio: models.Ejercicio, usuario: str) -> dict:
    """Refunde los resultados contra la cuenta de resultado del ejercicio y lo deja CERRADO.

    Los saldos patrimoniales no se tocan: siguen vivos en el ejercicio siguiente (que arranca con su
    asiento de apertura, si se quiere abrir con saldos iniciales)."""
    if ejercicio.estado != "ABIERTO":
        raise motor.ErrorContable("El ejercicio ya está cerrado.")
    pendientes = db.scalar(select(func.count()).select_from(models.Transaccion).where(
        models.Transaccion.estado.in_(["PENDIENTE_CONFIGURACION", "ERROR"]),
        models.Transaccion.fecha >= ejercicio.desde, models.Transaccion.fecha <= ejercicio.hasta)) or 0
    if pendientes:
        raise motor.ErrorContable(
            f"Hay {pendientes} transacción(es) sin contabilizar en el ejercicio: resolvelas antes de cerrar.")
    if not ejercicio.cuenta_resultado:
        raise motor.ErrorContable("Indicá la cuenta de resultado del ejercicio para poder cerrarlo.")

    datos = estados(db, desde=ejercicio.desde, hasta=ejercicio.hasta)["resultados"]
    lineas = []
    for c in datos["ingresos"]["cuentas"]:
        lineas.append({"cuenta_codigo": c["cuenta"], "cuenta_nombre": c["nombre"],
                       "debe": Decimal(str(c["importe"])), "haber": CERO, "centro_codigo": "",
                       "detalle": "Refundición de resultados"})
    for c in datos["egresos"]["cuentas"]:
        lineas.append({"cuenta_codigo": c["cuenta"], "cuenta_nombre": c["nombre"],
                       "debe": CERO, "haber": Decimal(str(c["importe"])), "centro_codigo": "",
                       "detalle": "Refundición de resultados"})
    resultado = Decimal(str(datos["resultado"]))
    if lineas:
        cuenta = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == ejercicio.cuenta_resultado))
        if cuenta is None:
            raise motor.ErrorContable(f"La cuenta de resultado {ejercicio.cuenta_resultado} no existe.")
        lineas.append({"cuenta_codigo": cuenta.codigo, "cuenta_nombre": cuenta.nombre,
                       "debe": CERO if resultado >= 0 else -resultado,
                       "haber": resultado if resultado >= 0 else CERO,
                       "centro_codigo": "", "detalle": "Resultado del ejercicio"})
        asiento = motor.registrar_asiento(
            db, fecha=ejercicio.hasta, concepto=f"Cierre del ejercicio {ejercicio.numero}",
            lineas=lineas, diario="VAR", origen="CIERRE", usuario=usuario)
    else:
        asiento = None
    ejercicio.estado = "CERRADO"
    ejercicio.cerrado_por = usuario
    from datetime import datetime
    ejercicio.cerrado_en = datetime.now()
    db.commit()
    return {"ejercicio": ejercicio.numero, "resultado": _f(resultado),
            "asientoCierre": asiento.numero if asiento else None}
