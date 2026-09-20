"""Consultas de trámites de Mesa de Entradas (histórico real)."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models

ESTADO_TXT = {"A": "En trámite", "C": "Cerrado/Archivado", "B": "Baja", "": "-"}


def tipos(db: Session) -> list[dict]:
    return [{"codigo": t.codigo, "descripcion": t.descripcion, "corta": t.corta}
            for t in db.scalars(select(models.TramiteTipo).order_by(models.TramiteTipo.codigo)).all()]


def consultar(db: Session, *, tipo: str | None = None, estado: str | None = None,
              anio: int | None = None, q: str | None = None,
              solo_expedientes: bool = False,
              limit: int = 25, offset: int = 0, cap: int = 200) -> dict:
    """Trámites paginados. Selecciona columnas puntuales (export rápido).

    `solo_expedientes`: filtra a los expedientes (tipo empieza con 'E')."""
    T = models.Tramite
    cols = (T.id, T.tipo, T.letra, T.numero, T.anio, T.sentido, T.referencia,
            T.iniciador, T.asegurado, T.estado, T.oficina_actual, T.hojas, T.fecha_alta)
    base = select(*cols)
    if solo_expedientes:
        base = base.where(T.tipo.like("E%"))
    if tipo:
        base = base.where(T.tipo == tipo)
    if estado:
        base = base.where(T.estado == estado)
    if anio:
        base = base.where(T.anio == anio)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(T.iniciador.like(like) | T.asegurado.like(like)
                          | T.referencia.like(like))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(T.fecha_alta.desc(), T.id.desc())
                      .limit(min(limit, cap)).offset(max(offset, 0))).all()
    # nombre de la oficina actual en vez del número (consistente con los pases)
    nombres = {o.id: o.denominacion for o in db.scalars(select(models.Oficina)).all()}

    def ofi(n):
        return nombres.get(n, f"Of. {n}") if n else "-"

    items = [{"id": r.id, "expediente": f"{r.tipo} {r.letra}-{r.numero}/{r.anio}",
              "tipo": r.tipo, "referencia": r.referencia,
              "iniciador": r.iniciador or r.asegurado, "destino_asegurado": r.asegurado,
              "estado": ESTADO_TXT.get(r.estado, r.estado), "oficina": ofi(r.oficina_actual),
              "hojas": r.hojas, "fecha_alta": r.fecha_alta} for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def oficinas(db: Session) -> list[dict]:
    return [{"id": o.id, "denominacion": o.denominacion,
             "telefono_interno": o.telefono_interno, "telefono_linea": o.telefono_linea,
             "interna": o.interna}
            for o in db.scalars(select(models.Oficina).order_by(models.Oficina.id)).all()]


def pases_de_tramite(db: Session, tramite_id: int) -> dict | None:
    """Historial de pases (movimientos de oficina) de un trámite (VFP: pases)."""
    t = db.get(models.Tramite, tramite_id)
    if not t:
        return None
    P = models.TramitePase
    pases = db.scalars(select(P).where(
        P.tipo == t.tipo, P.letra == t.letra, P.numero == t.numero, P.anio == t.anio)
        .order_by(P.fecha_pase, P.id)).all()
    # nombres de oficina para mostrar en vez del número
    nombres = {o.id: o.denominacion for o in db.scalars(select(models.Oficina)).all()}

    def ofi(n):
        return nombres.get(n, f"Of. {n}") if n else "-"

    return {
        "tramite_id": t.id, "expediente": f"{t.tipo} {t.letra}-{t.numero}/{t.anio}",
        "referencia": t.referencia, "cantidad": len(pases),
        "pases": [{"orden": i + 1, "fecha": p.fecha_pase,
                   "oficina_origen": ofi(p.oficina_origen),
                   "oficina_destino": ofi(p.oficina_destino),
                   "texto": p.texto, "activo": p.activo}
                  for i, p in enumerate(pases)],
    }


def ingresados_por_periodo(db: Session, desde=None, hasta=None) -> dict:
    """Informe de trámites ingresados por tipo (VFP: tramitesdiarios / parte diario)."""
    T = models.Tramite
    q = (select(T.tipo, func.count(T.id))
         .where(T.sentido == "I").group_by(T.tipo).order_by(func.count(T.id).desc()))
    if desde:
        q = q.where(T.fecha_alta >= desde)
    if hasta:
        q = q.where(T.fecha_alta <= hasta)
    nombres = {t.codigo: t.descripcion for t in db.scalars(select(models.TramiteTipo)).all()}
    filas, total = [], 0
    for tipo, n in db.execute(q).all():
        filas.append({"tipo": tipo, "descripcion": nombres.get(tipo, tipo), "cantidad": n})
        total += n
    return {"por_tipo": filas, "total": total}
