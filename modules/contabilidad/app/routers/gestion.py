"""API de las pantallas: plan de cuentas, centros, diarios, ejercicios, definiciones, transacciones,
asientos y libros."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.services import conciliacion, libros, motor

# Todo el módulo pide, como mínimo, el permiso de consulta (el gateway ya lo exige; acá se revalida
# por si una request no pasó por él).
router = APIRouter(prefix="/contabilidad", tags=["contabilidad"],
                   dependencies=[Depends(requiere("asientos:read"))])

_escribe = requiere("asientos:write")
_configura = requiere("definiciones:write")
_cierra = requiere("ejercicios:write")


def _error(e: motor.ErrorContable) -> HTTPException:
    return HTTPException(422, str(e))


# ── Plan de cuentas ──────────────────────────────────────────────────────────────────────────────
class CuentaIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=120)
    rubro: str
    imputable: bool = True
    saldo_normal: str = "DEUDOR"
    moneda: str = "ARS"
    ajustable: bool = False
    requiere_centro: bool = False
    descripcion: str = ""
    activa: bool = True


def _serial_cuenta(c: models.Cuenta, movimientos: int = 0) -> dict:
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "rubro": c.rubro,
            "imputable": c.imputable, "saldoNormal": c.saldo_normal, "moneda": c.moneda,
            "ajustable": c.ajustable, "requiereCentro": c.requiere_centro,
            "descripcion": c.descripcion, "activa": c.activa,
            "nivel": c.codigo.count(".") + 1,
            # Una cuenta en uso no se borra ni cambia de rubro: la pantalla lo muestra.
            "movimientos": movimientos, "enUso": movimientos > 0}


@router.get("/cuentas")
def listar_cuentas(solo_imputables: bool = False, db: Session = Depends(get_db)):
    q = select(models.Cuenta).order_by(models.Cuenta.codigo)
    if solo_imputables:
        q = q.where(models.Cuenta.imputable.is_(True), models.Cuenta.activa.is_(True))
    usos = dict(db.execute(select(models.AsientoLinea.cuenta_codigo, func.count())
                           .group_by(models.AsientoLinea.cuenta_codigo)).all())
    items = [_serial_cuenta(c, int(usos.get(c.codigo, 0))) for c in db.scalars(q).all()]
    return {"items": items, "total": len(items), "rubros": list(models.RUBROS)}


@router.post("/cuentas", status_code=201, dependencies=[Depends(_configura)])
def crear_cuenta(data: CuentaIn, db: Session = Depends(get_db)):
    if data.rubro not in models.RUBROS:
        raise HTTPException(422, f"Rubro inválido. Opciones: {', '.join(models.RUBROS)}.")
    if db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == data.codigo)):
        raise HTTPException(409, "Ya existe una cuenta con ese código.")
    c = models.Cuenta(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _serial_cuenta(c)


@router.put("/cuentas/{cuenta_id}", dependencies=[Depends(_configura)])
def editar_cuenta(cuenta_id: int, data: CuentaIn, db: Session = Depends(get_db)):
    c = db.get(models.Cuenta, cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    usada = db.scalar(select(func.count()).select_from(models.AsientoLinea)
                      .where(models.AsientoLinea.cuenta_codigo == c.codigo)) or 0
    if usada and data.codigo != c.codigo:
        raise HTTPException(409, "La cuenta ya tiene asientos: no se puede cambiar su código.")
    if usada and not data.imputable:
        raise HTTPException(409, "La cuenta ya tiene asientos: no puede pasar a ser de agrupación.")
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return _serial_cuenta(c)


# ── Entes contables (razón social, CUIT, condición frente al IVA) ───────────────────────────────
class EmpresaIn(BaseModel):
    razon_social: str = Field(min_length=1, max_length=120)
    cuit: str = ""
    condicion_iva: str = "RESPONSABLE_INSCRIPTO"
    domicilio: str = ""
    inicio_actividades: date | None = None


def _serial_empresa(e: models.Empresa) -> dict:
    return {"id": e.id, "razonSocial": e.razon_social, "cuit": e.cuit, "condicionIva": e.condicion_iva,
            "domicilio": e.domicilio, "predeterminada": e.predeterminada,
            "inicioActividades": e.inicio_actividades.isoformat() if e.inicio_actividades else None}


@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)):
    items = [_serial_empresa(e) for e in db.scalars(select(models.Empresa).order_by(models.Empresa.id)).all()]
    return {"items": items, "total": len(items)}


@router.post("/empresas", status_code=201, dependencies=[Depends(_configura)])
def crear_empresa(data: EmpresaIn, db: Session = Depends(get_db)):
    e = models.Empresa(**{**data.model_dump(), "cuit": "".join(ch for ch in data.cuit if ch.isdigit())[:11]},
                       predeterminada=not db.scalar(select(models.Empresa).limit(1)))
    db.add(e); db.commit(); db.refresh(e)
    return _serial_empresa(e)


@router.put("/empresas/{empresa_id}", dependencies=[Depends(_configura)])
def editar_empresa(empresa_id: int, data: EmpresaIn, db: Session = Depends(get_db)):
    e = db.get(models.Empresa, empresa_id)
    if not e:
        raise HTTPException(404, "Ente contable no encontrado")
    for k, v in data.model_dump().items():
        setattr(e, k, "".join(ch for ch in v if ch.isdigit())[:11] if k == "cuit" else v)
    db.commit(); db.refresh(e)
    return _serial_empresa(e)


# ── Centros de costo y diarios ───────────────────────────────────────────────────────────────────
class CentroIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=12)
    nombre: str = Field(min_length=1, max_length=80)
    activo: bool = True


@router.get("/centros")
def listar_centros(db: Session = Depends(get_db)):
    items = [{"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo}
             for c in db.scalars(select(models.CentroCosto).order_by(models.CentroCosto.codigo)).all()]
    return {"items": items, "total": len(items)}


@router.post("/centros", status_code=201, dependencies=[Depends(_configura)])
def crear_centro(data: CentroIn, db: Session = Depends(get_db)):
    if db.scalar(select(models.CentroCosto).where(models.CentroCosto.codigo == data.codigo)):
        raise HTTPException(409, "Ya existe un centro con ese código.")
    c = models.CentroCosto(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo}


@router.get("/diarios")
def listar_diarios(db: Session = Depends(get_db)):
    items = [{"id": d.id, "codigo": d.codigo, "nombre": d.nombre, "activo": d.activo}
             for d in db.scalars(select(models.Diario).order_by(models.Diario.codigo)).all()]
    return {"items": items, "total": len(items)}


@router.delete("/cuentas/{cuenta_id}", status_code=204, dependencies=[Depends(_configura)])
def borrar_cuenta(cuenta_id: int, db: Session = Depends(get_db)):
    """Sólo se borra una cuenta que nunca se usó; si tiene asientos, se da de baja (queda en los libros)."""
    c = db.get(models.Cuenta, cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    usada = db.scalar(select(func.count()).select_from(models.AsientoLinea)
                      .where(models.AsientoLinea.cuenta_codigo == c.codigo)) or 0
    if usada:
        raise HTTPException(409, f"La cuenta tiene {usada} movimiento(s): dala de baja en vez de borrarla.")
    en_definiciones = [d.nombre for d in db.scalars(select(models.DefinicionAsiento)).all()
                       if any(l.get("cuenta") == c.codigo for l in (d.lineas or []))]
    if en_definiciones:
        raise HTTPException(409, f"La usa la definición «{en_definiciones[0]}».")
    db.delete(c); db.commit()


@router.put("/centros/{centro_id}", dependencies=[Depends(_configura)])
def editar_centro(centro_id: int, data: CentroIn, db: Session = Depends(get_db)):
    c = db.get(models.CentroCosto, centro_id)
    if not c:
        raise HTTPException(404, "Centro no encontrado")
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo}


# ── Ejercicios ───────────────────────────────────────────────────────────────────────────────────
class EjercicioIn(BaseModel):
    numero: int
    desde: date
    hasta: date
    cuenta_resultado: str = "3.1.03"


def _serial_ejercicio(e: models.Ejercicio) -> dict:
    return {"id": e.id, "numero": e.numero, "desde": e.desde.isoformat(), "hasta": e.hasta.isoformat(),
            "estado": e.estado, "cuentaResultado": e.cuenta_resultado, "cerradoPor": e.cerrado_por,
            "cerradoEn": e.cerrado_en.isoformat() if e.cerrado_en else None}


@router.get("/ejercicios")
def listar_ejercicios(db: Session = Depends(get_db)):
    items = [_serial_ejercicio(e) for e in db.scalars(
        select(models.Ejercicio).order_by(models.Ejercicio.numero.desc())).all()]
    return {"items": items, "total": len(items)}


@router.post("/ejercicios", status_code=201, dependencies=[Depends(_cierra)])
def crear_ejercicio(data: EjercicioIn, db: Session = Depends(get_db)):
    if data.hasta <= data.desde:
        raise HTTPException(422, "El ejercicio termina antes de empezar.")
    if db.scalar(select(models.Ejercicio).where(models.Ejercicio.numero == data.numero)):
        raise HTTPException(409, "Ya existe ese ejercicio.")
    solapa = db.scalar(select(models.Ejercicio).where(models.Ejercicio.desde <= data.hasta,
                                                      models.Ejercicio.hasta >= data.desde))
    if solapa:
        raise HTTPException(409, f"Se superpone con el ejercicio {solapa.numero}.")
    e = models.Ejercicio(**data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return _serial_ejercicio(e)


@router.post("/ejercicios/{ejercicio_id}/cerrar", dependencies=[Depends(_cierra)])
def cerrar_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    e = db.get(models.Ejercicio, ejercicio_id)
    if not e:
        raise HTTPException(404, "Ejercicio no encontrado")
    try:
        return libros.cerrar_ejercicio(db, e, user.username)
    except motor.ErrorContable as err:
        raise _error(err)


@router.post("/ejercicios/{ejercicio_id}/reabrir", dependencies=[Depends(_cierra)])
def reabrir_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    """Vuelve a abrirlo y anula su asiento de cierre (los dos quedan en el libro)."""
    e = db.get(models.Ejercicio, ejercicio_id)
    if not e:
        raise HTTPException(404, "Ejercicio no encontrado")
    try:
        return motor.reabrir_ejercicio(db, e, user.username)
    except motor.ErrorContable as err:
        raise _error(err)


@router.post("/ejercicios/{ejercicio_id}/apertura", dependencies=[Depends(_cierra)])
def apertura_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    """Asiento de apertura con los saldos patrimoniales del ejercicio anterior."""
    e = db.get(models.Ejercicio, ejercicio_id)
    if not e:
        raise HTTPException(404, "Ejercicio no encontrado")
    try:
        a = motor.asiento_apertura(db, e, user.username)
        db.commit()
    except motor.ErrorContable as err:
        db.rollback()
        raise _error(err)
    return libros.serial_asiento(a)


# ── Definiciones (cómo se contabiliza cada transacción) ──────────────────────────────────────────
class LineaDefinicionIn(BaseModel):
    cuenta: str
    dc: str = "DEBE"
    importe: str                     # expresión sobre los datos: "capital", "interes + iva"…
    centro: str = ""
    detalle: str = ""
    omitir_si_cero: bool = True


class DefinicionIn(BaseModel):
    modulo: str = Field(min_length=1, max_length=30)
    tipo: str = Field(min_length=1, max_length=60)
    nombre: str = Field(min_length=1, max_length=120)
    diario_codigo: str = "VAR"
    leyenda: str = ""
    lineas: list[LineaDefinicionIn] = Field(min_length=2)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    activa: bool = True


def _serial_definicion(d: models.DefinicionAsiento) -> dict:
    return {"id": d.id, "modulo": d.modulo, "tipo": d.tipo, "nombre": d.nombre,
            "diario": d.diario_codigo, "leyenda": d.leyenda, "lineas": d.lineas or [],
            "vigenteDesde": d.vigente_desde.isoformat() if d.vigente_desde else None,
            "vigenteHasta": d.vigente_hasta.isoformat() if d.vigente_hasta else None,
            "activa": d.activa, "creadaPor": d.creada_por}


@router.get("/definiciones")
def listar_definiciones(modulo: str = "", db: Session = Depends(get_db)):
    q = select(models.DefinicionAsiento).order_by(models.DefinicionAsiento.modulo,
                                                  models.DefinicionAsiento.tipo)
    if modulo:
        q = q.where(models.DefinicionAsiento.modulo == modulo)
    items = [_serial_definicion(d) for d in db.scalars(q).all()]
    return {"items": items, "total": len(items)}


def _validar_definicion(db: Session, data: DefinicionIn) -> None:
    lados = {l.dc.upper() for l in data.lineas}
    if not {"DEBE", "HABER"} <= lados:
        raise HTTPException(422, "La definición necesita al menos una línea al DEBE y una al HABER.")
    for l in data.lineas:
        c = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == l.cuenta))
        if c is None:
            raise HTTPException(422, f"La cuenta {l.cuenta} no existe en el plan.")
        if not c.imputable:
            raise HTTPException(422, f"La cuenta {l.cuenta} es de agrupación: no recibe asientos.")
        try:
            motor.calcular(l.importe, {})          # la expresión tiene que ser válida
        except motor.ErrorContable as e:
            raise HTTPException(422, str(e))


@router.post("/definiciones", status_code=201, dependencies=[Depends(_configura)])
def crear_definicion(data: DefinicionIn, db: Session = Depends(get_db),
                     user: Usuario = Depends(usuario_actual)):
    """Al definir la regla se reprocesan las transacciones que la estaban esperando."""
    _validar_definicion(db, data)
    d = models.DefinicionAsiento(**{**data.model_dump(), "lineas": [l.model_dump() for l in data.lineas]},
                                 creada_por=user.username)
    db.add(d); db.commit(); db.refresh(d)
    resultado = motor.reprocesar_pendientes(db, modulo=d.modulo, tipo=d.tipo, usuario=user.username)
    return {**_serial_definicion(d), "reproceso": resultado}


@router.put("/definiciones/{definicion_id}", dependencies=[Depends(_configura)])
def editar_definicion(definicion_id: int, data: DefinicionIn, db: Session = Depends(get_db),
                      user: Usuario = Depends(usuario_actual)):
    d = db.get(models.DefinicionAsiento, definicion_id)
    if not d:
        raise HTTPException(404, "Definición no encontrada")
    _validar_definicion(db, data)
    for k, v in data.model_dump().items():
        setattr(d, k, [l.model_dump() for l in data.lineas] if k == "lineas" else v)
    db.commit(); db.refresh(d)
    resultado = motor.reprocesar_pendientes(db, modulo=d.modulo, tipo=d.tipo, usuario=user.username)
    return {**_serial_definicion(d), "reproceso": resultado}


class PruebaIn(BaseModel):
    datos: dict = Field(default_factory=dict)


@router.post("/definiciones/{definicion_id}/probar", dependencies=[Depends(_configura)])
def probar_definicion(definicion_id: int, data: PruebaIn, db: Session = Depends(get_db)):
    """Vista previa del asiento con datos de ejemplo, sin registrar nada."""
    d = db.get(models.DefinicionAsiento, definicion_id)
    if not d:
        raise HTTPException(404, "Definición no encontrada")
    try:
        lineas = motor.lineas_de(db, d, data.datos)
        debe, haber = motor.validar_partida_doble(lineas)
    except motor.ErrorContable as e:
        raise _error(e)
    return {"lineas": [{"cuenta": l["cuenta_codigo"], "nombre": l["cuenta_nombre"],
                        "debe": float(l["debe"]), "haber": float(l["haber"]),
                        "centro": l["centro_codigo"], "detalle": l["detalle"]} for l in lineas],
            "debe": float(debe), "haber": float(haber)}


# ── Transacciones ────────────────────────────────────────────────────────────────────────────────
def _serial_transaccion(t: models.Transaccion) -> dict:
    return {"id": t.id, "modulo": t.modulo, "tipo": t.tipo, "referencia": t.referencia,
            "fecha": t.fecha.isoformat(), "moneda": t.moneda, "descripcion": t.descripcion,
            "datos": t.datos or {}, "estado": t.estado, "motivo": t.motivo,
            "asientoId": t.asiento_id, "usuarioOrigen": t.usuario_origen,
            "recibidaEn": t.recibida_en.isoformat() if t.recibida_en else None}


@router.get("/transacciones")
def listar_transacciones(estado: str = "", modulo: str = "", tipo: str = "", texto: str = "",
                         desde: date | None = None, hasta: date | None = None,
                         limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                         db: Session = Depends(get_db)):
    q = select(models.Transaccion)
    if estado:
        q = q.where(models.Transaccion.estado.in_(estado.split(",")))
    if modulo:
        q = q.where(models.Transaccion.modulo == modulo)
    if tipo:
        q = q.where(models.Transaccion.tipo == tipo)
    if texto:
        q = q.where(models.Transaccion.referencia.ilike(f"%{texto}%"))
    if desde:
        q = q.where(models.Transaccion.fecha >= desde)
    if hasta:
        q = q.where(models.Transaccion.fecha <= hasta)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    filas = db.scalars(q.order_by(models.Transaccion.fecha.desc(), models.Transaccion.id.desc())
                        .limit(limit).offset(offset)).all()
    pendientes = db.scalar(select(func.count()).select_from(models.Transaccion)
                           .where(models.Transaccion.estado == "PENDIENTE_CONFIGURACION")) or 0
    con_error = db.scalar(select(func.count()).select_from(models.Transaccion)
                          .where(models.Transaccion.estado == "ERROR")) or 0
    return {"items": [_serial_transaccion(t) for t in filas], "total": total, "limit": limit,
            "offset": offset, "pendientes": pendientes, "errores": con_error}


@router.get("/transacciones/sin-definir")
def sin_definir(db: Session = Depends(get_db)):
    """Tipos de transacción que están esperando su definición, con cuántas hay y un ejemplo de datos."""
    filas = db.execute(
        select(models.Transaccion.modulo, models.Transaccion.tipo, func.count(), func.min(models.Transaccion.id))
        .where(models.Transaccion.estado == "PENDIENTE_CONFIGURACION")
        .group_by(models.Transaccion.modulo, models.Transaccion.tipo)).all()
    items = []
    for modulo, tipo, cantidad, primera_id in filas:
        ejemplo = db.get(models.Transaccion, primera_id)
        items.append({"modulo": modulo, "tipo": tipo, "cantidad": int(cantidad),
                      "campos": sorted((ejemplo.datos or {}).keys()) if ejemplo else [],
                      "ejemplo": _serial_transaccion(ejemplo) if ejemplo else None})
    return {"items": sorted(items, key=lambda x: (-x["cantidad"], x["modulo"], x["tipo"])),
            "total": len(items)}


@router.post("/transacciones/reprocesar", dependencies=[Depends(_escribe)])
def reprocesar(modulo: str = "", tipo: str = "", db: Session = Depends(get_db),
               user: Usuario = Depends(usuario_actual)):
    return motor.reprocesar_pendientes(db, modulo=modulo, tipo=tipo, usuario=user.username)


@router.get("/transacciones/{transaccion_id}")
def ver_transaccion(transaccion_id: int, db: Session = Depends(get_db)):
    t = db.get(models.Transaccion, transaccion_id)
    if not t:
        raise HTTPException(404, "Transacción no encontrada")
    asiento = db.get(models.Asiento, t.asiento_id) if t.asiento_id else None
    return {**_serial_transaccion(t), "asiento": libros.serial_asiento(asiento) if asiento else None}


# ── Asientos ─────────────────────────────────────────────────────────────────────────────────────
class LineaManualIn(BaseModel):
    cuenta: str
    debe: float = 0
    haber: float = 0
    centro: str = ""
    detalle: str = ""


class AsientoManualIn(BaseModel):
    fecha: date
    concepto: str = Field(min_length=1, max_length=200)
    diario_codigo: str = "VAR"
    lineas: list[LineaManualIn] = Field(min_length=2)
    borrador: bool = False           # se guarda sin publicar (todavía no entra en los libros)


@router.get("/asientos")
def listar_asientos(desde: date | None = None, hasta: date | None = None, diario: str = "",
                    solo_vigentes: bool = False, limit: int = Query(100, ge=1, le=500),
                    offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return libros.diario(db, desde=desde, hasta=hasta, diario_codigo=diario,
                         solo_vigentes=solo_vigentes, limit=limit, offset=offset)


@router.post("/asientos", status_code=201, dependencies=[Depends(_escribe)])
def crear_asiento_manual(data: AsientoManualIn, db: Session = Depends(get_db),
                         user: Usuario = Depends(usuario_actual)):
    """Asiento manual (ajustes). Los del circuito salen de las transacciones, no de acá."""
    lineas = []
    for i, l in enumerate(data.lineas, start=1):
        if (l.debe or 0) and (l.haber or 0):
            raise HTTPException(422, f"Línea {i}: una línea va al debe o al haber, no a los dos.")
        cuenta = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == l.cuenta))
        if cuenta is None or not cuenta.imputable or not cuenta.activa:
            raise HTTPException(422, f"Línea {i}: la cuenta {l.cuenta} no es imputable.")
        lineas.append({"cuenta_codigo": cuenta.codigo, "cuenta_nombre": cuenta.nombre,
                       "debe": Decimal(str(l.debe or 0)), "haber": Decimal(str(l.haber or 0)),
                       "centro_codigo": l.centro, "detalle": l.detalle})
    try:
        a = motor.registrar_asiento(db, fecha=data.fecha, concepto=data.concepto, lineas=lineas,
                                    diario=data.diario_codigo, origen="MANUAL", usuario=user.username)
        if data.borrador:
            a.estado = "BORRADOR"
        db.commit()
    except motor.ErrorContable as e:
        db.rollback()
        raise _error(e)
    return libros.serial_asiento(a)


@router.post("/asientos/{asiento_id}/publicar", dependencies=[Depends(_escribe)])
def publicar_asiento(asiento_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    """Publica un borrador: recién ahí entra en los libros."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    try:
        motor.publicar_borrador(db, a, user.username)
    except motor.ErrorContable as e:
        raise _error(e)
    return libros.serial_asiento(a)


