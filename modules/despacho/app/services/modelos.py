"""Catálogo de modelos (plantillas) de resoluciones y disposiciones.

Cada modelo aporta dos cosas al acto que se crea con él: su descripción pasa a ser el MOTIVO y su
plantilla, el cuerpo inicial del texto. El código se autoasigna (MAX+1) como en el sistema anterior,
pero el identificador de verdad es el id: el código se repite entre resoluciones y disposiciones.
"""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ModeloResolucion, TIPOS


def _validar(datos) -> str:
    if not (datos.descripcion or "").strip():
        raise HTTPException(422, "La descripción del modelo es obligatoria.")
    tipo = (datos.tipo or "RES").upper()
    if tipo not in TIPOS:
        raise HTTPException(422, "El tipo tiene que ser RES (resolución) o DIS (disposición).")
    return tipo


def listar(db: Session, *, tipo: str | None = None, buscar: str | None = None,
           incluir_inactivos: bool = False) -> list[ModeloResolucion]:
    q = select(ModeloResolucion)
    if tipo:
        q = q.where(ModeloResolucion.tipo == tipo.upper())
    if not incluir_inactivos:
        q = q.where(ModeloResolucion.activo.is_(True))
    if buscar:
        q = q.where(ModeloResolucion.descripcion.ilike(f"%{buscar}%"))
    return list(db.scalars(q.order_by(ModeloResolucion.tipo, ModeloResolucion.codigo)).all())


def obtener(db: Session, modelo_id: int) -> ModeloResolucion:
    m = db.get(ModeloResolucion, modelo_id)
    if m is None:
        raise HTTPException(404, "Modelo no encontrado")
    return m


def crear(db: Session, datos) -> ModeloResolucion:
    tipo = _validar(datos)
    codigo = datos.codigo or ((db.scalar(select(func.max(ModeloResolucion.codigo))) or 0) + 1)
    m = ModeloResolucion(codigo=codigo, descripcion=datos.descripcion.strip()[:120], tipo=tipo,
                         es_seguros=bool(datos.es_seguros), plantilla=datos.plantilla or "")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def editar(db: Session, modelo_id: int, datos) -> ModeloResolucion:
    m = obtener(db, modelo_id)
    m.tipo = _validar(datos)
    m.descripcion = datos.descripcion.strip()[:120]
    if datos.plantilla is not None:
        m.plantilla = datos.plantilla
    if datos.es_seguros is not None:
        m.es_seguros = bool(datos.es_seguros)
    if datos.activo is not None:
        m.activo = bool(datos.activo)
    db.commit()
    db.refresh(m)
    return m
