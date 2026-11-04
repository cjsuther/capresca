"""Catálogo de series de numeración (VFP: TIPO_RES): el área que emite el acto.

El número de la serie lo elige quien la crea (para seguir el del sistema anterior) y después no se
cambia: es la clave de la numeración de los actos. El nombre y el orden sí se editan. Una serie con
modelos, actos o numeración fijada no se borra: se desactiva, y deja de ofrecerse para lo nuevo.
"""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, ModeloResolucion, NumeracionSerie, Resolucion, Serie


def _usos(db: Session) -> dict[int, int]:
    """Cuántos modelos, actos y numeraciones fijadas tiene cada serie."""
    usos: dict[int, int] = {}
    for modelo in (ModeloResolucion, Resolucion, NumeracionSerie):
        for serie, n in db.execute(select(modelo.serie, func.count()).group_by(modelo.serie)):
            usos[serie] = usos.get(serie, 0) + n
    return usos


def _salida(s: Serie, usos: dict[int, int]) -> dict:
    return {"serie": s.numero, "nombre": s.nombre, "orden": s.orden, "activa": s.activa,
            "en_uso": usos.get(s.numero, 0) > 0}


def listar(db: Session, incluir_inactivas: bool = False) -> list[dict]:
    q = select(Serie).order_by(Serie.orden, Serie.numero)
    if not incluir_inactivas:
        q = q.where(Serie.activa.is_(True))
    usos = _usos(db)
    return [_salida(s, usos) for s in db.scalars(q)]


def obtener(db: Session, numero: int) -> Serie:
    s = db.get(Serie, numero)
    if s is None:
        raise HTTPException(404, f"La serie {numero} no existe.")
    return s


def validar(db: Session, numero, actual: int | None = None) -> int:
    """La serie de un modelo o acto: tiene que existir y estar activa. La que ya tenía (`actual`) se
    acepta aunque se haya desactivado después, para poder seguir editando lo existente."""
    n = SERIE_POR_DEFECTO if numero is None else int(numero)
    s = db.get(Serie, n)
    if s is None:
        raise HTTPException(422, f"La serie {n} no existe.")
    if not s.activa and n != actual:
        raise HTTPException(422, f"La serie {n} ({s.nombre}) está inactiva.")
    return n


def _nombre(nombre: str | None) -> str:
    n = " ".join((nombre or "").split()).upper()[:60]
    if not n:
        raise HTTPException(422, "El nombre de la serie es obligatorio.")
    return n


def _nombre_libre(db: Session, nombre: str, numero: int | None = None) -> None:
    otra = db.scalar(select(Serie).where(func.upper(Serie.nombre) == nombre, Serie.numero != (numero or -1)))
    if otra is not None:
        raise HTTPException(409, f"El nombre {nombre} ya lo usa la serie {otra.numero}.")


def _guardar(db: Session, s: Serie) -> dict:
    try:
        db.commit()
    except IntegrityError:
        # Otro usuario creó la misma serie o el mismo nombre entre la verificación y el commit.
        db.rollback()
        raise HTTPException(409, f"Ya existe una serie con el número {s.numero} o el nombre {s.nombre}.")
    db.refresh(s)
    return _salida(s, _usos(db))


def crear(db: Session, datos) -> dict:
    numero = int(datos.serie)
    if numero < 1:
        raise HTTPException(422, "El número de la serie tiene que ser mayor que cero.")
    if db.get(Serie, numero) is not None:
        raise HTTPException(409, f"La serie {numero} ya existe.")
    nombre = _nombre(datos.nombre)
    _nombre_libre(db, nombre)
    orden = datos.orden if datos.orden is not None else \
        (db.scalar(select(func.max(Serie.orden))) or 0) + 1
    s = Serie(numero=numero, nombre=nombre, orden=orden, activa=True)
    db.add(s)
    return _guardar(db, s)


def editar(db: Session, numero: int, datos) -> dict:
    """Cambia el nombre y el orden. El número no: es la clave de la numeración de los actos."""
    s = obtener(db, numero)
    s.nombre = _nombre(datos.nombre)
    _nombre_libre(db, s.nombre, numero)
    if datos.orden is not None:
        s.orden = datos.orden
    return _guardar(db, s)


def activar(db: Session, numero: int, activa: bool) -> dict:
    s = obtener(db, numero)
    if not activa and numero == SERIE_POR_DEFECTO:
        raise HTTPException(422, f"La serie {s.nombre} es la serie por defecto: no se puede desactivar.")
    s.activa = bool(activa)
    return _guardar(db, s)


def eliminar(db: Session, numero: int) -> None:
    """Sólo una serie sin uso (p. ej. cargada por error). Si ya tiene modelos o actos, se desactiva."""
    s = obtener(db, numero)
    if numero == SERIE_POR_DEFECTO:
        raise HTTPException(422, f"La serie {s.nombre} es la serie por defecto: no se puede borrar.")
    if _usos(db).get(numero):
        raise HTTPException(409, f"La serie {numero} ya tiene modelos, actos o numeración: desactivala en "
                                 "lugar de borrarla.")
    db.delete(s)
    db.commit()
