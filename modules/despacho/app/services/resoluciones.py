"""Reglas de las resoluciones y disposiciones.

Lo que hay que respetar del circuito administrativo:

- El **correlativo** es único por (año, SERIE) y lo arbitra la base: si dos usuarios crean a la vez,
  uno reintenta con el siguiente número en lugar de pisar al otro. Cada serie (el área que emite:
  general, seguros, juegos…) numera por su cuenta, como en el sistema anterior.
- El **número real** (el oficial) se carga después y tiene su propia numeración por (año, serie).
- Un acto **firmado, con número real o anulado es inmutable**: no se edita algo ya emitido. Tampoco
  se cambia tipo, número ni año, porque rompería la serie del correlativo.
- Anular no borra: deja el acto con su número y el motivo, como en el papel.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (BORRADOR, FIRMADA, SERIE_POR_DEFECTO, SERIES, ModeloResolucion, Resolucion,
                        ResolucionBeneficiario, TIPOS)

REINTENTOS_NUMERO = 5


def _validar_tipo(tipo: str) -> str:
    t = (tipo or "RES").upper()
    if t not in TIPOS:
        raise HTTPException(422, "El tipo tiene que ser RES (resolución) o DIS (disposición).")
    return t


def _validar_serie(serie) -> int:
    s = SERIE_POR_DEFECTO if serie is None else int(serie)
    if s not in SERIES:
        raise HTTPException(422, f"La serie {s} no existe.")
    return s


def _proximo_numero(db: Session, anio: int, serie: int) -> int:
    n = db.scalar(select(func.max(Resolucion.numero)).where(
        Resolucion.anio == anio, Resolucion.serie == serie))
    return (n or 0) + 1


def _proximo_numero_real(db: Session, anio: int, serie: int) -> int:
    n = db.scalar(select(func.max(Resolucion.numero_real)).where(
        Resolucion.anio == anio, Resolucion.serie == serie))
    return (n or 0) + 1


def _modelo(db: Session, modelo_id: int | None) -> ModeloResolucion | None:
    if not modelo_id:
        return None
    m = db.get(ModeloResolucion, modelo_id)
    if m is None:
        raise HTTPException(422, "El modelo de resolución no existe.")
    return m


def _beneficiarios(db: Session, resolucion: Resolucion, filas) -> None:
    """Reemplaza la grilla completa: es como se edita en la pantalla.

    Acepta tanto los objetos del esquema como diccionarios (el importador arma diccionarios)."""
    if filas is None:
        return
    resolucion.beneficiarios.clear()
    db.flush()
    for fila in filas:
        b = fila if isinstance(fila, dict) else fila.model_dump()
        resolucion.beneficiarios.append(ResolucionBeneficiario(
            tipo_doc=int(b.get("tipo_doc") or 0),
            nro_doc=str(b.get("nro_doc") or "")[:11],
            nombre=str(b.get("nombre") or "")[:80],
            tipo_bene=int(b.get("tipo_bene") or 0),
            importe=Decimal(str(b.get("importe") or 0))))


def crear(db: Session, datos, usuario: str = "") -> Resolucion:
    tipo = _validar_tipo(datos.tipo)
    fecha = datos.fecha or date.today()
    modelo = _modelo(db, datos.modelo_id)
    # El modelo ya pertenece a una serie: manda la suya, así el motivo y el número van juntos.
    serie = _validar_serie(modelo.serie if modelo is not None else datos.serie)

    texto = (datos.texto or "").strip()
    motivo_codigo, motivo = 0, ""
    if modelo is not None:
        # El modelo aporta el motivo y, si no se escribió nada, el cuerpo inicial.
        motivo_codigo, motivo = modelo.codigo, modelo.descripcion
        texto = texto or (modelo.plantilla or "")
    asunto = (datos.asunto or "").strip() or motivo or f"{tipo} {fecha.year}"

    for intento in range(REINTENTOS_NUMERO):
        r = Resolucion(
            numero=_proximo_numero(db, fecha.year, serie), anio=fecha.year, tipo=tipo, serie=serie,
            fecha=fecha,
            organo=(datos.organo or "")[:60], asunto=asunto[:200], motivo_codigo=motivo_codigo,
            motivo=(motivo or "")[:120], importe=Decimal(str(datos.importe or 0)),
            modelo_id=modelo.id if modelo else None, origen=(datos.origen or "")[:40],
            nro_op=datos.nro_op, texto=texto, estado=BORRADOR, creado_por=usuario[:60])
        db.add(r)
        try:
            # La unicidad (año, tipo, número) la garantiza la DB: si otro se adelantó, se reintenta.
            with db.begin_nested():
                db.flush()
            break
        except IntegrityError:
            db.rollback()
            if intento == REINTENTOS_NUMERO - 1:
                raise HTTPException(409, "No se pudo asignar el número; probá de nuevo.")
    _beneficiarios(db, r, datos.beneficiarios)
    db.commit()
    db.refresh(r)
    return r


def _editable(r: Resolucion) -> None:
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada: no se puede modificar.")
    if r.oficial:
        raise HTTPException(422, "El instrumento ya fue emitido (firmado o con N° real): no se modifica.")


def editar(db: Session, resolucion_id: int, datos) -> Resolucion:
    r = obtener(db, resolucion_id)
    _editable(r)
    if datos.modelo_id is not None:
        modelo = _modelo(db, datos.modelo_id)
        if modelo.serie != r.serie:
            raise HTTPException(422, "Ese modelo es de otra serie: cambiaría la numeración del acto.")
        r.modelo_id = modelo.id
        r.motivo_codigo, r.motivo = modelo.codigo, modelo.descripcion[:120]
    for campo, valor, largo in (("asunto", datos.asunto, 200), ("organo", datos.organo, 60),
                                ("origen", datos.origen, 40)):
        if valor is not None:
            setattr(r, campo, valor[:largo])
    if datos.fecha is not None:
        # El año no cambia: la serie del correlativo es por año y tipo.
        if datos.fecha.year != r.anio:
            raise HTTPException(422, "No se puede cambiar el año: rompería la serie del correlativo.")
        r.fecha = datos.fecha
    if datos.texto is not None:
        r.texto = datos.texto
    if datos.importe is not None:
        r.importe = Decimal(str(datos.importe))
    if datos.nro_op is not None:
        r.nro_op = datos.nro_op
    _beneficiarios(db, r, datos.beneficiarios)
    db.commit()
    db.refresh(r)
    return r


def firmar(db: Session, resolucion_id: int) -> Resolucion:
    r = obtener(db, resolucion_id)
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada.")
    if r.estado == FIRMADA:
        raise HTTPException(422, "La resolución ya está firmada.")
    r.estado = FIRMADA
    db.commit()
    db.refresh(r)
    return r


def asignar_numero_real(db: Session, resolucion_id: int, fecha_real: date | None = None) -> Resolucion:
    """Carga el número OFICIAL, que llega después del correlativo. Con esto el acto queda emitido."""
    r = obtener(db, resolucion_id)
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada.")
    if r.numero_real is not None:
        raise HTTPException(422, f"Ya tiene N° real ({r.numero_real}).")
    freal = fecha_real or date.today()
    for intento in range(REINTENTOS_NUMERO):
        r.numero_real = _proximo_numero_real(db, freal.year, r.serie)
        r.fecha_real = freal
        r.estado = FIRMADA
        try:
            with db.begin_nested():
                db.flush()
            break
        except IntegrityError:
            db.rollback()
            if intento == REINTENTOS_NUMERO - 1:
                raise HTTPException(409, "No se pudo asignar el N° real; probá de nuevo.")
    db.commit()
    db.refresh(r)
    return r


def anular(db: Session, resolucion_id: int, motivo: str) -> Resolucion:
    """Anular NO borra: el acto queda con su número y el motivo, como en el papel."""
    r = obtener(db, resolucion_id)
    if r.anulada:
        raise HTTPException(422, "La resolución ya está anulada.")
    if not (motivo or "").strip():
        raise HTTPException(422, "Indicá el motivo de la anulación.")
    r.anulada = True
    r.motivo_anulacion = motivo.strip()[:200]
    db.commit()
    db.refresh(r)
    return r


def obtener(db: Session, resolucion_id: int) -> Resolucion:
    r = db.get(Resolucion, resolucion_id)
    if r is None:
        raise HTTPException(404, "Resolución no encontrada")
    return r


def listar(db: Session, *, tipo: str | None = None, anio: int | None = None,
           estado: str | None = None, buscar: str | None = None, serie: int | None = None,
           pagina: int = 1, por_pagina: int = 20) -> tuple[list[Resolucion], int]:
    q = select(Resolucion)
    if tipo:
        q = q.where(Resolucion.tipo == tipo.upper())
    if serie:
        q = q.where(Resolucion.serie == serie)
    if anio:
        q = q.where(Resolucion.anio == anio)
    if estado == "ANULADA":
        q = q.where(Resolucion.anulada.is_(True))
    elif estado:
        q = q.where(Resolucion.estado == estado, Resolucion.anulada.is_(False))
    if buscar:
        like = f"%{buscar}%"
        q = q.where(Resolucion.asunto.ilike(like) | Resolucion.motivo.ilike(like)
                    | Resolucion.origen.ilike(like))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    filas = db.scalars(q.order_by(Resolucion.anio.desc(), Resolucion.numero.desc())
                        .offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return list(filas), total
