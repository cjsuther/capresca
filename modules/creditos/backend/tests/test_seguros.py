"""Módulo Seguros: emisión de póliza al otorgar y liquidación a la compañía."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_seg.db"
os.environ["ENVIRONMENT"] = "development"

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _otorgar_con_seguro(client, h, fecha="2026-07-01"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    # la línea francesa del seed tiene compañía y prima de seguro
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "240000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": fecha,
    }).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def test_poliza_emitida_al_otorgar(client):
    h = _auth(client)
    cred = _otorgar_con_seguro(client, h)
    polizas = client.get(f"/api/creditos/seguros/polizas?credito_id={cred['id']}", headers=h).json()
    assert len(polizas) == 1
    p = polizas[0]
    assert p["estado"] == "V"
    assert Decimal(p["capital_asegurado"]) == Decimal("240000.00")


def test_liquidacion_agrupa_seguro_cobrado(client):
    h = _auth(client)
    fecha = "2026-07-01"
    cred = _otorgar_con_seguro(client, h, fecha=fecha)
    # las cuotas deben traer seguro (>0) porque la línea tiene prima
    assert any(float(c["seguro"]) > 0 for c in cred["cuotas"])

    # cobrar 2 cuotas ese día
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1, 2], "fecha_pago": fecha,
    })
    liq = client.get(f"/api/creditos/seguros/liquidacion?desde={fecha}&hasta={fecha}", headers=h).json()
    assert len(liq) >= 1
    fila = liq[0]
    assert Decimal(fila["total_seguro"]) > 0
    assert fila["compania"]


def teardown_module(_):
    if os.path.exists("_seg.db"):
        os.remove("_seg.db")
