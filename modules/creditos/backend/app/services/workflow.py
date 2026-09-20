"""Motor de workflow de aprobaciones configurable (cuatro-ojos / N-ojos en serie).

Una regla por tipo de objeto (LINEA, SOLICITUD, DESEMBOLSO, REFINANCIACION); cada regla tiene N
niveles en serie; cada nivel aprueba un ROL base con cuatro-ojos y overrides por usuario
(INCLUIR/EXCLUIR). El evaluador dice si un usuario puede aprobar un nivel dado, respetando que no
apruebe algo en lo que ya intervino (submitter o aprobadores previos).

La configuración vive en Seguridad (`/api/creditos/workflow`); las reglas sembradas replican el cuatro-ojos
actual, así el comportamiento por defecto no cambia.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, models_productos as m
from app.core.gateway import ROLES_APROBACION
from app.core.permisos import roles_de

# Catálogo de objetos aprobables y su estado inicial (activo hoy vs. futuro).
OBJETOS = [
    # App nueva: el cuatro-ojos arranca INACTIVO para que un único admin pueda operar (aprobar/publicar).
    # Se activa desde Seguridad → Workflow cuando la organización suma un segundo aprobador (H-141).
    ("LINEA", "Publicación de línea de crédito", "Aprobar/publicar una versión de línea (Configurar Créditos)", False),
    ("SOLICITUD", "Aprobación de solicitud de crédito", "Resolver una solicitud EN_EVALUACION", False),
    ("DESEMBOLSO", "Otorgamiento / desembolso de contrato", "Aprobar el desembolso de un crédito", False),
    ("REFINANCIACION", "Refinanciación de contrato", "Aprobar una refinanciación", False),
]


def seed_workflow(db: Session) -> None:
    """Siembra las reglas por defecto (idempotente): 1 nivel, rol APROBAR, cuatro-ojos on."""
    for objeto, nombre, desc, activo in OBJETOS:
        if db.query(m.PPWorkflowRegla).filter_by(objeto=objeto).first():
            continue
        regla = m.PPWorkflowRegla(objeto=objeto, nombre=nombre, descripcion=desc, activo=activo)
        db.add(regla); db.flush()
        db.add(m.PPWorkflowNivel(regla_id=regla.id, orden=1, nombre="Aprobación", rol="APROBAR", cuatro_ojos=True))
    db.commit()


def regla(db: Session, objeto: str) -> m.PPWorkflowRegla | None:
    return db.query(m.PPWorkflowRegla).filter_by(objeto=objeto).first()


def niveles(db: Session, objeto: str) -> list[m.PPWorkflowNivel]:
    r = regla(db, objeto)
    return sorted(r.niveles, key=lambda n: n.orden) if r else []


def _rol_apto(db: Session, nivel: m.PPWorkflowNivel, user: models.Usuario) -> bool:
    """¿`user` tiene el rol que aprueba este nivel? Los roles de aprobación (APROBAR / SUPERVISAR) salen de
    los permisos `aprobaciones:*` que el usuario tiene en Seguridad de Portezuelo; es la misma fuente que
    gobierna las capacidades de las pantallas (caps_creditos)."""
    return (nivel.rol or "").upper() in roles_de(db, user)


def elegible_en_nivel(db: Session, nivel: m.PPWorkflowNivel, user: models.Usuario,
                      actores: set[str] | None = None) -> bool:
    """Elegible = tiene el rol Y (sin cuatro-ojos o no intervino todavía)."""
    if not _rol_apto(db, nivel, user):
        return False
    return not (nivel.cuatro_ojos and user.username in (actores or set()))


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
    # El permiso para aprobar sale de los roles de aprobación del usuario (permisos de Portezuelo).
    if not _rol_apto(db, niv, user):
        return False, 403, (f"No tenés el permiso que aprueba este paso ({ROLES_APROBACION.get((niv.rol or '').upper(), niv.rol)}). "
                            "Se asigna en Seguridad de Portezuelo.")
    if niv.cuatro_ojos and user.username in (actores or set()):
        return False, 409, "Separación de funciones (cuatro-ojos): no podés aprobar algo en lo que ya interviniste."
    return True, 200, "elegible"
