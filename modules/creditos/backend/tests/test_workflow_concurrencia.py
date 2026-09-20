"""Cuatro-ojos / N-ojos: la cadena de aprobación no se puede completar duplicando el mismo nivel.

Riesgo (deep-QA): `aprobar_paso` calcula el nivel actual como max(aprobados)+1 e inserta una fila.
Bajo concurrencia, dos aprobadores del nivel 1 podrían leer el mismo estado e insertar dos filas de
nivel 1, marcando 'completo' una cadena de 2 niveles sin aprobar el nivel 2 (bypass de N-ojos).
La constraint única (objeto, objeto_id, nivel_orden) hace que la DB sea el árbitro y lo impida.
"""
import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
def db():
    from app.core.database import SessionLocal
    from app.main import app  # fuerza create_all + migraciones de arranque
    from fastapi.testclient import TestClient
    with TestClient(app):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.rollback(); s.close()


def test_un_nivel_se_aprueba_una_sola_vez(db):
    """Insertar dos aprobaciones del MISMO (objeto, objeto_id, nivel_orden) falla: la DB es árbitro."""
    from app import models_productos as m
    oid = "obj-concurrencia-test"
    db.query(m.PPWorkflowAprobacion).filter_by(objeto="LINEA", objeto_id=oid).delete()
    db.commit()
    db.add(m.PPWorkflowAprobacion(objeto="LINEA", objeto_id=oid, nivel_orden=1, aprobado_por="ana"))
    db.commit()
    # segundo aprobador cae en el MISMO nivel 1 (carrera) → la constraint lo rechaza
    db.add(m.PPWorkflowAprobacion(objeto="LINEA", objeto_id=oid, nivel_orden=1, aprobado_por="beto"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # el nivel 2 SÍ se puede aprobar (avanza la cadena, no la completa por duplicado)
    db.add(m.PPWorkflowAprobacion(objeto="LINEA", objeto_id=oid, nivel_orden=2, aprobado_por="beto"))
    db.commit()
    filas = db.query(m.PPWorkflowAprobacion).filter_by(objeto="LINEA", objeto_id=oid).count()
    assert filas == 2   # nivel 1 (ana) + nivel 2 (beto), nunca dos veces el nivel 1
    # limpieza
    db.query(m.PPWorkflowAprobacion).filter_by(objeto="LINEA", objeto_id=oid).delete()
    db.commit()


def test_aprobar_paso_carrera_devuelve_409(db, monkeypatch):
    """Carrera real: dos aprobadores ven el MISMO nivel actual (progreso stale). El primero lo toma;
    el segundo choca contra la constraint y aprobar_paso devuelve ok=False status=409 (no revienta)."""
    from app.services import workflow as wf
    from app import models

    oid = "obj-carrera-409"
    db.query(wf.m.PPWorkflowAprobacion).filter_by(objeto="LINEA", objeto_id=oid).delete()
    db.commit()

    r = wf.regla(db, "LINEA")
    assert r is not None
    r.activo = True; db.commit()   # el cuatro-ojos se siembra inactivo (H-141); este test lo activa
    nivel1 = next(n for n in r.niveles if n.orden == 1)

    # Ambos aprobadores ven el mismo estado stale: nivel actual = 1, sin actores (aún nadie aprobó).
    monkeypatch.setattr(wf, "progreso", lambda *a, **k: {
        "aprobados": [], "actores": set(), "nivelActual": 1, "total": len(r.niveles),
        "completo": False, "aprobadores": []})

    ana = models.Usuario(username="ana_carrera", perfil="SSO", password_hash="x")
    beto = models.Usuario(username="beto_carrera", perfil="SSO", password_hash="x")
    db.add_all([ana, beto]); db.flush()
    # Ambos tienen el permiso que exige el nivel (lo inyecta el gateway en get_current_user).
    from app.core.gateway import ROLES_APROBACION
    for u in (ana, beto):
        u.permisos_gateway = frozenset({ROLES_APROBACION[nivel1.rol]})

    r1 = wf.aprobar_paso(db, "LINEA", oid, ana, emisor=None)
    assert r1["ok"] is True and r1["nivel"] == 1                 # ana toma el nivel 1
    r2 = wf.aprobar_paso(db, "LINEA", oid, beto, emisor=None)    # beto ve el mismo nivel 1 → choca
    assert r2["ok"] is False and r2["status"] == 409

    db.rollback()
    db.query(wf.m.PPWorkflowAprobacion).filter_by(objeto="LINEA", objeto_id=oid).delete()
    db.query(models.Usuario).filter(models.Usuario.username.in_(["ana_carrera", "beto_carrera"])).delete()
    db.commit()
