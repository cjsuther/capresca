"""Procesos y versiones del workflow gráfico (fase 1): borrador, publicación, retiro y migración.

Convivencia con el motor actual: la versión PUBLICADA se proyecta sobre la regla vieja
(`workflow_reglas` + niveles + excepciones), que es lo que sigue leyendo la API interna. Por eso sólo
se publica un grafo que el motor actual sabe ejecutar (`wf_grafo.proyectar`): aprobaciones en serie
por rol. Los borradores pueden usar todo (decisiones, notificaciones, grupos) y se validan igual.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.models import WF_BORRADOR, WF_PUBLICADA, WF_RETIRADA
from app.services import auditoria_central as central
from app.services import wf_grafo as g
from app.services.workflow import VARIABLES, serial_regla

SISTEMA = "sistema"


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)   # columnas sin zona, en UTC


def variables(p: models.WfProceso) -> dict:
    return VARIABLES.get((p.modulo, p.objeto), {})


def publicada(p: models.WfProceso) -> models.WfVersion | None:
    return next((v for v in p.versiones if v.estado == WF_PUBLICADA), None)


def borrador(p: models.WfProceso) -> models.WfVersion | None:
    return next((v for v in p.versiones if v.estado == WF_BORRADOR), None)


def regla_de(db: Session, p: models.WfProceso) -> models.WorkflowRegla | None:
    return db.query(models.WorkflowRegla).filter_by(modulo=p.modulo, objeto=p.objeto).first()


def _niveles_regla(r: models.WorkflowRegla) -> list[dict] | None:
    """La regla pasada por el mismo camino que una versión (regla → grafo → proyección): así se compara
    con la proyección de la publicada sin falsos cambios (nombres vacíos, orden de usuarios…)."""
    return g.proyectar(g.grafo_desde_niveles(serial_regla(r)["niveles"])[0])[0]


# ── Migración / sincronización desde las reglas viejas ──────────────────────────────────────────
def sincronizar_procesos(db: Session) -> int:
    """Cada regla vieja tiene su proceso con una versión PUBLICADA equivalente. Idempotente:
      - regla sin proceso → proceso + versión 1 PUBLICADA (migración automática);
      - regla cuyos niveles ya no coinciden con la publicada (p.ej. la cambió el import interno del ETL
        de Créditos) → nueva versión PUBLICADA tomada de la regla, para que el editor muestre la verdad;
      - `habilitado` copia a `activo` de la regla.
    No borra ni modifica las reglas viejas. Devuelve cuántas versiones creó."""
    creadas = 0
    for r in db.query(models.WorkflowRegla).order_by(models.WorkflowRegla.id).all():
        p = db.query(models.WfProceso).filter_by(modulo=r.modulo, objeto=r.objeto).first()
        if p is None:
            p = models.WfProceso(modulo=r.modulo, objeto=r.objeto, nombre=r.nombre, descripcion=r.descripcion,
                                 habilitado=r.activo)
            db.add(p)
            db.flush()
            nota = "Migrada automáticamente desde la regla en serie."
        else:
            p.habilitado = r.activo
            pub = publicada(p)
            if pub is not None:
                niveles, _ = g.proyectar(pub.grafo)
                if niveles == _niveles_regla(r):
                    continue
            elif any(v.estado == WF_RETIRADA for v in p.versiones) and not r.activo:
                continue                 # se retiró a propósito: no se vuelve a publicar sola
            nota = "Tomada de la regla en serie (cambió fuera del editor)."
        _publicar_desde_regla(db, p, r, nota)
        creadas += 1
    db.commit()
    return creadas


def _publicar_desde_regla(db: Session, p: models.WfProceso, r: models.WorkflowRegla, nota: str) -> None:
    grafo, layout = g.grafo_desde_niveles(serial_regla(r)["niveles"])
    anterior = publicada(p)
    if anterior is not None:
        anterior.estado, anterior.retirada_por, anterior.retirada_en = WF_RETIRADA, SISTEMA, _ahora()
        db.flush()
    numero = max((v.numero for v in p.versiones), default=0) + 1
    v = models.WfVersion(proceso=p, numero=numero, estado=WF_PUBLICADA, grafo=grafo, layout=layout,
                         huella=g.huella(grafo), nota=nota, creada_por=SISTEMA, publicada_por=SISTEMA,
                         publicada_en=_ahora(),
                         diff_resumen="\n".join(g.comparar(anterior.grafo, grafo)["resumen"]) if anterior else "")
    db.add(v)
    db.flush()


# ── Borradores ───────────────────────────────────────────────────────────────────────────────────
def crear_borrador(db: Session, p: models.WfProceso, usuario: str, desde: int | None = None) -> models.WfVersion:
    if borrador(p):
        raise HTTPException(409, "Ya hay un borrador de este proceso: seguí editando ese o descartalo.")
    if desde is not None:
        base = next((v for v in p.versiones if v.numero == desde), None)
        if base is None:
            raise HTTPException(404, f"No existe la versión {desde}.")
    else:
        base = publicada(p) or (p.versiones[-1] if p.versiones else None)
    if base is not None:
        grafo, layout = base.grafo, base.layout
    else:
        grafo, layout = g.grafo_desde_niveles([{"orden": 1, "nombre": "Aprobación", "rol": "APROBAR"}])
    v = models.WfVersion(proceso=p, numero=max((x.numero for x in p.versiones), default=0) + 1,
                         estado=WF_BORRADOR, grafo=grafo, layout=layout, huella=g.huella(grafo),
                         basada_en=base.numero if base else None, creada_por=usuario)
    db.add(v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Otro usuario acaba de crear un borrador de este proceso. Refrescá.")
    return v


def guardar_borrador(db: Session, v: models.WfVersion, grafo: dict, layout: dict, nota: str | None,
                     revision: int, usuario: str) -> models.WfVersion:
    if v.estado != WF_BORRADOR:
        raise HTTPException(409, "Sólo se edita un borrador: una versión publicada no cambia nunca.")
    if revision != v.revision:
        raise HTTPException(409, "Otro usuario guardó este borrador mientras lo editabas. Recargá para ver "
                                 "sus cambios.")
    try:
        limpio = g.normalizar(grafo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    v.grafo, v.layout, v.huella = limpio, g.normalizar_layout(layout, limpio), g.huella(limpio)
    if nota is not None:
        v.nota = nota.strip()[:300]
    v.revision += 1
    v.modificada_por, v.modificada_en = usuario, _ahora()
    return v


def descartar_borrador(db: Session, v: models.WfVersion) -> None:
    if v.estado != WF_BORRADOR:
        raise HTTPException(409, "Sólo se descarta un borrador.")
    v.proceso.versiones.remove(v)
    db.delete(v)


# ── Publicación ──
def _bloquear(db: Session, v: models.WfVersion) -> models.WfProceso:
    """Serializa publicar/retirar de un mismo proceso (SELECT … FOR UPDATE en Postgres) y relee la
    versión y la lista de versiones DESPUÉS de tomar el lock: lo leído antes puede estar viejo."""
    p = db.query(models.WfProceso).filter_by(id=v.proceso_id).with_for_update().populate_existing().one()
    db.refresh(v)
    db.expire(p, ["versiones"])
    return p


# ── Publicación ──────────────────────────────────────────────────────────────────────────────────
def publicar(db: Session, v: models.WfVersion, usuario: str, nota: str | None = None) -> models.WfVersion:
    p = _bloquear(db, v)
    if v.estado != WF_BORRADOR:
        raise HTTPException(409, "Sólo se publica un borrador (¿otro usuario acaba de publicarlo?).")
    errs = g.errores(g.validar(v.grafo, variables(p)))
    if errs:
        raise HTTPException(422, {"mensaje": "El workflow tiene errores: corregilos antes de publicar.",
                                  "problemas": errs})
    niveles, motivos = g.proyectar(v.grafo)
    if niveles is None:
        raise HTTPException(409, {"mensaje": "Esta versión todavía no se puede publicar: Créditos y Tesorería "
                                             "ejecutan sólo aprobaciones en serie por rol (el motor nuevo llega "
                                             "en la fase 3).", "problemas": motivos})
    anterior = publicada(p)
    if anterior is not None and anterior.huella == g.huella(v.grafo):
        raise HTTPException(409, "No hay cambios respecto de la versión publicada.")
    regla = regla_de(db, p)
    if regla is None:
        raise HTTPException(409, "El proceso no tiene regla en el catálogo: no se puede publicar.")

    diff = g.comparar(anterior.grafo, v.grafo) if anterior else None
    if anterior is not None:
        anterior.estado, anterior.retirada_por, anterior.retirada_en = WF_RETIRADA, usuario, _ahora()
        db.flush()
    v.estado, v.publicada_por, v.publicada_en = WF_PUBLICADA, usuario, _ahora()
    v.diff_resumen = "\n".join(diff["resumen"]) if diff else ""
    if nota is not None and nota.strip():
        v.nota = nota.strip()[:300]
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Otro usuario acaba de publicar una versión de este proceso. Refrescá.")
    proyectar_en_regla(db, regla, niveles)
    central.registrar(usuario=usuario, operacion="ACCION", entidad="WorkflowVersion", entidad_id=str(v.id),
                      descripcion=f"Publica la versión {v.numero} del workflow {p.modulo}/{p.objeto}",
                      detalle=v.diff_resumen or "Primera versión publicada",
                      cambios={"version": v.numero, "anterior": anterior.numero if anterior else None,
                               "huella": v.huella})
    return v


def proyectar_en_regla(db: Session, r: models.WorkflowRegla, niveles: list[dict]) -> None:
    """Escribe los niveles en la regla vieja EN EL LUGAR: lo que no cambia conserva su id (la API interna
    devuelve exactamente lo mismo si la versión es equivalente)."""
    existentes = {n.orden: n for n in r.niveles}
    for nv in niveles:
        n = existentes.get(nv["orden"])
        if n is None:
            n = models.WorkflowNivel(orden=nv["orden"])
            r.niveles.append(n)
        if (n.nombre, n.rol, n.cuatro_ojos) != (nv["nombre"], nv["rol"], nv["cuatroOjos"]):
            n.nombre, n.rol, n.cuatro_ojos = nv["nombre"], nv["rol"], nv["cuatroOjos"]
        quiero = {u["username"]: u["modo"] for u in nv["usuarios"]}
        for u in list(n.usuarios):
            if u.username not in quiero:
                n.usuarios.remove(u)
            elif u.modo != quiero[u.username]:
                u.modo = quiero[u.username]
        tengo = {u.username for u in n.usuarios}
        for username, modo in quiero.items():
            if username not in tengo:
                n.usuarios.append(models.WorkflowNivelUsuario(username=username, modo=modo))
    for orden, n in existentes.items():
        if orden > len(niveles):
            r.niveles.remove(n)
    db.flush()


def retirar(db: Session, v: models.WfVersion, usuario: str) -> models.WfVersion:
    """Retira la versión publicada sin reemplazo: el proceso queda sin workflow vigente, o sea
    DESHABILITADO (deja de exigirse la aprobación, como desactivar la regla vieja)."""
    p = _bloquear(db, v)
    if v.estado != WF_PUBLICADA:
        raise HTTPException(409, "Sólo se retira la versión publicada.")
    v.estado, v.retirada_por, v.retirada_en = WF_RETIRADA, usuario, _ahora()
    p.habilitado = False
    regla = regla_de(db, p)
    if regla is not None:
        regla.activo = False
    central.registrar(usuario=usuario, operacion="ACCION", entidad="WorkflowVersion", entidad_id=str(v.id),
                      descripcion=f"Retira la versión {v.numero} del workflow {p.modulo}/{p.objeto} "
                                  "(queda deshabilitado)")
    return v


def habilitar(db: Session, p: models.WfProceso, valor: bool, usuario: str) -> models.WfProceso:
    if valor and publicada(p) is None:
        raise HTTPException(409, "Para habilitar el proceso primero publicá una versión.")
    p.habilitado = valor
    regla = regla_de(db, p)
    if regla is not None:
        regla.activo = valor
    central.registrar(usuario=usuario, operacion="ACCION", entidad="WorkflowProceso", entidad_id=str(p.id),
                      descripcion=f"{'Habilita' if valor else 'Deshabilita'} el workflow {p.modulo}/{p.objeto}")
    return p


# ── Serialización ────────────────────────────────────────────────────────────────────────────────
def _f(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def serial_version_resumen(v: models.WfVersion) -> dict:
    return {"id": v.id, "numero": v.numero, "estado": v.estado, "nota": v.nota, "basadaEn": v.basada_en,
            "creadaPor": v.creada_por, "creadaEn": _f(v.creada_en), "modificadaPor": v.modificada_por,
            "modificadaEn": _f(v.modificada_en), "publicadaPor": v.publicada_por, "publicadaEn": _f(v.publicada_en),
            "retiradaPor": v.retirada_por, "retiradaEn": _f(v.retirada_en), "diffResumen": v.diff_resumen}


def serial_version(v: models.WfVersion) -> dict:
    p = v.proceso
    problemas = g.validar(v.grafo, variables(p))
    niveles, motivos = g.proyectar(v.grafo)
    return {**serial_version_resumen(v), "procesoId": p.id, "grafo": v.grafo, "layout": v.layout,
            "revision": v.revision, "huella": v.huella, "problemas": problemas,
            "compatibleMotorActual": niveles is not None, "motivosIncompatible": motivos}


def serial_proceso(p: models.WfProceso, con_versiones: bool = False) -> dict:
    pub, bor = publicada(p), borrador(p)
    d = {"id": p.id, "modulo": p.modulo, "objeto": p.objeto, "nombre": p.nombre, "descripcion": p.descripcion,
         "habilitado": p.habilitado,
         "publicada": serial_version_resumen(pub) if pub else None,
         "borrador": serial_version_resumen(bor) if bor else None,
         "variables": variables(p)}
    if con_versiones:
        d["versiones"] = [serial_version_resumen(v) for v in sorted(p.versiones, key=lambda x: -x.numero)]
    return d