@router.delete("/asientos/{asiento_id}", status_code=204, dependencies=[Depends(_escribe)])
def borrar_borrador(asiento_id: int, db: Session = Depends(get_db)):
    """Un borrador se puede borrar; uno registrado, no (se anula)."""
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    if a.estado != "BORRADOR":
        raise HTTPException(409, "Un asiento registrado no se borra: se anula con su contra-asiento.")
    db.delete(a); db.commit()


@router.get("/asientos/{asiento_id}")
def ver_asiento(asiento_id: int, db: Session = Depends(get_db)):
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    t = db.get(models.Transaccion, a.transaccion_id) if a.transaccion_id else None
    return {**libros.serial_asiento(a), "transaccion": _serial_transaccion(t) if t else None}


class MotivoIn(BaseModel):
    motivo: str = ""


@router.post("/asientos/{asiento_id}/anular", dependencies=[Depends(_escribe)])
def anular_asiento(asiento_id: int, data: MotivoIn, db: Session = Depends(get_db),
                   user: Usuario = Depends(usuario_actual)):
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    try:
        reversa = motor.anular(db, a, user.username, data.motivo)
    except motor.ErrorContable as e:
        raise _error(e)
    return {"anulado": libros.serial_asiento(a), "reversa": libros.serial_asiento(reversa)}


