"""Catálogo de modelos (plantillas) de resoluciones y disposiciones.

Cada modelo aporta dos cosas al acto que se crea con él: su descripción pasa a ser el MOTIVO y su
plantilla, el cuerpo inicial del texto. El código lo carga el usuario al crear el modelo, es numérico,
no se repite en todo el catálogo y se puede cambiar después.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, SERIES, ModeloResolucion, Resolucion, TIPOS


def _validar(datos) -> tuple[str, int]:
    if not (datos.descripcion or "").strip():
        raise HTTPException(422, "La descripción del modelo es obligatoria.")
    tipo = (datos.tipo or "RES").upper()
    if tipo not in TIPOS:
        raise HTTPException(422, "El tipo tiene que ser RES (resolución) o DIS (disposición).")
    serie = SERIE_POR_DEFECTO if getattr(datos, "serie", None) is None else int(datos.serie)
    if serie not in SERIES:
        raise HTTPException(422, f"La serie {serie} no existe.")
    return tipo, serie


def _codigo(db: Session, valor, excluir_id: int | None = None) -> int:
    """El código del modelo: entero positivo y que no use otro modelo."""
    if valor is None:
        raise HTTPException(422, "El código del modelo es obligatorio.")
    codigo = int(valor)
    if codigo < 1:
        raise HTTPException(422, "El código del modelo tiene que ser un número mayor que cero.")
    otro = db.scalar(select(ModeloResolucion).where(ModeloResolucion.codigo == codigo))
    if otro is not None and otro.id != excluir_id:
        raise HTTPException(409, f"El código {codigo} ya lo usa el modelo \"{otro.descripcion}\".")
    return codigo


def _guardar(db: Session, m: ModeloResolucion) -> ModeloResolucion:
    try:
        db.commit()
    except IntegrityError:
        # Otro usuario guardó el mismo código entre la verificación y el commit.
        db.rollback()
        raise HTTPException(409, f"El código {m.codigo} ya lo usa otro modelo.")
    db.refresh(m)
    return m


def listar(db: Session, *, tipo: str | None = None, buscar: str | None = None,
           serie: int | None = None, sector: str | None = None, actividad: str | None = None,
           incluir_inactivos: bool = False) -> list[ModeloResolucion]:
    q = select(ModeloResolucion)
    if sector:
        q = q.where(ModeloResolucion.sector == sector)
    if actividad:
        q = q.where(ModeloResolucion.actividad == actividad)
    if tipo:
        q = q.where(ModeloResolucion.tipo == tipo.upper())
    if serie:
        q = q.where(ModeloResolucion.serie == serie)
    if not incluir_inactivos:
        q = q.where(ModeloResolucion.activo.is_(True))
    if buscar:
        q = q.where(ModeloResolucion.descripcion.ilike(f"%{buscar}%"))
    return list(db.scalars(q.order_by(ModeloResolucion.codigo)).all())


def obtener(db: Session, modelo_id: int) -> ModeloResolucion:
    m = db.get(ModeloResolucion, modelo_id)
    if m is None:
        raise HTTPException(404, "Modelo no encontrado")
    return m


def crear(db: Session, datos) -> ModeloResolucion:
    tipo, serie = _validar(datos)
    codigo = _codigo(db, datos.codigo)
    m = ModeloResolucion(codigo=codigo, serie=serie, descripcion=datos.descripcion.strip()[:120],
                         tipo=tipo, es_seguros=bool(datos.es_seguros),
                         plantilla=datos.plantilla or "", sector=(datos.sector or "").strip()[:80],
                         actividad=(datos.actividad or "").strip()[:80])
    db.add(m)
    return _guardar(db, m)


def editar(db: Session, modelo_id: int, datos) -> ModeloResolucion:
    m = obtener(db, modelo_id)
    m.tipo, m.serie = _validar(datos)
    if datos.codigo is not None:
        m.codigo = _codigo(db, datos.codigo, excluir_id=m.id)
    m.descripcion = datos.descripcion.strip()[:120]
    if datos.plantilla is not None:
        m.plantilla = datos.plantilla
    if datos.es_seguros is not None:
        m.es_seguros = bool(datos.es_seguros)
    if datos.sector is not None:
        m.sector = datos.sector.strip()[:80]
    if datos.actividad is not None:
        m.actividad = datos.actividad.strip()[:80]
    if datos.activo is not None:
        m.activo = bool(datos.activo)
    return _guardar(db, m)


def activar(db: Session, modelo_id: int, activo: bool) -> ModeloResolucion:
    """Un modelo inactivo no se ofrece para redactar, pero sigue existiendo."""
    m = obtener(db, modelo_id)
    m.activo = bool(activo)
    db.commit()
    db.refresh(m)
    return m


def eliminar(db: Session, modelo_id: int) -> None:
    """Borra el modelo. Los actos que se redactaron con él no cambian: el motivo y el texto ya se
    copiaron al acto; sólo pierden la referencia al modelo."""
    m = obtener(db, modelo_id)
    for r in db.scalars(select(Resolucion).where(Resolucion.modelo_id == m.id)):
        r.modelo_id = None
    db.delete(m)
    db.commit()
