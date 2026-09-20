"""Módulo Créditos: líneas y simulación de plan de cuotas.

El endpoint de simulación es la vitrina del motor de cálculo portado del VFP
(equivale a F11 - SIMULACION CREDITO del sistema original).
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import con_idempotencia
from app.deps import Actor, get_actor, get_current_user, requiere_perfil
from app.services import auditoria as audit
from app.domain import carteras
from app.domain.cuotas import ParametrosLinea, generar_plan
from app.domain.margen import margen_disponible
from app.services import creditos as svc
from app import models, schemas

router = APIRouter(prefix="/api/creditos/creditos", tags=["creditos"],
                   dependencies=[Depends(get_current_user)])


@router.get("/lineas", response_model=list[schemas.LineaOut])
def listar_lineas(incluir_inactivas: bool = Query(default=False),
                  db: Session = Depends(get_db)):
    """Líneas de crédito. Por defecto sólo activas; el ABM (30510) pide todas.
    El alta/edición vive en `/api/creditos/admin/lineas` (POST/PUT)."""
    q = db.query(models.LineaCredito)
    if not incluir_inactivas:
        q = q.filter_by(activa=True)
    return q.order_by(models.LineaCredito.nombre).all()


@router.post("/simular", response_model=schemas.SimulacionOut)
def simular(req: schemas.SimulacionRequest, db: Session = Depends(get_db)):
    linea = db.get(models.LineaCredito, req.linea_id)
    if not linea or not linea.activa:
        raise HTTPException(404, "Línea de crédito no encontrada o inactiva")

    advertencias: list[str] = []
    if linea.monto_max and req.capital > linea.monto_max:
        advertencias.append(
            f"El monto supera el máximo de la línea ({linea.monto_max}).")
    if req.plazo > linea.plazo_max:
        advertencias.append(
            f"El plazo supera el máximo de la línea ({linea.plazo_max} cuotas).")

    params = ParametrosLinea(
        tipo_calculo=linea.tipo_calculo,
        tna=linea.tna,
        iva=linea.iva,
        seguro_pct=linea.seguro_pct,
        gastos_adm_pct=linea.gastos_adm_pct,
        por_afecta=linea.por_afecta,
        cartera=linea.cartera,
    )
    try:
        plan = generar_plan(
            capital=req.capital,
            plazo=req.plazo,
            linea=params,
            fecha_primer_vto=req.fecha_primer_vencimiento,
            cuota_fija=req.cuota_fija,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))

    margen_val = None
    puede = None
    if req.sueldo is not None and carteras.afecta_margen(linea.cartera):
        r = margen_disponible(req.sueldo, linea.por_afecta, req.total_afectado)
        margen_val = r.margen_disponible
        puede = r.puede_tomar_credito
        cuota_prom = plan.cuota_promedio
        if puede and cuota_prom > r.margen_disponible:
            advertencias.append(
                "La cuota promedio supera el margen de afectación disponible.")
            puede = False
    elif not carteras.afecta_margen(linea.cartera):
        advertencias.append(
            f"Cartera '{carteras.CARTERA_NOMBRE.get(linea.cartera, linea.cartera)}' "
            "no consume margen de afectación.")

    return schemas.SimulacionOut(
        linea=linea.nombre,
        tipo_calculo=linea.tipo_calculo,
        capital=req.capital,
        cantidad_cuotas=len(plan.cuotas),
        total_a_pagar=plan.total_a_pagar,
        total_interes=plan.total_interes,
        cuota_promedio=plan.cuota_promedio,
        margen_disponible=margen_val,
        puede_tomar_credito=puede,
        advertencias=advertencias,
        cuotas=[schemas.CuotaOut(**c.as_dict()) for c in plan.cuotas],
    )


# ---------------------- Solicitudes ----------------------
def _detalle_solicitud(db: Session, s: models.Solicitud) -> schemas.SolicitudDetalle:
    cliente = db.get(models.Cliente, s.cliente_id)
    linea = db.get(models.LineaCredito, s.linea_id)
    ev = svc.evaluar_solicitud(db, s)
    credito = db.scalar(select(models.Credito).where(models.Credito.solicitud_id == s.id))
    return schemas.SolicitudDetalle(
        **schemas.SolicitudOut.model_validate(s).model_dump(),
        cliente_nombre=cliente.apellido_nombre if cliente else "",
        linea_nombre=linea.nombre if linea else "",
        margen_disponible=ev["margen"],
        puede_otorgarse=ev["puede"] and s.estado == "I",
        advertencias=ev["advertencias"],
        credito_id=credito.id if credito else None,
    )


@router.get("/solicitudes", response_model=list[schemas.SolicitudOut])
def listar_solicitudes(
    estado: str | None = Query(None, description="Filtra por estado (I,A,O,B)"),
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
):
    qy = select(models.Solicitud)
    if estado:
        qy = qy.where(models.Solicitud.estado == estado)
    if cliente_id:
        qy = qy.where(models.Solicitud.cliente_id == cliente_id)
    return db.scalars(qy.order_by(models.Solicitud.id.desc())).all()


@router.get("/solicitudes/{sid}", response_model=schemas.SolicitudDetalle)
def obtener_solicitud(sid: int, db: Session = Depends(get_db)):
    s = db.get(models.Solicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    return _detalle_solicitud(db, s)


@router.post("/solicitudes", response_model=schemas.SolicitudDetalle, status_code=201)
def crear_solicitud(data: schemas.SolicitudCreate, db: Session = Depends(get_db),
                    actor: Actor = Depends(get_actor),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
  def _do():   # idempotente: un reintento/doble-click no duplica la solicitud (H-108)
    if not db.get(models.Cliente, data.cliente_id):
        audit.registrar_cambio(db, usuario=actor.usuario, perfil=actor.perfil, ip=actor.ip,
                               entidad="Solicitud", operacion="ALTA", resultado="ERROR",
                               despues=data.model_dump(), detalle="Cliente inexistente")
        raise HTTPException(404, "Cliente inexistente")
    linea = db.get(models.LineaCredito, data.linea_id)
    if not linea or not linea.activa:
        audit.registrar_cambio(db, usuario=actor.usuario, perfil=actor.perfil, ip=actor.ip,
                               entidad="Solicitud", operacion="ALTA", resultado="ERROR",
                               despues=data.model_dump(), detalle="Línea inexistente o inactiva")
        raise HTTPException(404, "Línea inexistente o inactiva")

    s = models.Solicitud(
        cliente_id=data.cliente_id,
        linea_id=data.linea_id,
        estado="I",
        fecha_solicitud=data.fecha_primer_vencimiento,
        monto_solicitado=data.monto_solicitado,
        cantidad_cuotas=data.cantidad_cuotas,
        tna=linea.tna,
        cuota_fija=data.cuota_fija or Decimal("0"),
        garante1_cuil=data.garante1_cuil,
        garante2_cuil=data.garante2_cuil,
        garante3_cuil=data.garante3_cuil,
        garante4_cuil=data.garante4_cuil,
        gastos_originacion=data.gastos_originacion,
        iva_gastos_originacion=data.iva_gastos_originacion,
        quebranto=data.quebranto,
        iva_quebranto=data.iva_quebranto,
        cft=data.cft,
        credito_previo_pago=data.credito_previo_pago,
        importe_previo_pago=data.importe_previo_pago,
        observaciones=data.observaciones,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    audit.registrar_cambio(db, usuario=actor.usuario, perfil=actor.perfil, ip=actor.ip,
                           entidad="Solicitud", entidad_id=s.id, operacion="ALTA", resultado="OK",
                           despues={"cliente_id": s.cliente_id, "linea_id": s.linea_id,
                                    "monto_solicitado": s.monto_solicitado,
                                    "cantidad_cuotas": s.cantidad_cuotas, "estado": s.estado},
                           detalle=f"Alta de solicitud #{s.id}")
    return jsonable_encoder(_detalle_solicitud(db, s))
  return con_idempotencia(db, idempotency_key, "POST /api/creditos/solicitudes", _do)


@router.post("/solicitudes/{sid}/otorgar", response_model=schemas.CreditoDetalle)
def otorgar_solicitud(
    sid: int,
    forzar: bool = Query(False, description="Otorgar pese a advertencias de margen"),
    db: Session = Depends(get_db),
    _user: models.Usuario = Depends(requiere_perfil("CR")),  # perfil Créditos o ADMG
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
  def _do():   # idempotente: un reintento/doble-click no otorga dos créditos de la misma solicitud (H-108)
    s = db.get(models.Solicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    try:
        credito = svc.otorgar(db, s, forzar=forzar)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
    return jsonable_encoder(_credito_detalle(db, credito))
  return con_idempotencia(db, idempotency_key, "POST /api/creditos/solicitudes/otorgar", _do, usuario=_user.username)


# ---------------------- Créditos ----------------------
def _credito_detalle(db: Session, cr: models.Credito) -> schemas.CreditoDetalle:
    cliente = db.get(models.Cliente, cr.cliente_id)
    cuotas = db.scalars(
        select(models.Cuota).where(models.Cuota.credito_id == cr.id)
        .order_by(models.Cuota.numero)
    ).all()
    return schemas.CreditoDetalle(
        **schemas.CreditoOut.model_validate(cr).model_dump(),
        cliente_nombre=cliente.apellido_nombre if cliente else "",
        cantidad_cuotas=len(cuotas),
        total_a_pagar=sum((c.total for c in cuotas), Decimal("0")),
        cuotas=[schemas.CuotaCreditoOut.model_validate(c) for c in cuotas],
    )


@router.get("/{credito_id}/cancelacion", response_model=schemas.CancelacionDetalle)
def simular_cancelacion(credito_id: int,
                        fecha: date = Query(default_factory=date.today),
                        db: Session = Depends(get_db)):
    """Detalle del pago para cancelar anticipadamente un crédito (32045). No cobra."""
    from app.services import caja as caja_svc
    try:
        return caja_svc.simular_cancelacion(db, credito_id, fecha)
    except caja_svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/{credito_id}/cancelar", response_model=schemas.ReciboDetalle, status_code=201)
def cancelar_credito(credito_id: int, req: schemas.CancelacionRequest,
                     db: Session = Depends(get_db),
                     user: models.Usuario = Depends(requiere_perfil("CR", "CJ", "TE")),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Cancelación anticipada de un crédito por caja (32045)."""
    from app.services import caja as caja_svc
    from app.api.caja import _recibo_detalle

    def _do():   # H-157: dinero → idempotente (un doble-POST no genera dos recibos de cancelación).
        try:
            recibo = caja_svc.cancelar_credito(
                db, credito_id=credito_id, fecha_pago=req.fecha_pago,
                via_pago=req.via_pago, cajero=user.username)
        except caja_svc.ReglaNegocioError as e:
            raise HTTPException(409, str(e))
        return {"recibo_id": recibo.id}
    res = con_idempotencia(db, idempotency_key, f"POST /api/creditos/{credito_id}/cancelar", _do, usuario=user.username)
    return _recibo_detalle(db, db.get(models.Recibo, res["recibo_id"]))


