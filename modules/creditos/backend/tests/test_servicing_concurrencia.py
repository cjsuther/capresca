"""Event-sourcing del servicing (H-110): una actividad se reversa UNA sola vez (la DB es árbitro contra
dos reversar concurrentes) y `_recompute` es determinista (recomputar N veces da el mismo estado)."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_servicing.db"
os.environ["ENVIRONMENT"] = "development"

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
def app_client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    from app.core.database import SessionLocal
    from app.main import app
    with TestClient(app):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.rollback(); s.close()


def test_reversa_de_unico(db):
    """Dos REVERSAL apuntando a la misma actividad original → la DB rechaza la segunda (uq_pp_actividad_reversa_de).
    Los NULL (actividades que no son reversas) conviven sin problema."""
    from app import models_productos as m
    orig = "act-orig-h110"
    db.query(m.PPActividad).filter(m.PPActividad.reversa_de == orig).delete()
    db.query(m.PPActividad).filter(m.PPActividad.id.in_(["revA", "revB", "n1", "n2"])).delete()
    db.commit()
    db.add(m.PPActividad(id="revA", contrato_id="c1", tipo="REVERSAL", fecha=date(2026, 1, 1), importe=0, reversa_de=orig))
    db.commit()
    db.add(m.PPActividad(id="revB", contrato_id="c1", tipo="REVERSAL", fecha=date(2026, 1, 1), importe=0, reversa_de=orig))
    with pytest.raises(IntegrityError):        # segunda reversa de la misma actividad → rechazada
        db.commit()
    db.rollback()
    # varias actividades no-reversa (reversa_de = NULL) conviven
    db.add(m.PPActividad(id="n1", contrato_id="c1", tipo="PAYMENT", fecha=date(2026, 1, 1), importe=0))
    db.add(m.PPActividad(id="n2", contrato_id="c1", tipo="PAYMENT", fecha=date(2026, 1, 1), importe=0))
    db.commit()
    assert db.query(m.PPActividad).filter(m.PPActividad.id.in_(["revA", "n1", "n2"])).count() == 3
    db.query(m.PPActividad).filter(m.PPActividad.id.in_(["revA", "n1", "n2"])).delete(); db.commit()


def _estado(c):
    return ([(q.numero_cuota, q.estado, str(q.pagado), str(q.total)) for q in sorted(c.cuotas, key=lambda x: x.numero_cuota)],
            str(c.saldo_capital), c.estado)


def test_recompute_determinista(app_client):
    """Recomputar el mismo contrato N veces da EXACTAMENTE el mismo estado (event-sourcing idempotente)."""
    from app.core.database import SessionLocal
    from app.api.contratos import _recompute
    from app import models_productos as m

    h = {"Authorization": f"Bearer {app_client.post('/api/creditos/auth/login', data={'username':'admin','password':'admin123'}).json()['access_token']}"}
    p = next(x for x in app_client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if x["codigo"] == "LP-PERS-01")
    c = app_client.post("/api/creditos/contratos/originar", headers=h,
                        json={"producto_id": p["id"], "cliente_nombre": "DET", "monto": 1200000, "plazo": 24}).json()
    cid = c["id"]
    fv = c["fecha_valor"]
    app_client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "fecha": fv})

    s = SessionLocal()
    try:
        cont = s.get(m.PPContrato, cid)
        _recompute(cont); e1 = _estado(cont)
        _recompute(cont); e2 = _estado(cont)
        _recompute(cont); e3 = _estado(cont)
        assert e1 == e2 == e3           # idempotente: mismo estado tras cada recompute
    finally:
        s.rollback(); s.close()
