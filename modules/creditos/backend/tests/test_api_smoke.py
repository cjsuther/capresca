"""Smoke test de la API completa (login + simulación) sobre SQLite en memoria."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_smoke.db"
os.environ["ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient  # noqa: E402


def _client():
    # importar después de fijar el entorno
    from app.main import app
    return TestClient(app)


def test_flujo_login_y_simulacion():
    with _client() as client:
        # health
        assert client.get("/api/creditos/health").json()["status"] == "ok"

        # login
        r = client.post("/api/creditos/auth/login",
                        data={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # sin token -> 401
        assert client.get("/api/creditos/clientes").status_code == 401

        # líneas sembradas
        lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
        assert len(lineas) >= 4
        linea_frances = next(l for l in lineas if l["tipo_calculo"] == 1)

        # simulación francés con margen
        r = client.post("/api/creditos/creditos/simular", headers=h, json={
            "linea_id": linea_frances["id"],
            "capital": "500000",
            "plazo": 12,
            "fecha_primer_vencimiento": "2026-09-01",
            "sueldo": "650000",
            "total_afectado": "0",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["cantidad_cuotas"] == 12
        assert len(data["cuotas"]) == 12
        assert data["puede_tomar_credito"] is True
        # el capital amortizado total = capital
        total_cap = sum(float(c["amortizacion"]) for c in data["cuotas"])
        assert round(total_cap, 2) == 500000.00

        # clientes
        cli = client.get("/api/creditos/clientes", headers=h).json()["items"]
        assert any(c["cuil"] == "20123456786" for c in cli)


def teardown_module(_):
    if os.path.exists("_smoke.db"):
        os.remove("_smoke.db")
