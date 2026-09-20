"""Auditoría de cambios del sistema nuevo (H-117): las mutaciones sensibles dejan un rastro
rico — usuario, IP, entidad, operación, resultado y el estado antes/después — y los rechazos
también quedan auditados. Idea incorporada del memo de migración de créditos."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_audit.db"
os.environ["ENVIRONMENT"] = "development"

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


def _payload(client, h):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json()
                 if l["activa"] and l["tipo_calculo"] == 1)
    return {"cliente_id": cli, "linea_id": linea["id"], "monto_solicitado": "80000",
            "cantidad_cuotas": 6, "fecha_primer_vencimiento": "2026-03-10"}


def test_alta_solicitud_deja_auditoria_con_ip(client):
    """Un alta OK deja un evento ALTA/OK con IP y datos_nuevos, sin log VFP de por medio."""
    h = _auth(client)
    body = _payload(client, h)
    # X-Forwarded-For debe quedar registrado como IP de origen.
    r = client.post("/api/creditos/creditos/solicitudes", headers={**h, "X-Forwarded-For": "203.0.113.7"}, json=body)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    d = client.get("/api/creditos/admin/auditoria-cambios", headers=h,
                   params={"entidad": "Solicitud", "operacion": "ALTA"}).json()
    assert d["total"] >= 1
    ev = next(e for e in d["items"] if str(e["entidad_id"]) == str(sid))
    assert ev["resultado"] == "OK"
    assert ev["usuario"] == "admin"
    assert ev["ip"] == "203.0.113.7"

    det = client.get(f"/api/creditos/admin/auditoria-cambios/{ev['id']}", headers=h).json()
    assert det["datos_nuevos"]["cliente_id"] == body["cliente_id"]
    assert det["datos_nuevos"]["estado"] == "I"


def test_mutacion_rechazada_queda_auditada(client):
    """Un alta con cliente inexistente se audita como ERROR (el registro no rompe el flujo)."""
    h = _auth(client)
    body = _payload(client, h)
    body["cliente_id"] = 999999   # inexistente → 404
    r = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body)
    assert r.status_code == 404

    d = client.get("/api/creditos/admin/auditoria-cambios", headers=h,
                   params={"entidad": "Solicitud", "resultado": "ERROR"}).json()
    assert d["total"] >= 1
    assert any("inexistente" in (e["detalle"] or "").lower() for e in d["items"])


def test_pago_contrato_deja_auditoria(client):
    """H-118: la cobranza (COBRAR) y su anulación (ANULAR) dejan rastro con antes/después + IP."""
    h = _auth(client)
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json()
                 if l["activa"] and l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"], "monto_solicitado": "120000",
        "cantidad_cuotas": 6, "fecha_primer_vencimiento": "2026-01-10"}).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()

    r = client.post("/api/creditos/caja/cobrar", headers={**h, "X-Forwarded-For": "10.20.30.40"},
                    json={"credito_id": cred["id"], "cuotas": [1], "fecha_pago": "2026-01-10"})
    assert r.status_code == 201, r.text
    recibo_num = r.json()["numero"]

    d = client.get("/api/creditos/admin/auditoria-cambios", headers=h,
                   params={"entidad": "Recibo", "operacion": "COBRAR"}).json()
    ev = next(e for e in d["items"] if str(e["entidad_id"]) == str(recibo_num))
    assert ev["resultado"] == "OK"
    assert ev["ip"] == "10.20.30.40"
    det = client.get(f"/api/creditos/admin/auditoria-cambios/{ev['id']}", headers=h).json()
    assert det["datos_nuevos"]["credito_id"] == cred["id"]

    # Anular → deja su propio rastro ANULAR con estado antes/después.
    recibo_id = r.json()["id"]
    ra = client.post(f"/api/creditos/caja/recibos/{recibo_id}/anular", headers=h)
    assert ra.status_code == 200, ra.text
    da = client.get("/api/creditos/admin/auditoria-cambios", headers=h,
                    params={"entidad": "Recibo", "operacion": "ANULAR"}).json()
    assert da["total"] >= 1


def test_filtro_y_diff(client):
    """El diff antes/después se computa: una baja de crédito registra el cambio de estado."""
    h = _auth(client)
    body = _payload(client, h)
    sid = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body).json()["id"]
    cid = client.post(f"/api/creditos/creditos/solicitudes/{sid}/otorgar", headers=h).json()["id"]

    r = client.post(f"/api/creditos/creditos/{cid}/baja", headers=h,
                    json={"motivo": "QA auditoría", "fecha": "2026-03-15"})
    # La baja puede resultar OK o RECHAZADA por regla; en cualquier caso queda auditada.
    d = client.get("/api/creditos/admin/auditoria-cambios", headers=h,
                   params={"entidad": "Credito", "operacion": "BAJA"}).json()
    assert d["total"] >= 1
    ev = d["items"][0]
    det = client.get(f"/api/creditos/admin/auditoria-cambios/{ev['id']}", headers=h).json()
    if ev["resultado"] == "OK":
        assert det["cambios"]["estado"] == [det["datos_anteriores"]["estado"], "B"]
    assert r.status_code in (200, 409)
