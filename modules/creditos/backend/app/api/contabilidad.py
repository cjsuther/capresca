"""Módulo Contabilidad: libro diario (asientos generados automáticamente)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.deps import get_current_user
from app.reports.pdf import libro_diario_pdf, iva_periodo_pdf, balance_sumas_saldos_pdf
from app.services import contabilidad as svc
from app import models, schemas

router = APIRouter(prefix="/api/creditos/contabilidad", tags=["contabilidad"],
                   dependencies=[Depends(get_current_user)])


# ---------------- Plan de cuentas (ABM editable, seed = plantilla base) ----------------
def _cuenta_out(db: Session, c: models.CuentaContable) -> dict:
    en_uso = db.scalar(select(models.AsientoLinea.id)
                       .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
                       .where(models.AsientoLinea.cuenta_codigo == c.codigo,
                              models.Asiento.empresa_id == c.empresa_id).limit(1)) is not None
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "tipo": c.tipo,
            "descripcion": c.descripcion or "", "alias": c.alias or "", "moneda": c.moneda or "ARS",
            "clasificacion": c.clasificacion or "Sin clasificar", "saldo_normal": c.saldo_normal or "deudor",
            "imputable": bool(c.imputable), "manual": bool(c.manual), "entidades": c.entidades or [],
            "en_uso": en_uso, "base": c.codigo in svc._NOMBRE}


def _aplica_campos(c: models.CuentaContable, data: schemas.CuentaContableIn) -> None:
    """Copia los 'datos de la cuenta' del payload al modelo (sin código/nombre/tipo, que van aparte)."""
    c.descripcion = (data.descripcion or "")[:2000]
    c.alias = (data.alias or "")[:40]
    c.moneda = (data.moneda or "ARS")[:3]
    c.clasificacion = (data.clasificacion or "Sin clasificar")[:30]
    c.saldo_normal = "acreedor" if (data.saldo_normal or "").lower().startswith("a") else "deudor"
    c.imputable = bool(data.imputable)
    c.manual = bool(data.manual)
    c.entidades = [{"tipo": (e.tipo or "")[:40], "entidad": (e.entidad or "")[:120]}
                   for e in data.entidades if (e.tipo or e.entidad)]


@router.get("/plan-cuentas", response_model=list[schemas.CuentaContableOut])
def plan_cuentas(q: str | None = None, empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Plan de cuentas (VFP: agjscontable) de la empresa (o la predeterminada). Editable desde la ABM."""
    emp = svc._emp(db, empresa_id)
    qy = select(models.CuentaContable).where(models.CuentaContable.empresa_id == emp)
    if q:
        like = f"%{q.lower()}%"
        qy = qy.where(models.CuentaContable.codigo.ilike(like) | models.CuentaContable.nombre.ilike(like))
    cuentas = db.scalars(qy.order_by(models.CuentaContable.codigo)).all()
    return [_cuenta_out(db, c) for c in cuentas]


def _valida_tipo(tipo: str) -> str:
    t = (tipo or "").strip().lower()
    if t not in svc.TIPOS_CUENTA:
        raise HTTPException(422, f"Tipo inválido. Usá: {', '.join(svc.TIPOS_CUENTA)}.")
    return t


@router.post("/plan-cuentas", response_model=schemas.CuentaContableOut, status_code=201)
def crear_cuenta(data: schemas.CuentaContableIn, empresa_id: int | None = None, db: Session = Depends(get_db)):
    emp = svc._emp(db, empresa_id)
    tipo = _valida_tipo(data.tipo)
    if db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == data.codigo,
                                                     models.CuentaContable.empresa_id == emp)):
        raise HTTPException(409, "Ya existe una cuenta con ese código")
    c = models.CuentaContable(empresa_id=emp, codigo=data.codigo, nombre=data.nombre, tipo=tipo)
    _aplica_campos(c, data)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Ya existe una cuenta con ese código")
    db.refresh(c)
    return _cuenta_out(db, c)


