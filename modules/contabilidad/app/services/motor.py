"""Motor contable: de la transacción al asiento.

Nadie manda asientos: se reciben transacciones y acá se resuelven contra su `DefinicionAsiento`.
  1. llega la transacción (idempotente por módulo + tipo + referencia);
  2. se busca la definición vigente para ese módulo y tipo;
  3. sin definición → la transacción queda **PENDIENTE_CONFIGURACION** (no se inventa un asiento);
  4. con definición → se calculan los importes, se valida la partida doble y se registra el asiento.

Al dar de alta o corregir una definición se reprocesan las transacciones que la estaban esperando.
"""
from __future__ import annotations

import ast
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")


class SinDefinicion(Exception):
    """No hay definición vigente para ese tipo de transacción: queda pendiente de configuración."""


class ErrorContable(Exception):
    """La definición existe pero no se puede aplicar (cuenta inexistente, no balancea, ejercicio cerrado…)."""


# ── Importes de la definición ────────────────────────────────────────────────────────────────────
_OPERADORES = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)


def calcular(expresion, datos: dict) -> Decimal:
    """Evalúa una expresión de la definición sobre los datos de la transacción.

    Acepta números, los campos que mandó el módulo y + - * / con paréntesis. Nada más: no se ejecuta
    código arbitrario de una definición cargada por pantalla.
    """
    if expresion is None or expresion == "":
        return CERO
    if isinstance(expresion, (int, float, Decimal)):
        return _dec(expresion)
    texto = str(expresion).strip()
    try:
        arbol = ast.parse(texto, mode="eval").body
    except SyntaxError as e:
        raise ErrorContable(f"Importe inválido en la definición: «{texto}».") from e
    return _dec(_evaluar(arbol, datos, texto))


def _evaluar(nodo, datos: dict, texto: str):
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, (int, float)):
            return Decimal(str(nodo.value))
        raise ErrorContable(f"Importe inválido en la definición: «{texto}».")
    if isinstance(nodo, ast.Name):
        return _dec(datos.get(nodo.id, 0))
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, _OPERADORES):
        a, b = _evaluar(nodo.left, datos, texto), _evaluar(nodo.right, datos, texto)
        if isinstance(nodo.op, ast.Add):
            return a + b
        if isinstance(nodo.op, ast.Sub):
            return a - b
        if isinstance(nodo.op, ast.Mult):
            return a * b
        if b == 0:
            raise ErrorContable(f"División por cero en la definición: «{texto}».")
        return a / b
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, _OPERADORES):
        v = _evaluar(nodo.operand, datos, texto)
        return -v if isinstance(nodo.op, ast.USub) else v
    raise ErrorContable(f"Importe no permitido en la definición: «{texto}».")


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ErrorContable(f"Importe inválido: «{v}».")


# ── Definiciones ─────────────────────────────────────────────────────────────────────────────────
def definicion_para(db: Session, modulo: str, tipo: str, fecha: date) -> models.DefinicionAsiento | None:
    """Definición activa y vigente a esa fecha (la más específica: la que empezó más tarde)."""
    q = (select(models.DefinicionAsiento)
         .where(models.DefinicionAsiento.modulo == modulo, models.DefinicionAsiento.tipo == tipo,
                models.DefinicionAsiento.activa.is_(True))
         .order_by(models.DefinicionAsiento.vigente_desde.desc().nullslast(),
                   models.DefinicionAsiento.id.desc()))
    for d in db.scalars(q).all():
        if d.vigente_desde and fecha < d.vigente_desde:
            continue
        if d.vigente_hasta and fecha > d.vigente_hasta:
            continue
        return d
    return None


# ── Ejercicio y numeración ───────────────────────────────────────────────────────────────────────
def ejercicio_de(db: Session, fecha: date) -> models.Ejercicio:
    ej = db.scalar(select(models.Ejercicio).where(models.Ejercicio.desde <= fecha,
                                                  models.Ejercicio.hasta >= fecha))
    if ej is None:
        raise ErrorContable(f"No hay un ejercicio contable que incluya el {fecha:%d/%m/%Y}.")
    if ej.estado != "ABIERTO":
        raise ErrorContable(f"El ejercicio {ej.numero} está cerrado: no admite asientos.")
    return ej


def _proximo_numero(db: Session, ejercicio_id: int) -> int:
    ultimo = db.scalar(select(func.max(models.Asiento.numero)).where(models.Asiento.ejercicio_id == ejercicio_id))
    return (ultimo or 0) + 1


# ── Armado del asiento ───────────────────────────────────────────────────────────────────────────
def _cuenta(db: Session, codigo: str) -> models.Cuenta:
    c = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == codigo))
    if c is None:
        raise ErrorContable(f"La cuenta {codigo} no existe en el plan de cuentas.")
    if not c.activa:
        raise ErrorContable(f"La cuenta {codigo} está dada de baja.")
    if not c.imputable:
        raise ErrorContable(f"La cuenta {codigo} es de agrupación: no recibe asientos.")
    return c


