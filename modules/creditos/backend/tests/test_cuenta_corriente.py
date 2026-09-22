"""Consulta de cuenta corriente de un crédito (VFP: ctacte)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app import models


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cuenta_corriente_saldo(client):
    h = _auth(client)
    db = SessionLocal()
    db.add_all([
        models.MovimientoCta(credito_id=555, cuota=0, fecha=date(2026, 1, 1),
                             tipo="OTOR", debitos=Decimal("100000"), creditos=Decimal("0")),
        models.MovimientoCta(credito_id=555, cuota=1, fecha=date(2026, 2, 1),
                             tipo="PAGO", debitos=Decimal("0"), creditos=Decimal("30000")),
    ])
    db.commit(); db.close()

    r = client.get("/api/creditos/creditos/consultas/cuenta-corriente/555", headers=h).json()
    assert r["cantidad"] == 2
    # saldo final = 100000 - 30000 = 70000
    assert Decimal(r["saldo_final"]) == Decimal("70000")
    assert Decimal(r["movimientos"][-1]["saldo"]) == Decimal("70000")