# ── Libros y estados ─────────────────────────────────────────────────────────────────────────────
@router.get("/libros/diario")
def libro_diario(desde: date | None = None, hasta: date | None = None, diario: str = "",
                 limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db)):
    return libros.diario(db, desde=desde, hasta=hasta, diario_codigo=diario, limit=limit, offset=offset)


@router.get("/libros/mayor/{cuenta_codigo}")
def libro_mayor(cuenta_codigo: str, desde: date | None = None, hasta: date | None = None,
                db: Session = Depends(get_db)):
    try:
        return libros.mayor(db, cuenta_codigo, desde=desde, hasta=hasta)
    except motor.ErrorContable as e:
        raise _error(e)


@router.get("/libros/sumas-y-saldos")
def sumas_y_saldos(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    return libros.sumas_y_saldos(db, desde=desde, hasta=hasta)


@router.get("/libros/estados")
def estados_contables(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    return libros.estados(db, desde=desde, hasta=hasta)


@router.get("/libros/iva/{libro}")
def libro_iva(libro: str, desde: date | None = None, hasta: date | None = None,
              db: Session = Depends(get_db)):
    if libro.upper() not in ("VENTAS", "COMPRAS"):
        raise HTTPException(422, "El libro IVA es VENTAS o COMPRAS.")
    return libros.libro_iva(db, libro, desde=desde, hasta=hasta)


@router.get("/libros/flujo-efectivo")
def flujo_efectivo(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    return libros.flujo_efectivo(db, desde=desde, hasta=hasta)


@router.get("/libros/iva/posicion/periodo")
def posicion_iva(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    """Débito contra crédito fiscal: cuánto hay que pagar (o queda a favor) en el período."""
    return libros.posicion_iva(db, desde=desde, hasta=hasta)


@router.get("/reportes/por-centro")
def por_centro(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    return libros.por_centro(db, desde=desde, hasta=hasta)


# ── Conciliación bancaria ────────────────────────────────────────────────────────────────────────
class ExtractoIn(BaseModel):
    cuenta_codigo: str
    fecha: date
    importe: float
    descripcion: str = ""
    referencia: str = ""


class ConciliarIn(BaseModel):
    extracto_id: int
    asiento_linea_id: int


@router.get("/conciliacion")
def ver_conciliacion(cuenta: str = "1.1.02", desde: date | None = None, hasta: date | None = None,
                     db: Session = Depends(get_db)):
    try:
        return conciliacion.estado(db, cuenta, desde=desde, hasta=hasta)
    except motor.ErrorContable as e:
        raise _error(e)


@router.post("/conciliacion/extracto", status_code=201, dependencies=[Depends(_escribe)])
def cargar_extracto(data: ExtractoIn, db: Session = Depends(get_db)):
    """Carga una línea del extracto del banco (+ entrada / − salida, como viene del banco)."""
    if not db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == data.cuenta_codigo)):
        raise HTTPException(422, f"La cuenta {data.cuenta_codigo} no existe.")
    if not data.importe:
        raise HTTPException(422, "El importe no puede ser cero.")
    e = models.LineaExtracto(cuenta_codigo=data.cuenta_codigo, fecha=data.fecha,
                             importe=Decimal(str(data.importe)), descripcion=data.descripcion[:200],
                             referencia=data.referencia[:80])
    db.add(e); db.commit(); db.refresh(e)
    return {"id": e.id, "fecha": e.fecha.isoformat(), "importe": float(e.importe),
            "descripcion": e.descripcion, "conciliada": False}


@router.delete("/conciliacion/extracto/{extracto_id}", status_code=204, dependencies=[Depends(_escribe)])
def borrar_extracto(extracto_id: int, db: Session = Depends(get_db)):
    e = db.get(models.LineaExtracto, extracto_id)
    if not e:
        raise HTTPException(404, "Línea del extracto no encontrada")
    db.delete(e); db.commit()


@router.post("/conciliacion/conciliar", dependencies=[Depends(_escribe)])
def conciliar(data: ConciliarIn, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    try:
        return conciliacion.conciliar(db, data.extracto_id, data.asiento_linea_id, user.username)
    except motor.ErrorContable as e:
        raise _error(e)


@router.post("/conciliacion/desconciliar/{extracto_id}", dependencies=[Depends(_escribe)])
def desconciliar(extracto_id: int, db: Session = Depends(get_db)):
    try:
        return conciliacion.desconciliar(db, extracto_id)
    except motor.ErrorContable as e:
        raise _error(e)


@router.post("/conciliacion/automatica", dependencies=[Depends(_escribe)])
def conciliar_automatica(cuenta: str = "1.1.02", db: Session = Depends(get_db),
                         user: Usuario = Depends(usuario_actual)):
    """Empareja lo pendiente por importe y fecha (misma fecha y, si no, hasta 5 días)."""
    try:
        return conciliacion.automatica(db, cuenta, user.username)
    except motor.ErrorContable as e:
        raise _error(e)


@router.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    """Lo que la pantalla principal necesita saber de un vistazo."""
    ejercicio = db.scalar(select(models.Ejercicio).where(models.Ejercicio.estado == "ABIERTO")
                          .order_by(models.Ejercicio.numero.desc()))
    cuenta = lambda w: db.scalar(select(func.count()).select_from(models.Transaccion).where(w)) or 0  # noqa: E731
    return {
        "ejercicio": _serial_ejercicio(ejercicio) if ejercicio else None,
        "pendientesConfiguracion": cuenta(models.Transaccion.estado == "PENDIENTE_CONFIGURACION"),
        "errores": cuenta(models.Transaccion.estado == "ERROR"),
        "contabilizadas": cuenta(models.Transaccion.estado == "CONTABILIZADA"),
        "asientos": db.scalar(select(func.count()).select_from(models.Asiento)) or 0,
        "definiciones": db.scalar(select(func.count()).select_from(models.DefinicionAsiento)) or 0,
        "cuentas": db.scalar(select(func.count()).select_from(models.Cuenta)) or 0,
    }
