"""Órdenes de pago de Tesorería (API interna, no pasa por el gateway; clave de Tesorería).

Tesorería arma una orden de pago con una o varias resoluciones / disposiciones de Despacho. Créditos es
el dueño de los lotes, así que acá se decide qué entra:

- `GET  /disponibles`: los actos con lotes CON_RESOLUCION que no están en otra orden.
- `POST /reservar`: los lotes de esos actos entran COMPLETOS a la orden (quedan PARA_LIQUIDAR), se
  originan sus solicitudes aprobadas y se devuelven las transferencias a hacer (una por crédito).
  Todo o nada: si algo no se puede liquidar, ningún lote entra. Reintentar con la misma orden devuelve
  lo mismo (idempotente).
- `POST /liberar`: Tesorería anuló la orden antes de pagar → sus lotes vuelven a CON_RESOLUCION. Los
  contratos ya originados quedan A_LIQUIDAR en su lote y los toma la próxima orden.

El resultado de cada transferencia llega por /internal/creditos/tesoreria/resultado: acreditadas todas
las de un lote, el lote queda LIQUIDADO.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models_productos as m
from app.api.contratos import (_originar_de_solicitud, _pago_de, _set_desembolso, desembolso_info,
                               en_tesoreria, serial_lote)
from app.api.tesoreria_interna import api_tesoreria
from app.core.database import get_db
from app.services import lotes_liquidacion as lotes

router = APIRouter(prefix="/internal/creditos/ordenes-pago", tags=["internal"],
                   dependencies=[Depends(api_tesoreria)])


def _clave(lt: m.PPLoteLiquidacion) -> str:
    k = lotes.clave_acto(lt)
    return f"id:{k[1]}" if k[0] == "id" else f"num:{k[1]}:{k[2]}"


def _acto(lt: m.PPLoteLiquidacion) -> dict:
    return {"clave": _clave(lt), "id": lt.resolucion_id, "tipo": lt.resolucion_tipo or "RES",
            "numero": lt.resolucion_numero, "anio": lt.resolucion_anio,
            "numeroOficial": lt.resolucion_numero_oficial,
            "fecha": str(lt.resolucion_fecha) if lt.resolucion_fecha else None,
            "importe": float(lt.resolucion_importe) if lt.resolucion_importe is not None else None}


def _agrupar(db: Session, registros: list[m.PPLoteLiquidacion]) -> list[dict]:
    nombres = dict(db.query(m.PPProducto.id, m.PPProducto.nombre).all())
    tope = lotes.maximo(db)
    grupos: dict[str, dict] = {}
    for lt in registros:
        g = grupos.setdefault(_clave(lt), {"acto": _acto(lt), "lotes": [], "cantidad": 0, "total": 0.0})
        s = serial_lote(db, lt, nombres, set(), tope, detalle=False)
        if not s["cantidad"]:
            continue
        g["lotes"].append(s)
        g["cantidad"] += s["cantidad"]
        g["total"] += s["montoTotal"]
    return [g for g in grupos.values() if g["lotes"]]


@router.get("/disponibles")
def disponibles(db: Session = Depends(get_db)):
    """Resoluciones / disposiciones con lotes que todavía no están en ninguna orden de pago."""
    lotes.asignar_pendientes(db)
    return {"items": _agrupar(db, lotes.lotes_sin_orden(db))}


class ReservarIn(BaseModel):
    orden_id: int
    codigo: str = Field(min_length=1, max_length=20)
    usuario: str = "tesoreria"
    actos: list[str] = Field(min_length=1)       # claves de /disponibles


class LiberarIn(BaseModel):
    orden_id: int


def _transferencias(db: Session, registros: list[m.PPLoteLiquidacion], codigo: str) -> dict:
    pagos, total = [], Decimal(0)
    for lt in registros:
        for _s, c in lotes.items(db, lt):
            if c is None:
                continue
            pago, _motivo = _pago_de(db, c)
            if pago is not None:
                pago["concepto"] = f"{codigo} lote {lt.codigo} {pago['concepto']}"[:120]
                pagos.append({**pago, "lote": lt.codigo})
                total += Decimal(str(pago["monto"]))
    return {"pagos": pagos, "lotes": [lt.codigo for lt in registros], "total": float(total),
            "actos": _agrupar(db, registros)}


def _devolver(db: Session, orden_id: int) -> None:
    """Deshace una reserva que no se completó: los lotes vuelven a CON_RESOLUCION."""
    db.rollback()
    for lt in lotes.de_orden(db, orden_id, lock=True):
        if lt.estado == lotes.PARA_LIQUIDAR:
            lotes.sacar_de_orden(lt)
    db.commit()


@router.post("/reservar")
def reservar(data: ReservarIn, db: Session = Depends(get_db)):
    ya = lotes.de_orden(db, data.orden_id)
    if ya:                                        # reintento de la misma orden: lo mismo de antes
        return _transferencias(db, ya, data.codigo)

    pedidos = set(data.actos)
    elegidos = [lt for lt in lotes.lotes_sin_orden(db) if _clave(lt) in pedidos and lotes.ocupados(db, lt.id)]
    faltan = pedidos - {_clave(lt) for lt in elegidos}
    if faltan:
        raise HTTPException(409, "Estas resoluciones / disposiciones ya no tienen lotes disponibles (están en "
                                 "otra orden de pago o se les quitó la resolución): " + ", ".join(sorted(faltan)) + ".")
    sin_oficial = sorted({f"{lt.resolucion_numero}/{lt.resolucion_anio}" for lt in elegidos
                          if not lt.resolucion_numero_oficial})
    if sin_oficial:
        raise HTTPException(409, "Todavía no tienen N° oficial (no se pagan en borrador): correlativo "
                                 + ", ".join(sin_oficial) + ".")
    problemas = [f"Lote {lt.codigo} · {p}" for lt in elegidos for p in lotes.no_liquidables(db, lt)]
    problemas += [f"Lote {lt.codigo} · contrato {c.numero_contrato}: ya está en Tesorería ({desembolso_info(c).get('lote')})"
                  for lt in elegidos for _s, c in lotes.items(db, lt) if c is not None and en_tesoreria(c)]
    if problemas:
        raise HTTPException(409, "La orden de pago no se puede armar completa. " + "; ".join(problemas))

    # Los lotes se toman primero (UPDATE condicionado): dos órdenes a la vez no se llevan el mismo lote.
    for lt in elegidos:
        tomado = (db.query(m.PPLoteLiquidacion)
                  .filter(m.PPLoteLiquidacion.id == lt.id, m.PPLoteLiquidacion.estado == lotes.CON_RESOLUCION,
                          m.PPLoteLiquidacion.orden_pago_id.is_(None))
                  .update({"orden_pago_id": data.orden_id, "orden_pago_codigo": data.codigo,
                           "estado": lotes.PARA_LIQUIDAR}, synchronize_session=False))
        if not tomado:
            _devolver(db, data.orden_id)
            raise HTTPException(409, f"El lote {lt.codigo} acaba de entrar en otra orden de pago. Refrescá.")
    db.commit()

    usuario = SimpleNamespace(username=data.usuario[:60], perfil="TESORERIA")
    errores = []
    registros = lotes.de_orden(db, data.orden_id)
    for lt in registros:
        for s, _c in lotes.items(db, lt):
            if s is not None and s.estado == "APROBADA":
                try:
                    _originar_de_solicitud(db, s, usuario)
                except HTTPException as e:
                    db.rollback(); errores.append(f"{s.numero}: {e.detail}")
    if errores:
        _devolver(db, data.orden_id)
        raise HTTPException(409, "No se pudieron originar: " + "; ".join(errores))

    registros = lotes.de_orden(db, data.orden_id, lock=True)
    out = _transferencias(db, registros, data.codigo)
    con_pago = {p["referencia_externa"]: p["monto"] for p in out["pagos"]}
    sin_pago = [c.numero_contrato for lt in registros for _s, c in lotes.items(db, lt)
                if c is not None and c.id not in con_pago]
    if sin_pago:
        _devolver(db, data.orden_id)
        raise HTTPException(409, "Sin CBU de acreditación válido: " + ", ".join(sin_pago) + ".")
    for lt in registros:
        lt.para_liquidar_en = lt.para_liquidar_en or datetime.now()
        for _s, c in lotes.items(db, lt):
            _set_desembolso(c, estado="EN_TESORERIA", lote=None, orden_pago=data.codigo, motivo="",
                            monto=con_pago[c.id], enviado_por=usuario.username)
    db.commit()
    return out


@router.post("/liberar")
def liberar(data: LiberarIn, db: Session = Depends(get_db)):
    registros = lotes.de_orden(db, data.orden_id, lock=True)
    pagados = [lt.codigo for lt in registros if lt.estado == lotes.LIQUIDADO
               or any(c is not None and c.estado == "ACTIVO" for _s, c in lotes.items(db, lt))]
    if pagados:
        db.rollback()
        raise HTTPException(409, "Ya hay créditos acreditados en los lotes " + ", ".join(pagados)
                                 + ": la orden de pago no se anula.")
    for lt in registros:
        codigo = lt.orden_pago_codigo
        for _s, c in lotes.items(db, lt):
            if c is not None and desembolso_info(c).get("orden_pago") == codigo:
                c.datos_adicionales = {**(c.datos_adicionales or {}), "desembolso": {}}
        lotes.sacar_de_orden(lt)
    db.commit()
    return {"lotes": [lt.codigo for lt in registros]}
