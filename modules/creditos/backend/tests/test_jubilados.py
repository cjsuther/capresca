"""Créditos de jubilados / Ley 5094."""
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


def _sembrar():
    db = SessionLocal()
    j = models.CreditoJubilado(id=9001, cuil="20111111119", apellido_nombre="JUBILADO TEST",
                               departamento="CAPITAL", monto=Decimal("500000"),
                               cantidad_cuotas=10, liquidada=True)
    db.add(j)
    db.add(models.CuotaJubilado(credito_jubilado_id=9001, numero=1, valor=Decimal("50000"),
                                fecha_vencimiento=date(2026, 2, 1), pagada=False))
    db.commit(); db.close()


def test_resumen_y_por_departamento(client):
    h = _auth(client)
    _sembrar()
    r = client.get("/api/creditos/creditos/consultas/jubilados/resumen", headers=h).json()
    assert r["total"] >= 1 and r["liquidadas"] >= 1
    dep = client.get("/api/creditos/creditos/consultas/jubilados/por-departamento", headers=h).json()
    assert any(d["departamento"] == "CAPITAL" and d["cantidad"] >= 1 for d in dep)
