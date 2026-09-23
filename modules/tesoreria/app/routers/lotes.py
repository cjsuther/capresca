"""API de Tesorería para las pantallas (detrás del gateway: permisos `tesoreria:*`)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.services import lotes as svc

router = APIRouter(prefix="/lotes", tags=["lotes"])


class PagoIn(BaseModel):
    referencia_externa: str = ""
    beneficiario: str
    documento: str = ""
    cbu: str
    monto: float
    concepto: str = ""


class LoteManualIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=200)
    pagos: list[PagoIn] = Field(min_length=1, max_length=500)


class MotivoIn(BaseModel):
    motivo: str = ""


class EnviarIn(BaseModel):
    cuenta_origen: str | None = None      # número de cuenta desde la que sale el pago


class ResolverIn(BaseModel):
    resultado: str
    observacion: str = ""


def _lote(db: Session, lote_id: int) -> models.Lote:
    lote = db.get(models.Lote, lote_id)
    if not lote:
        raise HTTPException(404, "Lote no encontrado")
    return lote


@router.get("")
def listar(estado: str | None = Query(None), origen: str | None = Query(None), db: Session = Depends(get_db),
           _u: Usuario = Depends(usuario_actual)):
    q = db.query(models.Lote)
    if estado:
        q = q.filter(models.Lote.estado.in_(estado.split(",")))
    if origen:
        q = q.filter(models.Lote.origen == origen)
    lotes = q.order_by(models.Lote.creado_en.desc(), models.Lote.id.desc()).limit(300).all()
    pendientes = db.query(models.Lote).filter(models.Lote.estado.in_(["PENDIENTE_APROBACION", "APROBADO"])).count()
    return {"items": [svc.resumen(l) for l in lotes], "pendientes": pendientes,
            "envio_simulado": svc.settings.envio_simulado}


@router.get("/cuentas-origen")
def cuentas_origen(_u: Usuario = Depends(usuario_actual)):
    """Cuentas desde las que se puede pagar (Interbanking); el tesorero elige una al enviar el lote."""
    return svc.cuentas_para_pagar()


@router.get("/{lote_id}")
def ver(lote_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    return svc.detalle(db, _lote(db, lote_id), user)


@router.post("", status_code=201)
def crear_manual(data: LoteManualIn, db: Session = Depends(get_db), user: Usuario = Depends(requiere("lotes:write"))):
    """Lote cargado a mano (o importado de un CSV desde la pantalla)."""
    from datetime import datetime
    sello = datetime.now().strftime("%Y%m%d%H%M%S%f")
    referencia = f"{user.username} {sello}"
    pagos = []
    for i, p in enumerate(data.pagos, start=1):
        d = p.model_dump()
        # Sin referencia propia, una única por lote: "manual-1" se repetiría entre lotes y el control de
        # pago vivo descartaría los del segundo lote.
        d["referencia_externa"] = d["referencia_externa"] or f"manual-{sello}-{i}"
        pagos.append(d)
    lote, rechazados, _ = svc.crear_lote(db, origen="MANUAL", referencia_origen=referencia, descripcion=data.descripcion,
                                         pagos=pagos, usuario=user.username)
    return {**svc.detalle(db, lote, user), "rechazados": rechazados}


@router.post("/{lote_id}/pagos/{pago_id}/excluir")
def excluir(lote_id: int, pago_id: int, data: MotivoIn, db: Session = Depends(get_db),
            user: Usuario = Depends(requiere("lotes:write"))):
    lote = _lote(db, lote_id)
    svc.excluir(db, lote, pago_id, data.motivo, user)
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/pagos/{pago_id}/incluir")
def incluir(lote_id: int, pago_id: int, db: Session = Depends(get_db), user: Usuario = Depends(requiere("lotes:write"))):
    lote = _lote(db, lote_id)
    svc.incluir(db, lote, pago_id, user)
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/aprobar")
def aprobar(lote_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    svc.aprobar(db, lote, user)
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/rechazar")
def rechazar(lote_id: int, data: MotivoIn, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    svc.rechazar(db, lote, data.motivo, user)
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/enviar")
def enviar(lote_id: int, data: EnviarIn | None = None, db: Session = Depends(get_db),
           user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    svc.enviar(db, lote, user, (data.cuenta_origen if data else None))
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/actualizar")
def actualizar(lote_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    cambios = svc.actualizar(db, lote, user.username)
    return {**svc.detalle(db, lote, user), "cambios": cambios}


@router.post("/{lote_id}/pagos/{pago_id}/reintentar")
def reintentar(lote_id: int, pago_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    svc.reintentar(db, lote, pago_id, user)
    return svc.detalle(db, lote, user)


@router.post("/{lote_id}/pagos/{pago_id}/resolver")
def resolver(lote_id: int, pago_id: int, data: ResolverIn, db: Session = Depends(get_db),
             user: Usuario = Depends(usuario_actual)):
    lote = _lote(db, lote_id)
    svc.resolver_incierto(db, lote, pago_id, data.resultado, data.observacion, user)
    return svc.detalle(db, lote, user)