def lineas_de(db: Session, definicion: models.DefinicionAsiento, datos: dict) -> list[dict]:
    """Aplica la definición a los datos de la transacción. Devuelve las líneas ya calculadas."""
    if not definicion.lineas:
        raise ErrorContable("La definición no tiene líneas cargadas.")
    salida = []
    for i, linea in enumerate(definicion.lineas, start=1):
        importe = calcular(linea.get("importe"), datos)
        if importe < 0:
            raise ErrorContable(f"Línea {i}: el importe calculado es negativo ({importe}).")
        if importe == 0 and linea.get("omitir_si_cero", True):
            continue
        cuenta = _cuenta(db, str(linea.get("cuenta") or ""))
        dc = str(linea.get("dc") or "DEBE").upper()
        if dc not in ("DEBE", "HABER"):
            raise ErrorContable(f"Línea {i}: el lado debe ser DEBE o HABER.")
        centro = str(linea.get("centro") or "")
        if cuenta.requiere_centro and not centro:
            raise ErrorContable(f"La cuenta {cuenta.codigo} exige centro de costo y la definición no lo trae.")
        salida.append({"cuenta_codigo": cuenta.codigo, "cuenta_nombre": cuenta.nombre,
                       "debe": importe if dc == "DEBE" else CERO,
                       "haber": importe if dc == "HABER" else CERO,
                       "centro_codigo": centro,
                       "detalle": _plantilla(str(linea.get("detalle") or ""), datos)})
    if not salida:
        raise ErrorContable("Todas las líneas dieron importe cero: no hay asiento que registrar.")
    return salida


def validar_partida_doble(lineas: list[dict]) -> tuple[Decimal, Decimal]:
    debe = sum((Decimal(str(l["debe"])) for l in lineas), CERO)
    haber = sum((Decimal(str(l["haber"])) for l in lineas), CERO)
    if debe != haber:
        raise ErrorContable(f"El asiento no balancea: debe {debe} ≠ haber {haber}.")
    if debe == CERO:
        raise ErrorContable("El asiento está en cero.")
    return debe, haber


def _plantilla(texto: str, datos: dict) -> str:
    """Reemplaza {campo} por el dato de la transacción (sin romper si falta)."""
    salida = texto
    for k, v in (datos or {}).items():
        salida = salida.replace("{" + str(k) + "}", str(v))
    return salida[:200]


def registrar_asiento(db: Session, *, fecha: date, concepto: str, lineas: list[dict], diario: str,
                      origen: str, usuario: str, transaccion_id: int | None = None,
                      definicion_id: int | None = None, reversa_de: int | None = None) -> models.Asiento:
    validar_partida_doble(lineas)
    ej = ejercicio_de(db, fecha)
    asiento = models.Asiento(ejercicio_id=ej.id, numero=_proximo_numero(db, ej.id), fecha=fecha,
                             diario_codigo=diario or "VAR", concepto=concepto[:200], origen=origen,
                             transaccion_id=transaccion_id, definicion_id=definicion_id,
                             reversa_de=reversa_de, usuario=usuario or "sistema")
    asiento.lineas = [models.AsientoLinea(**l) for l in lineas]
    db.add(asiento)
    db.flush()
    return asiento


# ── Circuito: transacción → asiento ──────────────────────────────────────────────────────────────
def contabilizar(db: Session, t: models.Transaccion, usuario: str = "") -> models.Transaccion:
    """Intenta contabilizar la transacción. Deja su estado y el motivo si no se pudo."""
    if t.estado == "CONTABILIZADA":
        return t
    definicion = definicion_para(db, t.modulo, t.tipo, t.fecha)
    if definicion is None:
        t.estado = "PENDIENTE_CONFIGURACION"
        t.motivo = f"Falta definir cómo se contabiliza «{t.tipo}» de {t.modulo}."
        return t
    try:
        lineas = lineas_de(db, definicion, dict(t.datos or {}))
        concepto = _plantilla(definicion.leyenda or definicion.nombre, {**(t.datos or {}),
                                                                        "referencia": t.referencia,
                                                                        "descripcion": t.descripcion})
        asiento = registrar_asiento(db, fecha=t.fecha, concepto=concepto or t.descripcion, lineas=lineas,
                                    diario=definicion.diario_codigo, origen="TRANSACCION",
                                    usuario=usuario or t.usuario_origen, transaccion_id=t.id,
                                    definicion_id=definicion.id)
        t.asiento_id = asiento.id
        t.estado, t.motivo = "CONTABILIZADA", ""
        t.procesada_en = datetime.now()
        _registrar_iva(db, t, asiento)
    except ErrorContable as e:
        t.estado, t.motivo = "ERROR", str(e)[:300]
    return t


