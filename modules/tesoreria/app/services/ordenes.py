"""Órdenes de pago de créditos.

Se confecciona con una o varias resoluciones / disposiciones de Despacho: entran completos sus lotes de
Créditos que no estén en otra orden (Créditos los deja PARA_LIQUIDAR y origina los créditos). La orden
crea su lote de pagos (una transferencia por crédito) y desde ahí sigue el circuito de cualquier lote:
aprobación según el workflow LOTE_PAGO y envío por Interbanking. Cada transferencia acreditada se le
avisa a Créditos; acreditadas todas las de un lote de Créditos, ese lote queda LIQUIDADO.

- La liquidación es completa: los pagos de una orden no se excluyen uno por uno.
- Anular (o rechazar su lote) sólo antes de enviar: Créditos devuelve los lotes a CON_RESOLUCION.
- Si algo falla a mitad de la confección, se deshace todo (Créditos libera lo que había reservado).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.dependencies.auth import Usuario
from app.services import creditos_central as creditos, lotes as svc_lotes

TIPO = {"RES": "Res.", "DIS": "Disp."}
# Cómo va el pago de la orden, según el estado de su lote de pagos.
ESTADO_PAGO = {"PENDIENTE_APROBACION": "PARA_APROBAR", "APROBADO": "PARA_PAGAR", "ENVIADO": "PAGANDO",
               "CONFIRMADO": "PAGADA", "CON_ERRORES": "CON_ERRORES", "RECHAZADO": "ANULADA"}
ANTES_DE_PAGAR = ("PENDIENTE_APROBACION", "APROBADO")


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def texto_acto(a: dict) -> str:
    n = a.get("numeroOficial") or a.get("numero")
    return f"{TIPO.get(a.get('tipo') or 'RES', 'Res.')} {n}/{a.get('anio')}"


# ── Serialización ────────────────────────────────────────────────────────────────────────────────
def resumen(op: models.OrdenPago) -> dict:
    lote = op.lote
    estado_pago = "ANULADA" if op.estado == "ANULADA" else ESTADO_PAGO.get(lote.estado if lote else "", "PARA_APROBAR")
    return {"id": op.id, "codigo": op.codigo, "anio": op.anio, "numero": op.numero, "estado": op.estado,
            "estado_pago": estado_pago, "importe": float(op.importe or 0), "cantidad": op.cantidad,
            "actos": op.actos or [], "actos_texto": ", ".join(texto_acto(g["acto"]) for g in (op.actos or [])),
            "lotes": [lt["codigo"] for g in (op.actos or []) for lt in g.get("lotes", [])],
            "lote": {"id": lote.id, "codigo": lote.codigo, "estado": lote.estado} if lote else None,
            "creado_por": op.creado_por, "creado_en": op.creado_en.isoformat() if op.creado_en else None,
            "anulada_por": op.anulada_por, "anulada_en": op.anulada_en.isoformat() if op.anulada_en else None,
            "motivo_anulacion": op.motivo_anulacion}


def detalle(op: models.OrdenPago, user: Usuario) -> dict:
    lote = op.lote
    return {**resumen(op),
            "pagos": [svc_lotes._pago(p) for p in lote.pagos] if lote else [],
            "puede_anular": (op.estado == "CONFECCIONADA" and user.puede("lotes:write")
                             and (lote is None or lote.estado in ANTES_DE_PAGAR))}


# ── Confección ───────────────────────────────────────────────────────────────────────────────────
def _numerar(db: Session, usuario: str) -> models.OrdenPago:
    anio = date.today().year
    for _ in range(5):
        ultimo = db.query(func.max(models.OrdenPago.numero)).filter(models.OrdenPago.anio == anio).scalar()
        try:
            with db.begin_nested():
                op = models.OrdenPago(anio=anio, numero=(ultimo or 0) + 1, actos=[], creado_por=usuario)
                db.add(op)
                db.flush()
            return op
        except IntegrityError:
            continue                                    # otro tomó ese número: releer y reintentar
    raise HTTPException(409, "No se pudo numerar la orden de pago; reintentá.")


def _deshacer(db: Session, op_id: int, liberar: bool) -> None:
    db.rollback()
    if liberar:
        try:
            creditos.liberar(op_id)
        except HTTPException:
            pass    # Créditos no la tiene o no responde: la reserva sin orden se libera al reintentar
    # Si el lote de pagos llegó a crearse, no puede quedar vivo sin su orden: se rechaza.
    lote = db.query(models.Lote).filter_by(origen="CREDITOS", referencia_origen=_codigo(db, op_id)).first()
    if lote is not None and lote.estado in ANTES_DE_PAGAR:
        lote.estado, lote.motivo_rechazo = "RECHAZADO", "La orden de pago no se pudo confeccionar."
        for p in lote.pagos:
            if p.estado == "PENDIENTE":
                p.estado, p.motivo, p.notificado = "RECHAZADO", lote.motivo_rechazo, "RECHAZADO"
    op = db.get(models.OrdenPago, op_id)
    if op is not None:
        if lote is None:
            db.delete(op)
        else:
            op.estado, op.lote_id, op.motivo_anulacion = "ANULADA", lote.id, "No se pudo confeccionar."
    db.commit()


def _codigo(db: Session, op_id: int) -> str:
    op = db.get(models.OrdenPago, op_id)
    return op.codigo if op is not None else ""


def _problemas(db: Session, pagos: list[dict]) -> list[str]:
    """Lo que haría rechazar alguna transferencia al crear el lote (la orden tiene que entrar completa)."""
    out = []
    for p in pagos:
        v, motivo = svc_lotes._validar_pago(p)
        if v is not None:
            vivo = (db.query(models.Pago).join(models.Lote)
                    .filter(models.Lote.origen == "CREDITOS", models.Pago.referencia_externa == v["referencia_externa"],
                            models.Pago.estado.in_(svc_lotes.VIVOS)).first())
            if vivo:
                motivo = f"ya está en el lote {vivo.lote.codigo} ({vivo.estado})"
        if motivo:
            out.append(f"{p.get('beneficiario') or p.get('referencia_externa')}: {motivo}")
    return out


def confeccionar(db: Session, actos: list[str], user: Usuario) -> models.OrdenPago:
    actos = sorted({a for a in actos if a})
    if not actos:
        raise HTTPException(422, "Elegí al menos una resolución o disposición.")
    op = _numerar(db, user.username)
    db.commit()                                       # el id ya es de esta orden: Créditos lo guarda
    op_id, codigo = op.id, op.codigo
    try:
        r = creditos.reservar(op_id, codigo, user.username, actos)
    except HTTPException:
        _deshacer(db, op_id, liberar=False)
        raise
    try:
        pagos = r.get("pagos") or []
        problemas = _problemas(db, pagos) if pagos else ["Créditos no devolvió transferencias."]
        if problemas:
            raise HTTPException(409, "La orden de pago no se puede confeccionar completa. " + "; ".join(problemas))
        op = db.get(models.OrdenPago, op_id)
        op.actos = r.get("actos") or []
        texto = ", ".join(texto_acto(g["acto"]) for g in op.actos)
        lote, _rechazados, _ya = svc_lotes.crear_lote(
            db, origen="CREDITOS", referencia_origen=codigo, descripcion=f"Orden de pago {codigo} · {texto}",
            pagos=pagos, usuario=user.username, callback_url=creditos.callback_url())
        op = db.get(models.OrdenPago, op_id)
        op.lote_id = lote.id
        op.cantidad = len(lote.pagos)
        op.importe = sum((p.monto for p in lote.pagos), Decimal(0))
        svc_lotes.evento(db, lote, user.username, "ORDEN_PAGO",
                         f"{codigo}: {texto} · lotes {', '.join(r.get('lotes') or [])}")
        db.commit()
        db.refresh(op)
        return op
    except Exception:
        _deshacer(db, op_id, liberar=True)
        raise


# ── Anulación ────────────────────────────────────────────────────────────────────────────────────
def anular(db: Session, op: models.OrdenPago, motivo: str, user: Usuario) -> models.OrdenPago:
    """Antes de enviar: Créditos devuelve los lotes a CON_RESOLUCION y el lote de pagos queda rechazado."""
    if op.estado != "CONFECCIONADA":
        raise HTTPException(409, "La orden de pago ya está anulada.")
    lote = op.lote
    if lote is not None and lote.estado not in ANTES_DE_PAGAR:
        raise HTTPException(409, "La orden de pago ya se empezó a pagar: no se anula.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(422, "Indicá el motivo de la anulación.")
    creditos.liberar(op.id)                           # si Créditos no responde, no se anula nada
    if lote is not None:
        lote.estado, lote.motivo_rechazo = "RECHAZADO", f"Orden de pago anulada: {motivo}"[:300]
        for p in lote.pagos:
            if p.estado == "PENDIENTE":
                # Créditos ya liberó los créditos: no hace falta avisarle cada pago.
                p.estado, p.motivo, p.notificado = "RECHAZADO", lote.motivo_rechazo, "RECHAZADO"
        svc_lotes.evento(db, lote, user.username, "ORDEN_PAGO_ANULADA", f"{op.codigo}: {motivo}")
    op.estado, op.anulada_por, op.anulada_en = "ANULADA", user.username, _ahora()
    op.motivo_anulacion = motivo[:300]
    db.commit()
    db.refresh(op)
    return op


def listar(db: Session, estado: str | None = None) -> list[models.OrdenPago]:
    q = db.query(models.OrdenPago)
    if estado:
        q = q.filter(models.OrdenPago.estado == estado)
    return q.order_by(models.OrdenPago.anio.desc(), models.OrdenPago.numero.desc()).limit(300).all()