@router.put("/plan-cuentas/{cuenta_id}", response_model=schemas.CuentaContableOut)
def editar_cuenta(cuenta_id: int, data: schemas.CuentaContableIn, db: Session = Depends(get_db)):
    c = db.get(models.CuentaContable, cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    tipo = _valida_tipo(data.tipo)
    # el código de una cuenta base (usada por el motor de asientos) no se puede cambiar
    if data.codigo != c.codigo:
        if c.codigo in svc._NOMBRE:
            raise HTTPException(422, "No se puede cambiar el código de una cuenta base del sistema.")
        if db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == data.codigo,
                                                         models.CuentaContable.empresa_id == c.empresa_id,
                                                         models.CuentaContable.id != cuenta_id)):
            raise HTTPException(409, "Ya existe una cuenta con ese código")
    c.codigo, c.nombre, c.tipo = data.codigo, data.nombre, tipo
    _aplica_campos(c, data)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Ya existe una cuenta con ese código")
    db.refresh(c)
    return _cuenta_out(db, c)


@router.delete("/plan-cuentas/{cuenta_id}", status_code=204)
def borrar_cuenta(cuenta_id: int, db: Session = Depends(get_db)):
    c = db.get(models.CuentaContable, cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    if c.codigo in svc._NOMBRE:
        raise HTTPException(422, "Es una cuenta base del sistema; no se puede borrar.")
    if db.scalar(select(models.AsientoLinea.id)
                 .join(models.Asiento, models.Asiento.id == models.AsientoLinea.asiento_id)
                 .where(models.AsientoLinea.cuenta_codigo == c.codigo,
                        models.Asiento.empresa_id == c.empresa_id).limit(1)):
        raise HTTPException(422, "La cuenta tiene asientos que la referencian; no se puede borrar.")
    db.delete(c); db.commit()
    return Response(status_code=204)


@router.post("/plan-cuentas/restaurar-plantilla")
def restaurar_plantilla(empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Agrega las cuentas de la plantilla base que falten (no pisa ni duplica) en la empresa."""
    return {"agregadas": svc.restaurar_plan_cuentas(db, empresa_id)}


@router.post("/plan-cuentas/cargar-estandar")
def cargar_estandar(empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Puebla el plan de la empresa con un chart estándar (ejemplo argentino), idempotente."""
    return {"agregadas": svc.cargar_plan_estandar(db, empresa_id)}


# ---------------- Empresas (entes contables) ----------------
class EmpresaIn(BaseModel):
    codigo: str
    nombre: str
    cuit: str = ""
    predeterminada: bool = False


@router.get("/empresas")
def empresas(db: Session = Depends(get_db)):
    """Empresas / entes contables. Cada una tiene su plan de cuentas y sus libros (H-188)."""
    return [{"id": e.id, "codigo": e.codigo, "nombre": e.nombre, "cuit": e.cuit,
             "predeterminada": e.predeterminada, "activa": e.activa} for e in svc.listar_empresas(db)]


@router.post("/empresas", status_code=201)
def crear_empresa(data: EmpresaIn, db: Session = Depends(get_db)):
    e = _regla(svc.crear_empresa, db, data.codigo, data.nombre, data.cuit, data.predeterminada)
    return {"id": e.id, "codigo": e.codigo, "nombre": e.nombre, "predeterminada": e.predeterminada}


@router.post("/empresas/{empresa_id}/predeterminada")
def predeterminar_empresa(empresa_id: int, db: Session = Depends(get_db)):
    e = _regla(svc.set_empresa_predeterminada, db, empresa_id)
    return {"id": e.id, "predeterminada": e.predeterminada}


# ---------------- Parametrización contable (evento → cuenta) ----------------
@router.get("/imputaciones")
def imputaciones(db: Session = Depends(get_db)):
    """Mapa evento de operación → cuenta del plan (editable). Incluye el nombre de la cuenta actual."""
    svc.seed_imputaciones(db)
    ctas = {c.codigo: c.nombre for c in db.scalars(select(models.CuentaContable)).all()}
    ims = db.scalars(select(models.ImputacionContable).order_by(models.ImputacionContable.id)).all()
    return [{"id": i.id, "clave": i.clave, "grupo": i.grupo, "descripcion": i.descripcion,
             "cuenta_codigo": i.cuenta_codigo, "cuenta_nombre": ctas.get(i.cuenta_codigo, "(sin cuenta)")}
            for i in ims]


@router.put("/imputaciones/{imp_id}")
def editar_imputacion(imp_id: int, data: schemas.ImputacionIn, db: Session = Depends(get_db)):
    i = db.get(models.ImputacionContable, imp_id)
    if not i:
        raise HTTPException(404, "Imputación no encontrada")
    cta = db.scalar(select(models.CuentaContable).where(models.CuentaContable.codigo == data.cuenta_codigo))
    if not cta:
        raise HTTPException(422, "La cuenta no existe en el plan.")
    if not cta.imputable:
        raise HTTPException(422, f"La cuenta {cta.codigo} ({cta.nombre}) es de agrupación (no imputable).")
    i.cuenta_codigo = data.cuenta_codigo
    db.commit()
    return {"id": i.id, "clave": i.clave, "cuenta_codigo": i.cuenta_codigo, "cuenta_nombre": cta.nombre}


# ---------------- Reportes contables (sumas y saldos + estados) ----------------
@router.get("/sumas-y-saldos")
def sumas_y_saldos(desde: date | None = None, hasta: date | None = None, empresa_id: int | None = None,
                   db: Session = Depends(get_db)):
    """Balance de comprobación de sumas y saldos por cuenta (opcional: rango de fechas / empresa)."""
    return svc.sumas_y_saldos(db, desde, hasta, empresa_id)


@router.get("/estados-contables")
def estados_contables(desde: date | None = None, hasta: date | None = None, empresa_id: int | None = None,
                      db: Session = Depends(get_db)):
    """Situación patrimonial + Estado de resultados armados desde los saldos por rubro."""
    return svc.estados_contables(db, desde, hasta, empresa_id)


@router.get("/flujo-efectivo")
def flujo_efectivo(desde: date | None = None, hasta: date | None = None, empresa_id: int | None = None,
                   db: Session = Depends(get_db)):
    """Flujo de efectivo (método directo): saldo inicial + entradas/salidas por contrapartida + saldo final."""
    return svc.flujo_efectivo(db, desde, hasta, empresa_id)


# ---------------- Conciliación bancaria ----------------
class ExtractoLineaIn(BaseModel):
    cuenta_codigo: str
    fecha: date
    descripcion: str = ""
    referencia: str = ""
    importe: float


class ConciliarIn(BaseModel):
    extracto_id: int
    asiento_linea_id: int


def _regla(fn, *a):
    try:
        return fn(*a)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))


