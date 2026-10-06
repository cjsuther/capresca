"""Lotes de créditos y su resolución: el vínculo entre Despacho y Créditos.

Créditos arma los lotes solo (solicitudes aprobadas y liquidables, por tipo de crédito y fecha) y
manda sobre ellos. Despacho los ve y les asigna la resolución que los otorga: una misma resolución
puede alcanzar varios lotes, sin que la suma de sus importes pase el importe de la resolución
(lo controla Créditos, que tiene los importes de los lotes).

Despacho pone la regla del instrumento: no se asignan lotes a un acto anulado o ya emitido (con N°
oficial o firmado), ni se quita un lote de un acto emitido. El anexo impreso de la resolución lista
las solicitudes de sus lotes.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, Resolucion
from app.services import creditos_central


def resolucion_dict(r: Resolucion) -> dict:
    """Lo que Créditos guarda de la resolución en sus lotes."""
    return {"id": r.id, "numero": r.numero, "anio": r.anio, "numero_oficial": r.numero_real,
            "fecha": r.fecha.isoformat() if r.fecha else None, "importe": str(r.importe or 0)}


def _resumen(r: Resolucion | None) -> dict | None:
    if r is None:
        return None
    return {"id": r.id, "numero": r.numero, "anio": r.anio, "numero_real": r.numero_real,
            "fecha": r.fecha, "importe": r.importe, "anulada": r.anulada, "oficial": r.oficial,
            "motivo": r.motivo or r.asunto}


def _local(db: Session, res: dict | None) -> Resolucion | None:
    """La resolución de Despacho que corresponde a lo que informa Créditos para un lote."""
    if not res:
        return None
    if res.get("id"):
        r = db.get(Resolucion, res["id"])
        if r is not None:
            return r
    if res.get("numero") and res.get("anio"):
        # Lotes migrados del anexo anterior: se conocían por número (serie general) y año.
        return db.scalar(select(Resolucion).where(Resolucion.numero == res["numero"],
                                                  Resolucion.anio == res["anio"],
                                                  Resolucion.serie == SERIE_POR_DEFECTO))
    return None


def tipos() -> list[dict]:
    return [{"tipo": "", "nombre": "Todos los tipos"}] + creditos_central.tipos()


def listar(db: Session, *, estado: str | None = None, tipo: str | None = None) -> dict:
    d = creditos_central.lotes(estado=estado or None, producto_id=tipo or None)
    vinculadas: set[int] = set()
    for lt in d.get("items", []):
        r = _local(db, lt.get("resolucion"))
        # Un lote migrado todavía no conoce el id de su resolución: se lo informa una vez.
        if r is not None and not (lt.get("resolucion") or {}).get("id") and r.id not in vinculadas:
            creditos_central.resolucion_actualizada(resolucion_dict(r))
            vinculadas.add(r.id)
        lt["resolucion_despacho"] = _resumen(r)
    return d


def ver(db: Session, lote_id: int) -> dict:
    lt = creditos_central.lote(lote_id)
    lt["resolucion_despacho"] = _resumen(_local(db, lt.get("resolucion")))
    return lt


def comprometido(r: Resolucion) -> dict:
    """Cuánto de la resolución ya está tomado por sus lotes, y cuánto queda."""
    d = creditos_central.lotes(resolucion_id=r.id, numero=r.numero, anio=r.anio)
    total = Decimal(str(d.get("total") or 0))
    importe = Decimal(str(r.importe or 0))
    return {"lotes": d.get("items", []), "total": total, "importe": importe, "disponible": importe - total}


def _resolucion_para_lotes(db: Session, resolucion_id: int) -> Resolucion:
    r = db.get(Resolucion, resolucion_id)
    if r is None:
        raise HTTPException(404, "Resolución no encontrada")
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada.")
    if r.oficial:
        raise HTTPException(422, "El instrumento ya fue emitido (firmado o con N° oficial): no se le "
                                 "agregan lotes.")
    if not r.importe or r.importe <= 0:
        raise HTTPException(422, "Cargá el importe de la resolución: es el tope de los lotes que otorga.")
    return r


def asignar(db: Session, *, resolucion_id: int, lote_ids: list[int]) -> dict:
    """Asigna la resolución a los lotes elegidos (Créditos controla el importe)."""
    if not lote_ids:
        raise HTTPException(422, "Elegí al menos un lote.")
    r = _resolucion_para_lotes(db, resolucion_id)
    d = creditos_central.asignar_resolucion(lote_ids, resolucion_dict(r))
    total = Decimal(str(d.get("totalResolucion") or 0))
    return {"resolucion_id": r.id, "numero": r.numero, "anio": r.anio, "asignados": d.get("asignados", []),
            "total": total, "importe": r.importe, "disponible": (r.importe or Decimal(0)) - total}


def quitar(db: Session, lote_id: int) -> dict:
    """Le quita la resolución a un lote (mientras el acto no esté emitido y el lote no se liquidó)."""
    lt = creditos_central.lote(lote_id)
    r = _local(db, lt.get("resolucion"))
    if r is not None and r.oficial and not r.anulada:
        raise HTTPException(422, "El instrumento ya fue emitido: no se le saca ningún lote.")
    return creditos_central.quitar_resolucion(lote_id)


def filas_anexo(r: Resolucion) -> list[dict]:
    """Las solicitudes que otorga la resolución: las de sus lotes."""
    return creditos_central.solicitudes_de_resolucion(r.id, r.numero, r.anio).get("items", [])


def notificar(r: Resolucion) -> None:
    """Créditos actualiza su copia de la resolución (y rechaza un importe que no alcance)."""
    if creditos_central.habilitado():
        creditos_central.resolucion_actualizada(resolucion_dict(r))