@router.get("/turnos/generar/preview", response_model=schemas.TurnosPreview)
def turnos_generar_preview(periodo: str = Query(...), cantidad: int = Query(...),
                           grupo: str = Query(default="TODO"),
                           desde: date | None = Query(default=None),
                           db: Session = Depends(get_db)):
    """Vista previa de la generación de turnos del mes (32065). No escribe."""
    try:
        return svc.generar_turnos_preview(db, periodo=periodo, cantidad=cantidad,
                                          grupo=grupo, desde=desde)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/turnos/generar")
def turnos_generar(req: schemas.TurnosGenerarRequest, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(requiere_perfil("CR", "AF"))):
    """Genera los turnos del período (32065)."""
    try:
        return svc.generar_turnos_aplicar(db, periodo=req.periodo, cantidad=req.cantidad,
                                          grupo=req.grupo, desde=req.desde,
                                          usuario=user.username)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/turnos/asignar", response_model=schemas.TurnoCreditoOut, status_code=201)
def turnos_asignar(req: schemas.TurnoAsignarRequest, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(requiere_perfil("CR", "AF"))):
    """Asigna un turno a un solicitante (32067) o un turno excepcional por N° (32068)."""
    try:
        return svc.asignar_turno(db, periodo=req.periodo, cuil=req.cuil,
                                 apellido_nombre=req.apellido_nombre, linea=req.linea,
                                 sueldo=req.sueldo, numero=req.numero)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.get("/{credito_id}/recalculo", response_model=schemas.RecalculoPreview)
