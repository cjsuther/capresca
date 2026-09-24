"""Expedientes y pases (mesa de entradas).

Un expediente circula de oficina en oficina; cada movimiento queda registrado como un pase. La
historia de pases no se edita ni se borra: es el recorrido del trámite.
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expediente, Pase


def listar(db: Session, *, estado: str | None = None, buscar: str | None = None,
           oficina: str | None = None) -> list[Expediente]:
    q = select(Expediente)
    if estado:
        q = q.where(Expediente.estado == estado)
    if oficina:
        q = q.where(Expediente.oficina_actual == oficina)
    if buscar:
        like = f"%{buscar}%"
        q = q.where(Expediente.numero.ilike(like) | Expediente.caratula.ilike(like)
                    | Expediente.iniciador.ilike(like))
    return list(db.scalars(q.order_by(Expediente.fecha_inicio.desc(), Expediente.id.desc())).all())


def por_oficina(db: Session) -> list[dict]:
    """Cuántos expedientes en trámite tiene cada oficina (el tablero de mesa de entradas)."""
    filas = db.execute(
        select(Expediente.oficina_actual, func.count())
        .where(Expediente.estado == "T")
        .group_by(Expediente.oficina_actual)
        .order_by(func.count().desc())).all()
    return [{"oficina": o or "(sin asignar)", "cantidad": c} for o, c in filas]


def obtener(db: Session, expediente_id: int) -> Expediente:
    e = db.get(Expediente, expediente_id)
    if e is None:
        raise HTTPException(404, "Expediente no encontrado")
    return e


def crear(db: Session, datos, usuario: str = "") -> Expediente:
    numero = (datos.numero or "").strip()
    if not numero:
        raise HTTPException(422, "El número de expediente es obligatorio.")
    if db.scalar(select(Expediente).where(Expediente.numero == numero)):
        raise HTTPException(409, f"Ya existe el expediente {numero}.")
    if not (datos.caratula or "").strip():
        raise HTTPException(422, "La carátula es obligatoria.")
    e = Expediente(numero=numero[:20], caratula=datos.caratula.strip()[:200],
                   iniciador=(datos.iniciador or "")[:80],
                   fecha_inicio=datos.fecha_inicio or date.today(),
                   estado="T", oficina_actual=(datos.oficina or "")[:60])
    db.add(e)
    db.flush()
    # El alta es el primer pase: de dónde salió y a qué oficina entró.
    e.pases.append(Pase(fecha=e.fecha_inicio, oficina_origen="", oficina_destino=e.oficina_actual,
                        motivo="Alta del expediente", usuario=usuario[:60]))
    db.commit()
    db.refresh(e)
    return e


def pasar(db: Session, expediente_id: int, datos, usuario: str = "") -> Expediente:
    e = obtener(db, expediente_id)
    if e.estado == "A":
        raise HTTPException(422, "El expediente está archivado: no se puede pasar.")
    destino = (datos.oficina_destino or "").strip()
    if not destino:
        raise HTTPException(422, "Indicá la oficina de destino.")
    if destino == e.oficina_actual:
        raise HTTPException(422, "El expediente ya está en esa oficina.")
    e.pases.append(Pase(fecha=datos.fecha or date.today(), oficina_origen=e.oficina_actual,
                        oficina_destino=destino[:60], motivo=(datos.motivo or "")[:200],
                        usuario=usuario[:60]))
    e.oficina_actual = destino[:60]
    db.commit()
    db.refresh(e)
    return e


def archivar(db: Session, expediente_id: int, usuario: str = "") -> Expediente:
    e = obtener(db, expediente_id)
    if e.estado == "A":
        raise HTTPException(422, "El expediente ya está archivado.")
    e.estado = "A"
    e.pases.append(Pase(fecha=date.today(), oficina_origen=e.oficina_actual,
                        oficina_destino="ARCHIVO", motivo="Archivo del expediente",
                        usuario=usuario[:60]))
    e.oficina_actual = "ARCHIVO"
    db.commit()
    db.refresh(e)
    return e
