"""Transacciones para Contabilidad con outbox: se graban con la operación y se reenvían hasta que llegan."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.core.database import SessionLocal
from app.services import contabilidad_central as contab


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(contab, "CLAVE", "clave-test")
    monkeypatch.setattr(contab, "_asegurar_hilo", lambda: None)     # el envío se prueba a mano
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _originar(client, h, nombre):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    p = next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")
    r = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": nombre, "monto": 1000000, "plazo": 12})
    assert r.status_code == 201, r.text
    return r.json()


def _outbox(numero):
    with SessionLocal() as db:
        return [(f.accion, f.tipo, f.referencia, f.payload) for f in
                db.query(models.OutboxContable).order_by(models.OutboxContable.id).all()
                if numero in f.referencia]


def test_el_desembolso_sale_con_neto_y_cargos_para_la_cuenta_puente(client):
    h = _auth(client)
    c = _originar(client, h, "OUTBOX-DES")
    (accion, tipo, ref, payload), = [x for x in _outbox(c["numero_contrato"]) if x[1] == "DESEMBOLSO"]
    assert (accion, ref) == ("REGISTRAR", c["numero_contrato"])
    d = payload["datos"]
    assert d["capital"] == 1000000 and d["neto"] == c["liquidacion"]["neto"]
    assert d["capital_amortizar"] == c["liquidacion"]["capitalAmortizar"]
    assert d["cargos_financiados"] == c["liquidacion"]["cargosFinanciados"]
    assert d["via_tesoreria"] is False


def test_dos_pagos_parciales_de_la_misma_cuota_no_se_pisan(client):
    h = _auth(client)
    c = _originar(client, h, "OUTBOX-PARC")
    for _ in range(2):
        r = client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h,
                        json={"tipo": "PAYMENT", "importe": 1000, "medio_pago": "efectivo"})
        assert r.status_code in (200, 201), r.text
    cobros = [x for x in _outbox(c["numero_contrato"]) if x[1] == "COBRANZA_CUOTA"]
    assert len(cobros) == 2 and cobros[0][2] != cobros[1][2]
    assert cobros[0][3]["datos"]["medio_pago"] == "EFECTIVO"


def test_el_prepago_parcial_tiene_su_propio_tipo(client):
    h = _auth(client)
    c = _originar(client, h, "OUTBOX-PREP")
    r = client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h,
                    json={"tipo": "PARTIAL_PREPAYMENT", "importe": 50000})
    assert r.status_code in (200, 201), r.text
    assert any(x[1] == "PREPAGO_PARCIAL" for x in _outbox(c["numero_contrato"]))
    assert not any(x[1] == "CANCELACION_ANTICIPADA" for x in _outbox(c["numero_contrato"]))


def test_la_reversa_anula_la_transaccion_en_contabilidad(client):
    h = _auth(client)
    c = _originar(client, h, "OUTBOX-REV")
    pay = client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    act = next(a for a in pay["actividades"] if a["tipo"] == "PAYMENT")
    client.post(f"/api/creditos/contratos/{c['id']}/actividad/{act['id']}/reversar", headers=h)
    filas = _outbox(c["numero_contrato"])
    cobro = next(x for x in filas if x[1] == "COBRANZA_CUOTA" and x[0] == "REGISTRAR")
    anul = next(x for x in filas if x[0] == "ANULAR")
    assert (anul[1], anul[2]) == (cobro[1], cobro[2])


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class _Cliente:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def post(self, url, json, headers, timeout):
        self.llamadas.append((url, json, headers))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_el_outbox_reintenta_hasta_que_contabilidad_recibe(client):
    h = _auth(client)
    c = _originar(client, h, "OUTBOX-ENV")
    ahora = models._utc_ahora() + timedelta(seconds=1)
    with SessionLocal() as db:
        pendientes = db.query(models.OutboxContable).filter_by(estado="PENDIENTE").count()
        caida = _Cliente([ConnectionError("contabilidad caída")] * pendientes)
        assert contab.enviar_pendientes(db, ahora=ahora, cliente=caida) == 0
        f = db.query(models.OutboxContable).filter(models.OutboxContable.referencia == c["numero_contrato"]).one()
        assert f.estado == "PENDIENTE" and f.intentos == 1 and "caída" in f.ultimo_error
        assert f.proximo_intento > ahora                         # espera antes del próximo intento
        # Antes de la espera no se reintenta; después, sí, y queda enviada.
        assert contab.enviar_pendientes(db, ahora=ahora, cliente=_Cliente([])) == 0
        luego = ahora + timedelta(hours=2)
        ok = _Cliente([_Resp(201)] * pendientes)
        assert contab.enviar_pendientes(db, ahora=luego, cliente=ok) == pendientes
        db.refresh(f)
        assert f.estado == "ENVIADA" and f.enviado_en == luego
        url, cuerpo, headers = next(x for x in ok.llamadas if x[1]["referencia"] == c["numero_contrato"])
        assert url.endswith("/internal/contabilidad/transacciones") and headers["X-Api-Key"] == "clave-test"
        assert cuerpo["modulo"] == "creditos" and cuerpo["tipo"] == "DESEMBOLSO"


def test_las_anulaciones_van_al_endpoint_de_anular(client):
    with SessionLocal() as db:
        db.query(models.OutboxContable).delete()
        contab.anular(db, tipo="COBRANZA_CUOTA", referencia="CTO-X/C1/A9", fecha=datetime(2026, 10, 10).date(),
                      motivo="Reversa")
        db.commit()
        cli = _Cliente([_Resp(200)])
        assert contab.enviar_pendientes(db, cliente=cli) == 1
        assert cli.llamadas[0][0].endswith("/transacciones/anular")
        assert cli.llamadas[0][1]["fecha"] == "2026-10-10"


def test_si_la_operacion_se_deshace_la_transaccion_no_sale(client):
    with SessionLocal() as db:
        antes = db.query(models.OutboxContable).count()
        contab.registrar(db, tipo="DESEMBOLSO", referencia="CTO-ROLLBACK", fecha=datetime.now().date(),
                         datos={"capital": 1})
        db.rollback()
        assert db.query(models.OutboxContable).count() == antes