def recalculo_preview(credito_id: int, modo: str = Query(...),
                      primer_vto: date | None = Query(default=None),
                      haber: Decimal | None = Query(default=None),
                      db: Session = Depends(get_db)):
    """Vista previa del recálculo de un crédito (32535). No escribe."""
    try:
        return svc.recalculo_preview(db, credito_id, modo=modo,
                                     primer_vto=primer_vto, haber=haber)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/{credito_id}/recalculo")
def recalculo_aplicar(credito_id: int, req: schemas.RecalculoRequest,
                      db: Session = Depends(get_db),
                      user: models.Usuario = Depends(requiere_perfil("CR", "AF"))):
    """Aplica el recálculo del plan pendiente de un crédito (32535)."""
    try:
        return svc.recalculo_aplicar(db, credito_id, modo=req.modo,
                                     usuario=user.username,
                                     primer_vto=req.primer_vto, haber=req.haber)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/{credito_id}/baja", response_model=schemas.CreditoDetalle)
def dar_baja_credito(credito_id: int, req: schemas.BajaCreditoRequest,
                     request: Request, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(requiere_perfil("CR", "AF"))):
    """Baja/anulación administrativa de un crédito (32565), con motivo obligatorio."""
    cr = db.get(models.Credito, credito_id)
    estado_previo = cr.estado if cr else None
    ip = audit.ip_de(request)
    try:
        svc.dar_baja_credito(db, credito_id=credito_id, motivo=req.motivo,
                             usuario=user.username, fecha=req.fecha)
    except svc.ReglaNegocioError as e:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Credito", entidad_id=credito_id, operacion="BAJA",
                               resultado="RECHAZADO", antes={"estado": estado_previo},
                               detalle=f"Baja rechazada: {e}")
        raise HTTPException(409, str(e))
    audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                           entidad="Credito", entidad_id=credito_id, operacion="BAJA", resultado="OK",
                           antes={"estado": estado_previo}, despues={"estado": "B"},
                           detalle=f"Baja administrativa. Motivo: {req.motivo}")
    return obtener_credito(credito_id, db)


@router.get("/{credito_id}", response_model=schemas.CreditoDetalle)
def obtener_credito(credito_id: int, db: Session = Depends(get_db)):
    cr = db.get(models.Credito, credito_id)
    if not cr:
        raise HTTPException(404, "Crédito no encontrado")
    return _credito_detalle(db, cr)
