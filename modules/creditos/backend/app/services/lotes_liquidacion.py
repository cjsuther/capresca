"""Lotes: las solicitudes aprobadas que se otorgan y liquidan juntas.

Circuito:
- Una solicitud APROBADA y **liquidable** (cliente en el padrón, CUIL y CBU de 22 dígitos) entra sola
  al lote de su producto (tipo de crédito) y fecha de aprobación, hasta el tope del parámetro
  LOTE_LIQUIDACION_MAX (Créditos → Parámetros; 50 si no está cargado). Las que no son liquidables
  quedan "fuera de lote" y entran apenas se completan: un lote sólo tiene lo que se puede liquidar.
- El número es correlativo dentro del año y arranca en 1 cada año: 2026-0001, 2026-0002…
- Despacho le asigna al lote la resolución que lo otorga (una resolución puede alcanzar varios
  lotes, sin que la suma de sus importes pase el importe de la resolución). El lote queda
  CON_RESOLUCION: sus solicitudes no se modifican; sólo se pueden mover a otro lote del mismo
  producto y fecha (o a uno nuevo).
- Liquidar el lote origina y desembolsa todas sus solicitudes (contratos.liquidar_lote) y lo deja
  LIQUIDADO.

Concurrencia: el lote se toma con lock antes de contarlo, así dos aprobaciones simultáneas no lo
pasan del tope. Abrir un lote lo arbitra la DB con dos constraints únicas: (anio, numero) y
(producto, fecha, orden); la que choca reintenta y entra al que abrió la otra.

Un lote también puede tener contratos A_LIQUIDAR sin solicitud (originados antes del circuito de
solicitudes): son ítems del lote como cualquier otro.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, models_productos as m

PARAMETRO = "LOTE_LIQUIDACION_MAX"
POR_DEFECTO = 50

ABIERTO, CON_RESOLUCION, LIQUIDADO = "ABIERTO", "CON_RESOLUCION", "LIQUIDADO"


def maximo(db: Session) -> int:
    p = db.query(models.Parametro).filter(models.Parametro.clave == PARAMETRO).first()
    try:
        return max(1, int(str(p.valor).strip())) if p else POR_DEFECTO
    except ValueError:
        return POR_DEFECTO


def _digitos(v) -> str:
    return "".join(ch for ch in str(v or "") if ch.isdigit())


# ----------------------------------------------------------------------------------- liquidable
def faltantes(db: Session, s: m.PPSolicitud) -> list[str]:
    """Lo que le falta a la solicitud para poder liquidarse. Vacío = liquidable."""
    falta = []
    cli = db.get(models.Cliente, s.cliente_id) if (s.solicitante_tipo == "REGISTRADO" and s.cliente_id) else None
    if cli is None:
        falta.append("Cliente en el padrón")
    if not _digitos(cli.cuil if cli else (s.cliente_datos or {}).get("cuil")):
        falta.append("CUIL")
    cbu = _digitos((s.datos_adicionales or {}).get("cbu")) or _digitos(getattr(cli, "cbu", ""))
    if len(cbu) != 22:
        falta.append("CBU de acreditación (22 dígitos)")
    return falta


def _contrato_pendiente(db: Session, s: m.PPSolicitud) -> m.PPContrato | None:
    """El contrato A_LIQUIDAR de una solicitud ya originada (circuito anterior)."""
    if s.estado != "ORIGINADA" or not s.contrato_id:
        return None
    c = db.get(m.PPContrato, s.contrato_id)
    return c if c is not None and c.estado == "A_LIQUIDAR" else None


# ----------------------------------------------------------------------------------- lotes
def _proximo_numero(db: Session, anio: int) -> int:
    ultimo = db.query(func.max(m.PPLoteLiquidacion.numero)).filter(m.PPLoteLiquidacion.anio == anio).scalar()
    return (ultimo or 0) + 1


def _ultimo(db: Session, producto_id: str, fecha: date, lock: bool = True) -> m.PPLoteLiquidacion | None:
    q = (db.query(m.PPLoteLiquidacion)
         .filter(m.PPLoteLiquidacion.producto_id == producto_id, m.PPLoteLiquidacion.fecha == fecha)
         .order_by(m.PPLoteLiquidacion.orden.desc()))
    return (q.with_for_update() if lock else q).first()


def _abrir(db: Session, producto_id: str, fecha: date, intentos: int = 10) -> m.PPLoteLiquidacion:
    """Abre el siguiente lote de ese producto y fecha (no hace commit)."""
    ultimo_error: IntegrityError | None = None
    for _ in range(max(1, intentos)):
        ultimo = _ultimo(db, producto_id, fecha)
        try:
            with db.begin_nested():
                lote = m.PPLoteLiquidacion(anio=fecha.year, numero=_proximo_numero(db, fecha.year),
                                           producto_id=producto_id, fecha=fecha, estado=ABIERTO,
                                           orden=(ultimo.orden + 1) if ultimo else 1)
                db.add(lote)
                db.flush()
            return lote
        except IntegrityError as e:     # otro abrió ese lote o tomó ese número → releer y reintentar
            ultimo_error = e
    assert ultimo_error is not None
    raise ultimo_error


def _items_q(db: Session, lote_id: int):
    sols = db.query(m.PPSolicitud).filter(m.PPSolicitud.lote_liquidacion_id == lote_id)
    con_solicitud = db.query(m.PPSolicitud.contrato_id).filter(m.PPSolicitud.contrato_id.isnot(None))
    sueltos = db.query(m.PPContrato).filter(m.PPContrato.lote_liquidacion_id == lote_id,
                                           m.PPContrato.id.notin_(con_solicitud))
    return sols, sueltos


def ocupados(db: Session, lote_id: int) -> int:
    sols, sueltos = _items_q(db, lote_id)
    return sols.count() + sueltos.count()


def importe(db: Session, lote_id: int) -> Decimal:
    sols, sueltos = _items_q(db, lote_id)
    return (sum((s.monto_solicitado or Decimal(0) for s in sols.all()), Decimal(0))
            + sum((c.monto_original or Decimal(0) for c in sueltos.all()), Decimal(0)))


def _tomar(db: Session, producto_id: str, fecha: date, tope: int) -> m.PPLoteLiquidacion:
    """El lote abierto de ese producto y fecha con lugar; si no hay, abre el siguiente."""
    for _ in range(10):
        ultimo = _ultimo(db, producto_id, fecha)
        if ultimo is not None and ultimo.estado == ABIERTO and ocupados(db, ultimo.id) < tope:
            return ultimo
        try:
            return _abrir(db, producto_id, fecha, intentos=1)
        except IntegrityError:
            continue
    return _abrir(db, producto_id, fecha)


def fecha_de(s: m.PPSolicitud) -> date:
    """Fecha del lote: la de aprobación (las aprobadas antes de guardarla, la de alta)."""
    return s.aprobada_en or (s.creado_en.date() if s.creado_en else date.today())


def asignar(db: Session, s: m.PPSolicitud, tope: int | None = None) -> m.PPLoteLiquidacion | None:
    """Pone la solicitud en su lote si es liquidable (no hace commit). Devuelve el lote o None."""
    if s.lote_liquidacion_id:
        return db.get(m.PPLoteLiquidacion, s.lote_liquidacion_id)
    pendiente = _contrato_pendiente(db, s)
    if s.estado != "APROBADA" and pendiente is None:
        return None
    if s.estado == "APROBADA" and faltantes(db, s):
        return None
    fecha = pendiente.fecha_valor if pendiente is not None else fecha_de(s)
    lote = _tomar(db, s.producto_id, fecha, tope or maximo(db))
    s.lote_liquidacion_id = lote.id
    if pendiente is not None:
        pendiente.lote_liquidacion_id = lote.id
    db.flush()
    return lote


def _asignar_contrato(db: Session, c: m.PPContrato, tope: int) -> None:
    lote = _tomar(db, c.producto_id, c.fecha_valor, tope)
    c.lote_liquidacion_id = lote.id
    db.flush()


def asignar_pendientes(db: Session) -> int:
    """Ubica en su lote las liquidables que todavía no tienen (p. ej. porque recién se completó el
    CBU) y los contratos A_LIQUIDAR sin solicitud ni lote. Idempotente."""
    tope = maximo(db)
    n = 0
    sueltas = (db.query(m.PPSolicitud)
               .filter(m.PPSolicitud.lote_liquidacion_id.is_(None),
                       m.PPSolicitud.estado.in_(("APROBADA", "ORIGINADA")))
               .order_by(m.PPSolicitud.creado_en).all())
    for s in sueltas:
        if asignar(db, s, tope) is not None:
            n += 1
    con_solicitud = db.query(m.PPSolicitud.contrato_id).filter(m.PPSolicitud.contrato_id.isnot(None))
    for c in (db.query(m.PPContrato)
              .filter(m.PPContrato.estado == "A_LIQUIDAR", m.PPContrato.lote_liquidacion_id.is_(None),
                      m.PPContrato.id.notin_(con_solicitud))
              .order_by(m.PPContrato.fecha_valor, m.PPContrato.numero_contrato).all()):
        _asignar_contrato(db, c, tope)
        n += 1
    if n:
        db.commit()
    return n


def quitar(db: Session, s: m.PPSolicitud) -> None:
    """Saca la solicitud de su lote (al anularla). Sólo de un lote ABIERTO."""
    if not s.lote_liquidacion_id:
        return
    lote = db.get(m.PPLoteLiquidacion, s.lote_liquidacion_id)
    if lote is not None and lote.estado != ABIERTO:
        raise HTTPException(409, f"La solicitud está en el lote {lote.codigo}, que ya tiene resolución: "
                                 "no se modifica. Sacala del lote primero.")
    s.lote_liquidacion_id = None


def bloqueada(db: Session, s: m.PPSolicitud) -> m.PPLoteLiquidacion | None:
    """El lote con resolución que congela la solicitud, si lo hay."""
    if not s.lote_liquidacion_id:
        return None
    lote = db.get(m.PPLoteLiquidacion, s.lote_liquidacion_id)
    return lote if lote is not None and lote.estado != ABIERTO else None


# ----------------------------------------------------------------------------------- resolución
def _de_resolucion(db: Session, resolucion_id: int | None, numero: int = 0, anio: int | None = None):
    """Lotes de una resolución: por id, o los migrados (sin id) por número y año."""
    conds = []
    if resolucion_id:
        conds.append(m.PPLoteLiquidacion.resolucion_id == resolucion_id)
    if numero and anio:
        conds.append((m.PPLoteLiquidacion.resolucion_id.is_(None))
                     & (m.PPLoteLiquidacion.resolucion_numero == numero)
                     & (m.PPLoteLiquidacion.resolucion_anio == anio))
    if not conds:
        return db.query(m.PPLoteLiquidacion).filter(False)
    return db.query(m.PPLoteLiquidacion).filter(or_(*conds))


def _sync_solicitudes(db: Session, lote: m.PPLoteLiquidacion) -> None:
    """Las solicitudes del lote publican la resolución que las otorga (la ven Créditos y el portal)."""
    con = lote.estado != ABIERTO and bool(lote.resolucion_numero)
    for s in db.query(m.PPSolicitud).filter(m.PPSolicitud.lote_liquidacion_id == lote.id).all():
        s.en_resolucion = con
        s.numero_resolucion = lote.resolucion_numero if con else 0
        s.lote_resolucion = lote.resolucion_numero if con else 0
        s.fecha_resolucion = lote.resolucion_fecha if con else None


def _copiar(lote: m.PPLoteLiquidacion, r: dict) -> None:
    lote.resolucion_id = r.get("id") or lote.resolucion_id
    lote.resolucion_numero = int(r.get("numero") or 0)
    lote.resolucion_anio = r.get("anio")
    lote.resolucion_numero_oficial = r.get("numero_oficial")
    f = r.get("fecha")
    lote.resolucion_fecha = date.fromisoformat(str(f)[:10]) if f else None
    imp = r.get("importe")
    lote.resolucion_importe = Decimal(str(imp)) if imp is not None else None


def _controlar_importe(total: Decimal, r: dict) -> None:
    tope = Decimal(str(r.get("importe") or 0))
    if total > tope:
        raise HTTPException(409, f"La suma de los lotes (${total:,.2f}) supera el importe de la resolución "
                                 f"(${tope:,.2f}).")


def asignar_resolucion(db: Session, lote_ids: list[int], r: dict) -> list[m.PPLoteLiquidacion]:
    """Despacho asigna la resolución `r` ({id, numero, anio, numero_oficial, fecha, importe}) a lotes."""
    if not lote_ids:
        raise HTTPException(422, "Elegí al menos un lote.")
    lotes = (db.query(m.PPLoteLiquidacion).filter(m.PPLoteLiquidacion.id.in_(lote_ids))
             .with_for_update().all())
    if len(lotes) != len(set(lote_ids)):
        raise HTTPException(404, "Algún lote no existe.")
    otros = [lt for lt in lotes if lt.estado != ABIERTO]
    if otros:
        raise HTTPException(409, "Estos lotes ya tienen resolución: " + ", ".join(lt.codigo for lt in otros) + ".")
    vacios = [lt for lt in lotes if ocupados(db, lt.id) == 0]
    if vacios:
        raise HTTPException(409, "Estos lotes no tienen solicitudes: " + ", ".join(lt.codigo for lt in vacios) + ".")
    ya = _de_resolucion(db, r.get("id"), int(r.get("numero") or 0), r.get("anio")).with_for_update().all()
    total = sum((importe(db, lt.id) for lt in {*lotes, *ya}), Decimal(0))
    _controlar_importe(total, r)
    for lt in {*lotes, *ya}:
        _copiar(lt, r)
        if lt.estado == ABIERTO:
            lt.estado = CON_RESOLUCION
        _sync_solicitudes(db, lt)
    db.commit()
    return lotes


def quitar_resolucion(db: Session, lote_id: int) -> m.PPLoteLiquidacion:
    lote = db.query(m.PPLoteLiquidacion).filter_by(id=lote_id).with_for_update().first()
    if lote is None:
        raise HTTPException(404, "Lote no encontrado.")
    if lote.estado == LIQUIDADO:
        raise HTTPException(409, "El lote ya se liquidó: su resolución no se quita.")
    if lote.estado != CON_RESOLUCION:
        raise HTTPException(409, "El lote no tiene resolución.")
    lote.estado = ABIERTO
    _copiar(lote, {})
    lote.resolucion_id = None
    _sync_solicitudes(db, lote)
    db.commit()
    return lote


def actualizar_resolucion(db: Session, r: dict) -> int:
    """Despacho cambió la resolución (N° oficial, fecha o importe): se actualiza la copia en sus lotes
    y, si bajó el importe, se controla que siga alcanzando. También vincula los lotes migrados."""
    lotes = _de_resolucion(db, r.get("id"), int(r.get("numero") or 0), r.get("anio")).with_for_update().all()
    if not lotes:
        return 0
    _controlar_importe(sum((importe(db, lt.id) for lt in lotes), Decimal(0)), r)
    for lt in lotes:
        _copiar(lt, r)
        _sync_solicitudes(db, lt)
    db.commit()
    return len(lotes)


def total_resolucion(db: Session, resolucion_id: int, numero: int = 0, anio: int | None = None) -> Decimal:
    return sum((importe(db, lt.id) for lt in _de_resolucion(db, resolucion_id, numero, anio).all()), Decimal(0))


# ----------------------------------------------------------------------------------- mover
def mover(db: Session, *, solicitud_id: str | None = None, contrato_id: str | None = None,
          destino_id: int | None = None, nuevo: bool = False) -> m.PPLoteLiquidacion:
    """Saca una solicitud (o un contrato sin solicitud) de su lote y la pone en otro del mismo
    producto y fecha, o en uno nuevo. Controla el tope y el importe de la resolución del destino."""
    if solicitud_id:
        item = db.get(m.PPSolicitud, solicitud_id)
        if item is None:
            raise HTTPException(404, "Solicitud no encontrada.")
        monto = item.monto_solicitado or Decimal(0)
    elif contrato_id:
        item = db.get(m.PPContrato, contrato_id)
        if item is None:
            raise HTTPException(404, "Contrato no encontrado.")
        monto = item.monto_original or Decimal(0)
    else:
        raise HTTPException(422, "Indicá la solicitud a mover.")
    origen = db.get(m.PPLoteLiquidacion, item.lote_liquidacion_id) if item.lote_liquidacion_id else None
    if origen is None:
        raise HTTPException(409, "No está en ningún lote.")
    if origen.estado == LIQUIDADO:
        raise HTTPException(409, f"El lote {origen.codigo} ya se liquidó.")
    contrato = db.get(m.PPContrato, item.contrato_id) if solicitud_id and item.contrato_id else None
    if (contrato is not None and contrato.estado != "A_LIQUIDAR") or \
            (contrato_id and item.estado != "A_LIQUIDAR"):
        raise HTTPException(409, "Ya se liquidó: no se mueve.")

    if nuevo:
        destino = _abrir(db, origen.producto_id, origen.fecha)
    else:
        destino = db.query(m.PPLoteLiquidacion).filter_by(id=destino_id).with_for_update().first()
        if destino is None:
            raise HTTPException(404, "Lote de destino no encontrado.")
        if destino.id == origen.id:
            raise HTTPException(409, "Ya está en ese lote.")
        if (destino.producto_id, destino.fecha) != (origen.producto_id, origen.fecha):
            raise HTTPException(409, "Sólo se mueve a un lote del mismo tipo de crédito y fecha.")
        if destino.estado == LIQUIDADO:
            raise HTTPException(409, f"El lote {destino.codigo} ya se liquidó.")
        if ocupados(db, destino.id) >= maximo(db):
            raise HTTPException(409, f"El lote {destino.codigo} está completo.")
        if destino.estado == CON_RESOLUCION:
            r = {"importe": destino.resolucion_importe or 0}
            total = total_resolucion(db, destino.resolucion_id, destino.resolucion_numero, destino.resolucion_anio)
            mismo = (origen.estado == CON_RESOLUCION and origen.resolucion_id == destino.resolucion_id
                     and origen.resolucion_numero == destino.resolucion_numero)
            _controlar_importe(total + (Decimal(0) if mismo else monto), r)
    item.lote_liquidacion_id = destino.id
    if contrato is not None:
        contrato.lote_liquidacion_id = destino.id
    db.flush()
    _sync_solicitudes(db, destino)
    if solicitud_id and destino.estado == ABIERTO:
        item.en_resolucion, item.numero_resolucion, item.lote_resolucion, item.fecha_resolucion = False, 0, 0, None
    db.commit()
    return destino


# ----------------------------------------------------------------------------------- liquidación
def items(db: Session, lote: m.PPLoteLiquidacion) -> list[tuple[m.PPSolicitud | None, m.PPContrato | None]]:
    sols, sueltos = _items_q(db, lote.id)
    out = [(s, db.get(m.PPContrato, s.contrato_id) if s.contrato_id else None)
           for s in sols.order_by(m.PPSolicitud.numero).all()]
    out += [(None, c) for c in sueltos.order_by(m.PPContrato.numero_contrato).all()]
    return out


def no_liquidables(db: Session, lote: m.PPLoteLiquidacion) -> list[str]:
    """Lo que impide liquidar el lote completo (vacío = se puede)."""
    problemas = []
    for s, c in items(db, lote):
        if s is not None and s.estado == "APROBADA":
            f = faltantes(db, s)
            if f:
                problemas.append(f"{s.numero}: falta {', '.join(f)}")
        elif s is not None and not (c is not None and c.estado in ("A_LIQUIDAR", "ACTIVO")):
            problemas.append(f"{s.numero}: está {s.estado}")
    return problemas


def marcar_liquidado(lote: m.PPLoteLiquidacion) -> None:
    lote.estado = LIQUIDADO
    lote.liquidado_en = datetime.now()


# ----------------------------------------------------------------------------------- migración
def migrar_a_solicitudes(db: Session) -> int:
    """Pasa los lotes de contratos (versión anterior) a lotes de solicitudes. Idempotente.

    Cada contrato A_LIQUIDAR con lote le deja el lote a su solicitud. Un lote que mezcla solicitudes
    de distintas resoluciones (el anexo era solicitud por solicitud) se parte: cada lote queda con
    una sola resolución, y el que tiene resolución pasa a CON_RESOLUCION."""
    cambios = 0
    for c in db.query(m.PPContrato).filter(m.PPContrato.lote_liquidacion_id.isnot(None)).all():
        s = db.query(m.PPSolicitud).filter(m.PPSolicitud.contrato_id == c.id).first()
        if s is not None and s.lote_liquidacion_id is None:
            s.lote_liquidacion_id = c.lote_liquidacion_id
            cambios += 1
    db.flush()
    for lote in db.query(m.PPLoteLiquidacion).filter(m.PPLoteLiquidacion.estado == ABIERTO).all():
        grupos: dict[tuple, list] = {}
        for s, c in items(db, lote):
            clave = ((s.numero_resolucion, s.fecha_resolucion) if (s is not None and s.en_resolucion
                                                                    and s.numero_resolucion) else (0, None))
            grupos.setdefault(clave, []).append((s, c))
        if not any(k[0] for k in grupos):
            continue
        # Se queda en este lote la resolución con más solicitudes; el resto va a lotes nuevos.
        orden = sorted(grupos, key=lambda k: (k[0] == 0, -len(grupos[k])))
        for i, clave in enumerate(orden):
            destino = lote if i == 0 else _abrir(db, lote.producto_id, lote.fecha)
            for s, c in grupos[clave]:
                if s is not None:
                    s.lote_liquidacion_id = destino.id
                if c is not None:
                    c.lote_liquidacion_id = destino.id
            numero, fecha = clave
            if numero:
                destino.estado = CON_RESOLUCION
                destino.resolucion_numero = numero
                destino.resolucion_fecha = fecha
                destino.resolucion_anio = fecha.year if fecha else lote.fecha.year
            cambios += 1
        db.flush()
    if cambios:
        db.commit()
    return cambios
