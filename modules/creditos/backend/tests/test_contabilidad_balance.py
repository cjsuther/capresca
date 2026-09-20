"""Guarda mecánica 'contabilidad balanceada' (H-109): un asiento de la app (doble partida) no puede
persistirse desbalanceado; los migrados del mayor plano de VFP (origen='legacy') sí (una sola pierna)."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_contab_bal.db"
os.environ["ENVIRONMENT"] = "development"

from datetime import date
import pytest


@pytest.fixture()
def db():
    from app.core.database import SessionLocal
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.rollback(); s.close()


def _asiento(origen, lineas):
    from app import models
    return models.Asiento(fecha=date(2026, 1, 1), concepto="test", origen=origen, ref_id=None,
                          lineas=[models.AsientoLinea(cuenta_codigo=c, cuenta_nombre=c, debe=d, haber=h)
                                  for c, d, h in lineas])


def test_asiento_app_desbalanceado_falla(db):
    """Asiento de la app con Σdebe ≠ Σhaber → la guarda before_insert lo rechaza al flush."""
    a = _asiento("pp_test", [("1.1.01", 100, 0), ("1.2.01", 0, 90)])   # 100 debe vs 90 haber
    db.add(a)
    with pytest.raises(Exception) as ei:
        db.flush()
    assert "desbalanceado" in str(ei.value).lower()
    db.rollback()


def test_asiento_app_balanceado_ok(db):
    """Asiento de la app balanceado → persiste sin problema."""
    a = _asiento("pp_test", [("1.1.01", 100, 0), ("1.2.01", 0, 100)])
    db.add(a); db.flush()
    assert a.id is not None
    db.rollback()


def test_asiento_legacy_desbalanceado_permitido(db):
    """El mayor plano migrado (origen='legacy') es de una sola pierna → la guarda lo excluye."""
    a = _asiento("legacy", [("1.1.01", 868.38, 0)])
    db.add(a); db.flush()          # no debe fallar
    assert a.id is not None
    db.rollback()