def _registrar_iva(db: Session, t: models.Transaccion, asiento: models.Asiento) -> None:
    """Si la transacción trae un comprobante fiscal, se anota en el libro IVA (ventas o compras)."""
    comp = (t.datos or {}).get("comprobante")
    if not isinstance(comp, dict) or not comp.get("libro"):
        return
    libro = str(comp["libro"]).upper()
    if libro not in ("VENTAS", "COMPRAS"):
        raise ErrorContable("El comprobante debe ser del libro VENTAS o COMPRAS.")
    ya = db.scalar(select(models.ComprobanteIva).where(
        models.ComprobanteIva.libro == libro,
        models.ComprobanteIva.tipo_comprobante == str(comp.get("tipo_comprobante") or "01"),
        models.ComprobanteIva.punto_venta == int(comp.get("punto_venta") or 0),
        models.ComprobanteIva.numero == int(comp.get("numero") or 0),
        models.ComprobanteIva.cuit == str(comp.get("cuit") or "")))
    if ya:
        return
    db.add(models.ComprobanteIva(
        libro=libro, fecha=t.fecha, tipo_comprobante=str(comp.get("tipo_comprobante") or "01"),
        punto_venta=int(comp.get("punto_venta") or 0), numero=int(comp.get("numero") or 0),
        cuit="".join(ch for ch in str(comp.get("cuit") or "") if ch.isdigit())[:11],
        razon_social=str(comp.get("razon_social") or "")[:120],
        condicion_iva=str(comp.get("condicion_iva") or "")[:30],
        neto_gravado=_dec(comp.get("neto_gravado")), neto_no_gravado=_dec(comp.get("neto_no_gravado")),
        exento=_dec(comp.get("exento")), alicuota=_dec(comp.get("alicuota") or 21),
        iva=_dec(comp.get("iva")), percepciones=_dec(comp.get("percepciones")),
        retenciones=_dec(comp.get("retenciones")), total=_dec(comp.get("total")),
        transaccion_id=t.id, asiento_id=asiento.id, detalle=str(comp.get("detalle") or "")))


def recibir(db: Session, datos: dict) -> tuple[models.Transaccion, bool]:
    """Alta idempotente de una transacción + intento de contabilizarla. Devuelve (transacción, ya_existía)."""
    modulo, tipo = str(datos["modulo"]), str(datos["tipo"])
    referencia = str(datos["referencia"])[:80]
    ya = db.scalar(select(models.Transaccion).where(models.Transaccion.modulo == modulo,
                                                    models.Transaccion.tipo == tipo,
                                                    models.Transaccion.referencia == referencia))
    if ya:
        return ya, True
    t = models.Transaccion(modulo=modulo, tipo=tipo, referencia=referencia, fecha=datos["fecha"],
                           moneda=str(datos.get("moneda") or "ARS"),
                           descripcion=str(datos.get("descripcion") or "")[:200],
                           datos=datos.get("datos") or {},
                           usuario_origen=str(datos.get("usuario") or "")[:60])
    db.add(t)
    db.flush()
    contabilizar(db, t)
    db.commit()
    db.refresh(t)
    return t, False


def reprocesar_pendientes(db: Session, *, modulo: str = "", tipo: str = "", usuario: str = "") -> dict:
    """Vuelve a intentar las que estaban esperando la definición (o dieron error)."""
    q = select(models.Transaccion).where(models.Transaccion.estado.in_(["PENDIENTE_CONFIGURACION", "ERROR"]))
    if modulo:
        q = q.where(models.Transaccion.modulo == modulo)
    if tipo:
        q = q.where(models.Transaccion.tipo == tipo)
    contabilizadas, pendientes, errores = 0, 0, 0
    for t in db.scalars(q.order_by(models.Transaccion.fecha, models.Transaccion.id)).all():
        contabilizar(db, t, usuario)
        contabilizadas += t.estado == "CONTABILIZADA"
        pendientes += t.estado == "PENDIENTE_CONFIGURACION"
        errores += t.estado == "ERROR"
    db.commit()
    return {"contabilizadas": contabilizadas, "pendientes": pendientes, "errores": errores}


def anular(db: Session, asiento: models.Asiento, usuario: str, motivo: str = "") -> models.Asiento:
    """Contra-asiento: un asiento no se borra ni se edita (libro inalterable)."""
    if asiento.estado == "ANULADO":
        raise ErrorContable("El asiento ya está anulado.")
    if asiento.origen == "REVERSA":
        raise ErrorContable("Un contra-asiento no se anula.")
    lineas = [{"cuenta_codigo": l.cuenta_codigo, "cuenta_nombre": l.cuenta_nombre,
               "debe": l.haber, "haber": l.debe, "centro_codigo": l.centro_codigo,
               "detalle": l.detalle} for l in asiento.lineas]
    concepto = f"Anulación del asiento {asiento.numero}" + (f" · {motivo}" if motivo else "")
    reversa = registrar_asiento(db, fecha=date.today(), concepto=concepto, lineas=lineas,
                                diario=asiento.diario_codigo, origen="REVERSA", usuario=usuario,
                                transaccion_id=asiento.transaccion_id, reversa_de=asiento.id)
    asiento.estado = "ANULADO"
    asiento.anulado_por_id = reversa.id
    if asiento.transaccion_id:
        t = db.get(models.Transaccion, asiento.transaccion_id)
        if t:
            t.estado, t.motivo = "ANULADA", motivo[:300] or f"Asiento {asiento.numero} anulado"
    db.commit()
    return reversa
