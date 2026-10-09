"""Espera después de un rechazo: quien tuvo una solicitud rechazada no puede pedir otra desde el
portal hasta que pasen N días (parámetro PORTAL_ESPERA_RECHAZO_DIAS, Créditos → Parámetros).

"La misma persona" es la misma cuenta del portal o el mismo CUIL (así no se esquiva con otra cuenta,
y cuenta también un rechazo de una solicitud cargada en sucursal). Sin el parámetro cargado son 30
días; en 0 la regla no aplica. El plazo corre desde el día del rechazo (o, en las rechazadas antes de
que se guardara esa fecha, desde el alta de la solicitud).
"""
from __future__ import annotations

from datetime import date, timedelta

from app import models, models_productos as m

PARAMETRO = "PORTAL_ESPERA_RECHAZO_DIAS"
POR_DEFECTO = 30


def dias(db) -> int:
    p = db.query(models.Parametro).filter(models.Parametro.clave == PARAMETRO).first()
    if p is None:
        return POR_DEFECTO
    try:
        return max(0, int(str(p.valor).strip() or 0))
    except ValueError:
        return POR_DEFECTO


def fecha_rechazo(s: m.PPSolicitud) -> date:
    f = (s.datos_adicionales or {}).get("rechazada_en")
    if f:
        return date.fromisoformat(str(f)[:10])
    return s.creado_en.date() if s.creado_en else date.today()


def _cuil_de(db, s: m.PPSolicitud) -> str:
    if s.cliente_id:
        cli = db.get(models.Cliente, s.cliente_id)
        if cli and cli.cuil:
            return "".join(ch for ch in cli.cuil if ch.isdigit())
    return "".join(ch for ch in str((s.cliente_datos or {}).get("cuil") or "") if ch.isdigit())


def bloqueo(db, marca: str, cuil: str = "", hoy: date | None = None) -> dict | None:
    """El rechazo que todavía frena una solicitud nueva, o None. {numero, rechazada, hasta}"""
    n = dias(db)
    if n <= 0:
        return None
    hoy = hoy or date.today()
    cuil = "".join(ch for ch in (cuil or "") if ch.isdigit())
    vigente = None
    for s in db.query(m.PPSolicitud).filter(m.PPSolicitud.estado == "RECHAZADA").all():
        if not (s.creado_por == marca or (cuil and _cuil_de(db, s) == cuil)):
            continue
        rechazada = fecha_rechazo(s)
        hasta = rechazada + timedelta(days=n)
        if hasta > hoy and (vigente is None or hasta > vigente["hasta"]):
            vigente = {"numero": s.numero, "rechazada": rechazada, "hasta": hasta}
    return vigente


def mensaje(b: dict) -> str:
    return (f"Tu solicitud {b['numero']} fue rechazada el {b['rechazada']:%d/%m/%Y}. "
            f"Podés volver a solicitar un crédito desde el {b['hasta']:%d/%m/%Y}.")