@router.get("/conciliacion")
def conciliacion(cuenta: str = "1.1.02", desde: date | None = None, hasta: date | None = None,
                 empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Estado de conciliación bancaria: extracto vs mayor de la cuenta banco, saldos y diferencia."""
    return svc.conciliacion_bancaria(db, cuenta, desde, hasta, empresa_id)


@router.post("/conciliacion/extracto", status_code=201)
def crear_extracto(data: ExtractoLineaIn, empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Carga una línea del extracto bancario (importe con signo: + ingreso / − egreso)."""
    from decimal import Decimal
    e = _regla(svc.crear_extracto_linea, db, data.cuenta_codigo, data.fecha, data.descripcion,
               Decimal(str(data.importe)), data.referencia, empresa_id)
    return {"id": e.id}


@router.delete("/conciliacion/extracto/{extracto_id}", status_code=204)
def borrar_extracto(extracto_id: int, db: Session = Depends(get_db)):
    _regla(svc.eliminar_extracto_linea, db, extracto_id)


@router.post("/conciliacion/conciliar")
def conciliar(data: ConciliarIn, db: Session = Depends(get_db)):
    """Concilia una línea del extracto con un movimiento del mayor (mismo importe con signo)."""
    e = _regla(svc.conciliar, db, data.extracto_id, data.asiento_linea_id)
    return {"id": e.id, "conciliada": e.conciliada}


@router.post("/conciliacion/desconciliar/{extracto_id}")
def desconciliar(extracto_id: int, db: Session = Depends(get_db)):
    e = _regla(svc.desconciliar, db, extracto_id)
    return {"id": e.id, "conciliada": e.conciliada}


@router.post("/conciliacion/automatica")
def conciliar_automatica(cuenta: str = "1.1.02", empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Concilia automáticamente los pares extracto↔mayor del mismo importe (con signo) sin conciliar."""
    return svc.conciliar_automatico(db, cuenta, empresa_id)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(contenido: bytes, nombre: str) -> Response:
    return Response(content=contenido, media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/sumas-y-saldos/excel")
def sumas_y_saldos_excel(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    from app.reports.excel import sumas_y_saldos_excel as _gen
    return _xlsx(_gen(svc.sumas_y_saldos(db, desde, hasta)), "sumas_y_saldos.xlsx")


@router.get("/estados-contables/excel")
def estados_contables_excel(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    from app.reports.excel import estados_contables_excel as _gen
    return _xlsx(_gen(svc.estados_contables(db, desde, hasta)), "estados_contables.xlsx")


@router.get("/libro-diario/excel")
def libro_diario_excel(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    from app.reports.excel import libro_diario_excel as _gen
    qy = select(models.Asiento).options(selectinload(models.Asiento.lineas))
    if desde:
        qy = qy.where(models.Asiento.fecha >= desde)
    if hasta:
        qy = qy.where(models.Asiento.fecha <= hasta)
    asientos = db.scalars(qy.order_by(models.Asiento.fecha, models.Asiento.id)).all()
    return _xlsx(_gen(asientos), "libro_diario.xlsx")


# ---------------- Ejercicios contables (períodos) ----------------
def _ejercicio_out(e: models.EjercicioContable) -> dict:
    return {"id": e.id, "nombre": e.nombre, "fecha_desde": str(e.fecha_desde), "fecha_hasta": str(e.fecha_hasta),
            "estado": e.estado, "resultado": float(e.resultado or 0),
            "asiento_cierre_id": e.asiento_cierre_id, "asiento_apertura_id": e.asiento_apertura_id}


@router.get("/ejercicios")
def ejercicios(empresa_id: int | None = None, db: Session = Depends(get_db)):
    emp = svc._emp(db, empresa_id)
    es = db.scalars(select(models.EjercicioContable).where(models.EjercicioContable.empresa_id == emp)
                    .order_by(models.EjercicioContable.fecha_desde.desc())).all()
    return [_ejercicio_out(e) for e in es]


@router.post("/ejercicios", status_code=201)
def crear_ejercicio(data: schemas.EjercicioIn, empresa_id: int | None = None, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    try:
        e = svc.crear_ejercicio(db, nombre=data.nombre, fecha_desde=data.fecha_desde, fecha_hasta=data.fecha_hasta, empresa_id=empresa_id)
    except svc.ReglaNegocioError as ex:
        raise HTTPException(422, str(ex))
    return _ejercicio_out(e)


@router.post("/ejercicios/{ejercicio_id}/cerrar")
def cerrar_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    try:
        e = svc.cerrar_ejercicio(db, ejercicio_id, usuario=user.username)
    except svc.ReglaNegocioError as ex:
        raise HTTPException(422, str(ex))
    return _ejercicio_out(e)


@router.post("/ejercicios/{ejercicio_id}/reabrir")
def reabrir_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    try:
        e = svc.reabrir_ejercicio(db, ejercicio_id)
    except svc.ReglaNegocioError as ex:
        raise HTTPException(422, str(ex))
    return _ejercicio_out(e)


@router.post("/ejercicios/{ejercicio_id}/apertura")
def apertura_ejercicio(ejercicio_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    try:
        a = svc.generar_apertura(db, ejercicio_id, usuario=user.username)
    except svc.ReglaNegocioError as ex:
        raise HTTPException(422, str(ex))
    return {"asiento_id": a.id, "numero": a.numero}


# ---------------- Centros de costo (analítica) ----------------
@router.get("/centros-costo")
def centros_costo(db: Session = Depends(get_db)):
    svc.seed_centros(db)
    cs = db.scalars(select(models.CentroCosto).order_by(models.CentroCosto.codigo)).all()
    return [{"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo} for c in cs]


@router.post("/centros-costo", status_code=201)
def crear_centro(data: schemas.CentroCostoIn, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    if db.scalar(select(models.CentroCosto).where(models.CentroCosto.codigo == data.codigo.upper())):
        raise HTTPException(409, "Ya existe un centro con ese código")
    c = models.CentroCosto(codigo=data.codigo.upper()[:12], nombre=data.nombre.strip()[:60], activo=data.activo)
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo}


@router.put("/centros-costo/{centro_id}")
def editar_centro(centro_id: int, data: schemas.CentroCostoIn, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    c = db.get(models.CentroCosto, centro_id)
    if not c:
        raise HTTPException(404, "Centro no encontrado")
    c.nombre = data.nombre.strip()[:60]; c.activo = data.activo
    db.commit()
    return {"id": c.id, "codigo": c.codigo, "nombre": c.nombre, "activo": c.activo}


@router.get("/por-centro")
def por_centro(desde: date | None = None, hasta: date | None = None, empresa_id: int | None = None,
               db: Session = Depends(get_db)):
    return svc.analisis_por_centro(db, desde, hasta, empresa_id)


# ---------------- Diarios contables (Odoo: journals) ----------------
@router.get("/diarios")
def diarios(db: Session = Depends(get_db)):
    svc.seed_diarios(db)
    ds = db.scalars(select(models.DiarioContable).where(models.DiarioContable.activo.is_(True))
                    .order_by(models.DiarioContable.codigo)).all()
    return [{"codigo": d.codigo, "nombre": d.nombre, "tipo": d.tipo} for d in ds]


# ---------------- Asientos manuales (contabilidad general) ----------------
@router.get("/asientos-manuales", response_model=list[schemas.AsientoOut])
def asientos_manuales(empresa_id: int | None = None, db: Session = Depends(get_db)):
    """Asientos cargados a mano (borradores + publicados) y sus reversas. Los automáticos van al diario."""
    emp = svc._emp(db, empresa_id)
    qy = (select(models.Asiento).options(selectinload(models.Asiento.lineas))
          .where(models.Asiento.origen.in_(("manual", "reversa")), models.Asiento.empresa_id == emp)
          .order_by(models.Asiento.fecha.desc(), models.Asiento.id.desc()))
    return db.scalars(qy).all()


@router.post("/asientos-manuales", response_model=schemas.AsientoOut, status_code=201)
def crear_asiento_manual(data: schemas.AsientoManualIn, empresa_id: int | None = None, db: Session = Depends(get_db),
                         user: models.Usuario = Depends(get_current_user)):
    try:
        a = svc.crear_asiento_manual(db, fecha=data.fecha, concepto=data.concepto, diario_codigo=data.diario_codigo,
                                     lineas=[l.model_dump() for l in data.lineas], usuario=user.username,
                                     empresa_id=empresa_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_asiento(a.id, db)


@router.put("/asientos-manuales/{asiento_id}", response_model=schemas.AsientoOut)
def editar_asiento_manual(asiento_id: int, data: schemas.AsientoManualIn, db: Session = Depends(get_db),
                          _u: models.Usuario = Depends(get_current_user)):
    try:
        a = svc.editar_asiento_borrador(db, asiento_id, fecha=data.fecha, concepto=data.concepto,
                                        diario_codigo=data.diario_codigo, lineas=[l.model_dump() for l in data.lineas])
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_asiento(a.id, db)


@router.post("/asientos-manuales/{asiento_id}/publicar", response_model=schemas.AsientoOut)
def publicar_asiento(asiento_id: int, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    try:
        a = svc.publicar_asiento(db, asiento_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_asiento(a.id, db)


@router.delete("/asientos-manuales/{asiento_id}", status_code=204)
def eliminar_asiento_manual(asiento_id: int, db: Session = Depends(get_db), _u: models.Usuario = Depends(get_current_user)):
    try:
        svc.eliminar_asiento_borrador(db, asiento_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return Response(status_code=204)


@router.post("/asientos-manuales/{asiento_id}/reversar", response_model=schemas.AsientoOut)
def reversar_asiento(asiento_id: int, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    try:
        rev = svc.reversar_asiento(db, asiento_id, usuario=user.username)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_asiento(rev.id, db)


@router.get("/libro-diario", response_model=list[schemas.AsientoOut])
def libro_diario(
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
):
    qy = select(models.Asiento).options(selectinload(models.Asiento.lineas))
    if desde:
        qy = qy.where(models.Asiento.fecha >= desde)
    if hasta:
        qy = qy.where(models.Asiento.fecha <= hasta)
    return db.scalars(qy.order_by(models.Asiento.fecha, models.Asiento.id)).all()


@router.get("/balance")
def balance_sumas_saldos(desde: date | None = None, hasta: date | None = None,
                         db: Session = Depends(get_db)):
    """Balance de sumas y saldos del período (VFP: balance de comprobación)."""
    return svc.balance_sumas_saldos(db, desde, hasta)


@router.get("/iva-cuotas")
def iva_cuotas_cobradas(desde: date | None = None, hasta: date | None = None,
                        db: Session = Depends(get_db)):
    """IVA débito de cuotas de crédito cobradas por período, sobre dato real
    (`maecuotas`). VFP: cb-cjcreditoscobrados (61005/60505)."""
    return svc.iva_cuotas_cobradas(db, desde=desde, hasta=hasta)


@router.get("/ctacte-credito")
def ctacte_contable_credito(no_credito: int, db: Session = Depends(get_db)):
    """Cta. cte. contable de un crédito (crctacte.dbf): desglose contable + totales."""
    return svc.ctacte_contable_credito(db, no_credito)


@router.get("/general")
def contabilidad_general(desde: date | None = None, hasta: date | None = None,
                         tipo: str | None = None, limit: int = Query(100, le=500),
                         offset: int = 0, db: Session = Depends(get_db)):
    """Contabilidad general de caja/juegos (contgral.dbf): asientos + totales por moneda."""
    return svc.contabilidad_general(db, desde=desde, hasta=hasta, tipo=tipo,
                                    limit=limit, offset=offset)


@router.get("/mayor/balance")
def balance_mayor(desde: date | None = None, hasta: date | None = None,
                  periodo: str | None = None, db: Session = Depends(get_db)):
    """Balance de sumas y saldos sobre el LIBRO MAYOR REAL (asientos migrados, 2M)."""
    return svc.balance_mayor(db, desde=desde, hasta=hasta, periodo=periodo)


@router.get("/mayor/cuenta")
def mayor_cuenta(cuenta: str = Query(...), desde: date | None = None,
                 hasta: date | None = None,
                 limit: int = Query(default=200, le=500), offset: int = 0,
                 db: Session = Depends(get_db)):
    """Movimientos (mayor) de una cuenta contable sobre el dato real."""
    return svc.mayor_cuenta(db, cuenta=cuenta, desde=desde, hasta=hasta,
                            limit=limit, offset=offset)


@router.get("/balance/pdf")
def balance_pdf_endpoint(desde: date | None = None, hasta: date | None = None,
                         db: Session = Depends(get_db)):
    pdf = balance_sumas_saldos_pdf(svc.balance_sumas_saldos(db, desde, hasta))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="balance_sumas_saldos.pdf"'})


@router.get("/libro-diario/pdf")
def libro_diario_pdf_endpoint(
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
):
    qy = select(models.Asiento).options(selectinload(models.Asiento.lineas))
    if desde:
        qy = qy.where(models.Asiento.fecha >= desde)
    if hasta:
        qy = qy.where(models.Asiento.fecha <= hasta)
    asientos = db.scalars(qy.order_by(models.Asiento.fecha, models.Asiento.id)).all()
    pdf = libro_diario_pdf(asientos)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="libro_diario.pdf"'})


@router.get("/iva-periodo", response_model=schemas.IvaPeriodo)
def iva_periodo(desde: date, hasta: date, db: Session = Depends(get_db)):
    return svc.iva_periodo(db, desde, hasta)


@router.get("/iva-periodo/pdf")
def iva_periodo_pdf_endpoint(desde: date, hasta: date, db: Session = Depends(get_db)):
    data = svc.iva_periodo(db, desde, hasta)
    pdf = iva_periodo_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="iva_{desde}_{hasta}.pdf"'})


@router.get("/op-devengadas", response_model=schemas.OpDevengadas)
def op_devengadas(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Órdenes de pago devengadas por período, agrupadas por tipo."""
    return svc.op_devengadas(db, desde, hasta)


@router.get("/iva-egresos")
def iva_egresos(desde: date, hasta: date, db: Session = Depends(get_db)):
    """IVA de egresos de créditos por período (cb-egivaegresos)."""
    return svc.iva_egresos(db, desde, hasta)


@router.get("/iva-gsoq")
def iva_gsoq(desde: date, hasta: date, db: Session = Depends(get_db)):
    """IVA de gastos de originación y quebranto por período (cb-iva-gsoq-periodo)."""
    return svc.iva_gsoq_periodo(db, desde, hasta)


@router.get("/solicitudes-baja", response_model=list[schemas.SolicitudBaja])
def solicitudes_baja(db: Session = Depends(get_db)):
    """Solicitudes dadas de baja / rechazadas, para revisión."""
    return svc.solicitudes_baja(db)


@router.get("/asientos/{asiento_id}", response_model=schemas.AsientoOut)
def obtener_asiento(asiento_id: int, db: Session = Depends(get_db)):
    a = db.get(models.Asiento, asiento_id)
    if not a:
        raise HTTPException(404, "Asiento no encontrado")
    return a
