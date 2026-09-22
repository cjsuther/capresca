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


def _eventos(entidad: str, **filtros) -> list:
    """Rastro de auditoría tal como queda en la base (la consulta de auditoría era del área Seguridad
    de CCyPP, que no se migró; el registro de cada mutación sigue igual)."""
    from app import models
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        q = db.query(models.AuditoriaCambio).filter_by(entidad=entidad, **filtros)
        eventos = q.order_by(models.AuditoriaCambio.id.desc()).all()
        db.expunge_all()
        return eventos


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

    ev = next(e for e in _eventos("Solicitud", operacion="ALTA") if str(e.entidad_id) == str(sid))
    assert ev.resultado == "OK"
    assert ev.usuario == "admin"
    assert ev.ip == "203.0.113.7"
    assert ev.datos_nuevos["cliente_id"] == body["cliente_id"]
    assert ev.datos_nuevos["estado"] == "I"


def test_mutacion_rechazada_queda_auditada(client):
    """Un alta con cliente inexistente se audita como ERROR (el registro no rompe el flujo)."""
    h = _auth(client)
    body = _payload(client, h)
    body["cliente_id"] = 999999   # inexistente → 404
    r = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body)
    assert r.status_code == 404

    errores = _eventos("Solicitud", resultado="ERROR")
    assert errores
    assert any("inexistente" in (e.detalle or "").lower() for e in errores)


def test_pago_contrato_deja_auditoria(client):
    """H-118: el cobro de un contrato deja rastro PAGAR con antes/después + IP."""
    h = _auth(client)
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    pers = next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")
    cto = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": "AUDIT PAGO", "monto": 300000, "plazo": 12}).json()

    r = client.post(f"/api/creditos/contratos/{cto['id']}/actividad",
                    headers={**h, "X-Forwarded-For": "10.20.30.40"}, json={"tipo": "PAYMENT"})
    assert r.status_code == 200, r.text

    ev = next(e for e in _eventos("Contrato", operacion="PAGAR") if e.entidad_id == cto["id"])
    assert ev.resultado == "OK"
    assert ev.ip == "10.20.30.40"
    assert ev.datos_anteriores["estado"] == "ACTIVO"
    assert ev.datos_nuevos["tipo"] == "PAYMENT"


def test_filtro_y_diff(client):
    """El diff antes/después se computa: una baja de crédito registra el cambio de estado."""
    h = _auth(client)
    body = _payload(client, h)
    sid = client.post("/api/creditos/creditos/solicitudes", headers=h, json=body).json()["id"]
    cid = client.post(f"/api/creditos/creditos/solicitudes/{sid}/otorgar", headers=h).json()["id"]

    r = client.post(f"/api/creditos/creditos/{cid}/baja", headers=h,
                    json={"motivo": "QA auditoría", "fecha": "2026-03-15"})
    # La baja puede resultar OK o RECHAZADA por regla; en cualquier caso queda auditada.
    bajas = _eventos("Credito", operacion="BAJA")
    assert bajas
    ev = bajas[0]
    if ev.resultado == "OK":
        assert ev.cambios["estado"] == [ev.datos_anteriores["estado"], "B"]
    assert r.status_code in (200, 409)
