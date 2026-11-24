"""Vista lista del workflow de aprobaciones: las reglas en serie tal como las ejecutan hoy los módulos.

Es de SÓLO LECTURA desde la fase 1 del workflow gráfico: se edita en el editor (`routers/wf.py`), que
publica versiones y las proyecta sobre estas tablas. Tener dos lugares para editar haría que un
borrador del editor pisara sin aviso un cambio hecho acá. Ver docs/decisiones-workflows.md.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, usuario_actual
from app.services import wf_procesos
from app.services.workflow import ROLES, sembrar_reglas, serial_regla

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get("")
def listar(modulo: str | None = Query(None), db: Session = Depends(get_db),
           user: Usuario = Depends(usuario_actual)):
    sembrar_reglas(db)   # un módulo nuevo en el catálogo aparece sin esperar al próximo arranque
    wf_procesos.sincronizar_procesos(db)
    q = db.query(models.WorkflowRegla)
    if modulo:
        q = q.filter(models.WorkflowRegla.modulo == modulo)
    reglas = q.order_by(models.WorkflowRegla.modulo, models.WorkflowRegla.id).all()
    procesos = {(p.modulo, p.objeto): p for p in db.query(models.WfProceso).all()}
    out = []
    for r in reglas:
        d = serial_regla(r)
        p = procesos.get((r.modulo, r.objeto))
        pub = wf_procesos.publicada(p) if p else None
        d["procesoId"] = p.id if p else None
        d["versionPublicada"] = pub.numero if pub else None
        out.append(d)
    # `puedeEditar` queda en False: la vista lista ya no edita (se edita en el editor gráfico).
    return {"reglas": out, "roles": list(ROLES), "puedeEditar": False}
