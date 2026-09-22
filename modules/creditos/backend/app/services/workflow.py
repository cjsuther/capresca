"""Motor de workflow de aprobaciones (cuatro-ojos / N-ojos en serie).

La DEFINICIÓN de las reglas (niveles, rol que aprueba cada uno, cuatro-ojos y overrides por usuario)
vive en el módulo Configuraciones de Portezuelo; acá se lee con `core.configuraciones.regla_workflow`.
La EJECUCIÓN es de Créditos: qué nivel de qué objeto aprobó quién (`pp_workflow_aprobacion`, con la
DB como árbitro contra dos aprobadores concurrentes en el mismo nivel).

Objetos: LINEA, SOLICITUD, DESEMBOLSO, REFINANCIACION. Regla inactiva o inexistente → no exige
aprobación (el gate lo pone la pantalla con el permiso de aprobar).
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, models_productos as m
from app.core import configuraciones as config
from app.core.configuraciones import NivelWorkflow, ReglaWorkflow
from app.core.gateway import ROLES_APROBACION
from app.core.permisos import roles_de


def regla(db: Session, objeto: str) -> ReglaWorkflow | None:
    return config.regla_workflow(objeto)


def niveles(db: Session, objeto: str) -> list[NivelWorkflow]:
    r = regla(db, objeto)
    return list(r.niveles) if r else []


def _habilitado(db: Session, nivel: NivelWorkflow, user: models.Usuario) -> bool:
    """¿`user` aprueba este nivel? Por rol (permisos `aprobaciones:*` de Seguridad), salvo los overrides
    del nivel: EXCLUIR le saca la aprobación aunque tenga el rol; INCLUIR se la da aunque no lo tenga."""
    if user.username in nivel.excluidos:
        return False
    if user.username in nivel.incluidos:
        return True
    return (nivel.rol or "").upper() in roles_de(db, user)


def progreso(db: Session, objeto: str, objeto_id: str) -> dict:
    """Estado de la cadena de aprobaciones de un objeto concreto: qué niveles se aprobaron, quiénes
    intervinieron, cuál es el nivel actual pendiente, cuántos niveles tiene y si está completa."""
    aps = (db.query(m.PPWorkflowAprobacion).filter_by(objeto=objeto, objeto_id=objeto_id)
           .order_by(m.PPWorkflowAprobacion.nivel_orden).all())
    total = len(niveles(db, objeto))
    aprobados = [a.nivel_orden for a in aps]
    actores = {a.aprobado_por for a in aps}
    nivel_actual = (max(aprobados) + 1) if aprobados else 1
    completo = total > 0 and len(aprobados) >= total
    return {"aprobados": aprobados, "actores": actores, "nivelActual": nivel_actual,
            "total": total, "completo": completo, "aprobadores": [(a.nivel_orden, a.aprobado_por) for a in aps]}


def aprobar_paso(db: Session, objeto: str, objeto_id: str, user: models.Usuario,
                 emisor: str | None) -> dict:
    """Registra la aprobación del usuario en el nivel actual pendiente si es elegible. Devuelve
    {ok, status, motivo?, completo, nivel, faltan}. Regla inactiva/inexistente → aprueba directo."""
    r = regla(db, objeto)
    if r is None or not r.activo:
        return {"ok": True, "status": 200, "completo": True, "nivel": 0, "faltan": 0}
    prog = progreso(db, objeto, objeto_id)
    orden = prog["nivelActual"]
    actores = set(prog["actores"]) | ({emisor} if emisor else set())
    ok, status, motivo = puede_aprobar(db, objeto, user, actores=actores, orden=orden)
    if not ok:
        return {"ok": False, "status": status, "motivo": motivo}
    db.add(m.PPWorkflowAprobacion(objeto=objeto, objeto_id=objeto_id, nivel_orden=orden, aprobado_por=user.username))
    try:
        db.flush()
    except IntegrityError:
        # Carrera: otro aprobador tomó este mismo nivel entre el chequeo y el insert. La DB es el
        # árbitro (uq_wf_aprobacion_nivel): no se duplica el nivel; el segundo debe reintentar.
        db.rollback()
        return {"ok": False, "status": 409,
                "motivo": "Otro aprobador acaba de resolver este nivel. Refrescá para ver el estado actual."}
    nuevo = progreso(db, objeto, objeto_id)
    return {"ok": True, "status": 200, "completo": nuevo["completo"], "nivel": orden,
            "faltan": max(0, nuevo["total"] - len(nuevo["aprobados"]))}


def limpiar_aprobaciones(db: Session, objeto: str, objeto_id: str) -> None:
    """Descarta las aprobaciones de un objeto (al rechazar/reenviar reinicia la cadena)."""
    db.query(m.PPWorkflowAprobacion).filter_by(objeto=objeto, objeto_id=objeto_id).delete()


def puede_aprobar(db: Session, objeto: str, user: models.Usuario,
                  actores: set[str] | None = None, orden: int = 1) -> tuple[bool, int, str]:
    """Devuelve (permitido, status_http, motivo). Regla inactiva o sin nivel → permitido.
    Precedencia: primero el rol (rechazo → 403), después cuatro-ojos (rechazo → 409)."""
    r = regla(db, objeto)
    if r is None or not r.activo:
        return True, 200, "sin regla activa"
    niv = next((n for n in r.niveles if n.orden == orden), None)
    if niv is None:
        return True, 200, "sin nivel"
    # Aprueba quien tiene el rol del nivel (permisos de Portezuelo), con los overrides del nivel.
    if not _habilitado(db, niv, user):
        if user.username in niv.excluidos:
            return False, 403, "Estás excluido de este paso de aprobación (Configuraciones → Workflow)."
        return False, 403, (f"No tenés el permiso que aprueba este paso ({ROLES_APROBACION.get((niv.rol or '').upper(), niv.rol)}). "
                            "Se asigna en Seguridad de Portezuelo.")
    if niv.cuatro_ojos and user.username in (actores or set()):
        return False, 409, "Separación de funciones (cuatro-ojos): no podés aprobar algo en lo que ya interviniste."
    return True, 200, "elegible"
