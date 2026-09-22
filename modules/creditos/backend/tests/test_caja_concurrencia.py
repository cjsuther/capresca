"""Unicidad concurrente del Nº de recibo (H-108): la DB es el árbitro contra dos cajeros que emiten
el mismo número a la vez, y `_emitir_recibo` reintenta con el próximo libre en vez de duplicar/500."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_caja_conc.db"
os.environ["ENVIRONMENT"] = "development"

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
def db():
    from app.core.database import SessionLocal
    from app.main import app  # create_all aplica el unique=True del modelo Recibo.numero
    from fastapi.testclient import TestClient
    with TestClient(app):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.rollback(); s.close()


def _recibo(n):
    from app import models
    from datetime import date
    return models.Recibo(numero=n, fecha_pago=date(2026, 1, 10), cliente_id=1, credito_id=1,
                          cajero="admin", via_pago="EFECTIVO", estado="E", total=0)


def test_recibo_numero_unico(db):
    """Dos recibos con el mismo número: la DB rechaza el segundo (constraint única)."""
    from app import models
    db.query(models.Recibo).filter(models.Recibo.numero.in_([900001, 900002])).delete()
    db.commit()
    db.add(_recibo(900001)); db.commit()
    db.add(_recibo(900001))                       # mismo número → carrera de dos cajeros
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # otro número sí entra
    db.add(_recibo(900002)); db.commit()
    assert db.query(models.Recibo).filter(models.Recibo.numero.in_([900001, 900002])).count() == 2
    db.query(models.Recibo).filter(models.Recibo.numero.in_([900001, 900002])).delete(); db.commit()


def test_orden_pago_numero_unico(db):
    """Nº de OP único: la DB rechaza dos órdenes de pago con el mismo número (carrera). H-108."""
    from app import models
    from datetime import date
    def op(n):
        return models.OrdenPago(numero=n, fecha=date(2026, 1, 10), beneficiario="X", concepto="pago", importe=0)
    db.query(models.OrdenPago).filter(models.OrdenPago.numero.in_([990001, 990002])).delete(); db.commit()
    db.add(op(990001)); db.commit()
    db.add(op(990001))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(op(990002)); db.commit()
    assert db.query(models.OrdenPago).filter(models.OrdenPago.numero.in_([990001, 990002])).count() == 2
    db.query(models.OrdenPago).filter(models.OrdenPago.numero.in_([990001, 990002])).delete(); db.commit()


def test_emitir_recibo_reintenta_en_carrera(db, monkeypatch):
    """_emitir_recibo: si el número generado ya lo tomó otro (carrera), reintenta con el próximo libre."""
    from app import models
    from app.services import caja as svc

    db.query(models.Recibo).filter(models.Recibo.numero.in_([900010, 900011])).delete()
    db.commit()
    db.add(_recibo(900010)); db.commit()          # 900010 ya está tomado

    # el generador devuelve primero el número tomado (900010), luego uno libre (900011)
    llamadas = {"n": 0}
    def gen(_db):
        llamadas["n"] += 1
        return 900010 if llamadas["n"] == 1 else 900011
    monkeypatch.setattr(svc, "_proximo_numero_recibo", gen)

    recibo = svc._emitir_recibo(db, fecha_pago=__import__("datetime").date(2026, 1, 10),
                                cliente_id=1, credito_id=1, cajero="admin", via_pago="EFECTIVO",
                                estado="E", total=0)
    db.commit()
    assert recibo.numero == 900011 and llamadas["n"] == 2   # reintentó una vez con número fresco
    db.query(models.Recibo).filter(models.Recibo.numero.in_([900010, 900011])).delete(); db.commit()
