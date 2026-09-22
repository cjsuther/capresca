"""Inbox de aprobaciones (cuatro-ojos).

Reúne, para el usuario actual, las tareas que esperan SU aprobación en los flujos con separación de
funciones: versiones de línea EN_REVISION (a aprobar) o APROBADA (a publicar), y solicitudes de
crédito EN_EVALUACION (a resolver). Excluye lo que el propio usuario envió (no puede aprobar lo suyo).

Alimenta también el badge de alertas del sistema (cuántas tareas hay pendientes).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.services import auditoria as audit
from app import models, models_productos as m
from app.api.productos import _caps

# Las tareas enlazan a la pantalla del módulo Créditos dentro del frontend de Portezuelo.
RUTA_FRONT = "/modules/creditos"

router = APIRouter(prefix="/api/creditos/aprobaciones", tags=["aprobaciones"])


def _paso_actual(db: Session, objeto: str, objeto_id: str, user: models.Usuario, emisor: str | None):
    """Si `user` puede aprobar el nivel PENDIENTE de este objeto (cadena N-niveles), devuelve
    (orden, total, actores); si no, None. Respeta rol + overrides + cuatro-ojos."""
    from app.services import workflow as wf
    r = wf.regla(db, objeto)
    if r is None or not r.activo:                 # sin regla activa: sólo un aprobador (ADMG) por defecto
        return (1, 1, set()) if _caps(db, user)["aprueba"] else None
    prog = wf.progreso(db, objeto, objeto_id)
    orden = prog["nivelActual"]
    actores = set(prog["actores"]) | ({emisor} if emisor else set())
    ok, _st, _m = wf.puede_aprobar(db, objeto, user, actores=actores, orden=orden)
    return (orden, prog["total"], actores) if ok else None


def _inbox(db: Session, user: models.Usuario) -> list[dict]:
    """Tareas pendientes de aprobación para `user`: cada objeto en su nivel actual, mostrado sólo a
    los aprobadores elegibles de ese nivel (rol + overrides + cuatro-ojos)."""
    yo = user.username
    tareas: list[dict] = []

    # --- Versiones de línea de crédito ---
    for v in (db.query(m.PPVersion).filter(m.PPVersion.estado.in_(("EN_REVISION", "APROBADO")))
              .order_by(m.PPVersion.creado_en.desc()).all()):
        prod = db.get(m.PPProducto, v.producto_id)
        if not prod:
            continue
        if v.estado == "EN_REVISION":
            paso = _paso_actual(db, "LINEA", v.id, user, v.enviado_por)
            if not paso:
                continue
            orden, total, _ = paso
            accion = "aprobar"
            detalle = f"Nivel {orden} de {total} — espera tu aprobación" if total > 1 else "Enviada a revisión — espera aprobación"
            solicitante = v.enviado_por or "—"
        else:                              # APROBADO → falta publicar (acción final del aprobador ADMG)
            if not _caps(db, user)["aprueba"]:
                continue
            solicitante = v.aprobado_por or v.enviado_por or "—"
            if solicitante == yo:
                continue
            accion, orden, total, detalle = "publicar", 0, 0, "Aprobada — espera publicación"
        tareas.append({
            "tipo": "LINEA", "id": prod.id, "titulo": f"{prod.nombre} · {prod.codigo} v{v.numero_version}",
            "estado": v.estado, "accion": accion, "solicitante": solicitante,
            "fecha": str(v.creado_en.date()) if v.creado_en else "", "detalle": detalle,
            "nivel": orden, "totalNiveles": total,
            "ruta": f"{RUTA_FRONT}/configurar", "deepLink": {"clave": "configurar_abrir_producto", "valor": prod.id},
        })

    # --- Solicitudes de crédito ---
    for s in (db.query(m.PPSolicitud).filter(m.PPSolicitud.estado == "EN_EVALUACION")
              .order_by(m.PPSolicitud.creado_en.desc()).all()):
        paso = _paso_actual(db, "SOLICITUD", s.id, user, s.enviada_por)
        if not paso:
            continue
        orden, total, _ = paso
        cli = db.get(models.Cliente, s.cliente_id) if s.cliente_id else None
        nombre = (cli.apellido_nombre if cli else (s.cliente_datos or {}).get("apellido_nombre")) or "Cliente"
        detalle = f"Nivel {orden} de {total} · ${float(s.monto_solicitado):,.0f} a {s.plazo_solicitado} cuotas" if total > 1 \
            else f"Solicitud por ${float(s.monto_solicitado):,.0f} a {s.plazo_solicitado} cuotas"
        tareas.append({
            "tipo": "SOLICITUD", "id": s.id, "titulo": f"{s.numero} · {nombre}",
            "estado": s.estado, "accion": "resolver", "solicitante": s.enviada_por or s.creado_por or "—",
            "fecha": str(s.creado_en.date()) if s.creado_en else "", "detalle": detalle,
            "nivel": orden, "totalNiveles": total,
            "ruta": f"{RUTA_FRONT}/solicitudes-credito", "deepLink": {"clave": "solicitud_abrir", "valor": s.id},
        })

    # --- Pendientes de contrato (gate de DESEMBOLSO / REFINANCIACION) — se aprueban desde el propio inbox ---
    for p in (db.query(m.PPWorkflowPendiente).filter(m.PPWorkflowPendiente.estado == "PENDIENTE")
              .order_by(m.PPWorkflowPendiente.creado_en.desc()).all()):
        paso = _paso_actual(db, p.objeto, p.id, user, p.solicitado_por)
        if not paso:
            continue
        orden, total, _ = paso
        c = db.get(m.PPContrato, p.contrato_id)
        if not c:
            continue
        base = "Desembolso del contrato" if p.objeto == "DESEMBOLSO" else \
            f"Refinanciar a TNA {p.datos.get('tasa')}% / {p.datos.get('plazo')} cuotas"
        detalle = f"{base} · Nivel {orden} de {total}" if total > 1 else base
        tareas.append({
            "tipo": p.objeto, "id": p.id, "titulo": f"{c.numero_contrato} · {c.cliente_nombre}",
            "estado": "PENDIENTE", "accion": "aprobar-inline", "solicitante": p.solicitado_por or "—",
            "fecha": str(p.creado_en.date()) if p.creado_en else "", "detalle": detalle,
            "nivel": orden, "totalNiveles": total, "ruta": "", "deepLink": None,
        })
    return tareas


class ResolverIn(BaseModel):
    motivo: str = ""


@router.post("/pendientes/{pid}/aprobar")
def aprobar_pendiente(pid: str, request: Request, db: Session = Depends(get_db),
                      user: models.Usuario = Depends(get_current_user)):
    """Aprueba un paso del gate de un pendiente (DESEMBOLSO/REFINANCIACION). Si completa la cadena,
    ejecuta la operación real."""
    from app.services import workflow as wf
    from app.api import contratos as C
    ip = audit.ip_de(request)
    pend = db.get(m.PPWorkflowPendiente, pid)
    if not pend or pend.estado != "PENDIENTE":
        raise HTTPException(404, "Pendiente no encontrado o ya resuelto.")
    paso = wf.aprobar_paso(db, pend.objeto, pend.id, user, pend.solicitado_por)
    if not paso["ok"]:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Aprobación", entidad_id=pend.id, operacion="APROBAR",
                               resultado="RECHAZADO", antes={"objeto": pend.objeto, "estado": "PENDIENTE"},
                               detalle=f"Aprobación rechazada: {paso['motivo']}")
        raise HTTPException(paso["status"], paso["motivo"])
    if paso["completo"]:
        pend.estado = "APROBADO"; pend.resuelto_por = user.username
        db.flush()
        resultado = C.ejecutar_pendiente(db, pend, user)   # ejecuta y commitea
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Aprobación", entidad_id=pend.id, operacion="APROBAR", resultado="OK",
                               antes={"objeto": pend.objeto, "estado": "PENDIENTE"},
                               despues={"estado": "APROBADO", "ejecutado": True},
                               detalle=f"Cadena completa: {pend.objeto} aprobado y ejecutado")
        return {"aprobado": True, "ejecutado": True, "resultado": resultado}
    db.commit()
    audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                           entidad="Aprobación", entidad_id=pend.id, operacion="APROBAR", resultado="OK",
                           antes={"objeto": pend.objeto, "estado": "PENDIENTE"},
                           despues={"estado": "PENDIENTE", "nivel_aprobado": paso["nivel"], "faltan": paso["faltan"]},
                           detalle=f"Nivel {paso['nivel']} aprobado; faltan {paso['faltan']} para completar la cadena")
    return {"aprobado": True, "ejecutado": False, "faltan": paso["faltan"], "nivel": paso["nivel"]}


@router.post("/pendientes/{pid}/rechazar")
def rechazar_pendiente(pid: str, data: ResolverIn, request: Request, db: Session = Depends(get_db),
                       user: models.Usuario = Depends(get_current_user)):
    """Rechaza un pendiente (no se ejecuta la operación)."""
    from app.services import workflow as wf
    ip = audit.ip_de(request)
    pend = db.get(m.PPWorkflowPendiente, pid)
    if not pend or pend.estado != "PENDIENTE":
        raise HTTPException(404, "Pendiente no encontrado o ya resuelto.")
    # Con la regla inactiva, puede_aprobar deja pasar a cualquiera: el gate es entonces el permiso de
    # aprobación (mismo criterio que H-153 para solicitudes).
    _regla = wf.regla(db, pend.objeto)
    if (_regla is None or not _regla.activo) and not _caps(db, user)["aprueba"]:
        raise HTTPException(403, "No tenés permiso de aprobación de créditos. Se asigna en Seguridad de Portezuelo.")
    ok, status, motivo = wf.puede_aprobar(db, pend.objeto, user,
                                          actores={pend.solicitado_por} if pend.solicitado_por else set())
    if not ok:
        raise HTTPException(status, motivo)
    pend.estado = "RECHAZADO"; pend.resuelto_por = user.username; pend.motivo = data.motivo or "Sin motivo"
    wf.limpiar_aprobaciones(db, pend.objeto, pend.id)
    db.commit()
    audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                           entidad="Aprobación", entidad_id=pend.id, operacion="RECHAZAR", resultado="OK",
                           antes={"objeto": pend.objeto, "estado": "PENDIENTE"},
                           despues={"estado": "RECHAZADO"}, detalle=f"Rechazado: {pend.motivo}")
    return {"rechazado": True}


@router.get("/inbox")
def inbox(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Bandeja de tareas de aprobación del usuario actual."""
    items = _inbox(db, user)
    porTipo: dict[str, int] = {}
    for t in items:
        porTipo[t["tipo"]] = porTipo.get(t["tipo"], 0) + 1
    return {"items": items, "total": len(items), "porTipo": porTipo}
