"""Pagos acreditados → transacción para Contabilidad por outbox (mismo commit que el pago)."""
from app import models
from app.services import contabilidad_central as contab, interbanking

import pytest


@pytest.fixture(autouse=True)
def contabilidad_activa(monkeypatch):
    monkeypatch.setattr(contab, "CLAVE", "clave-test")
    monkeypatch.setattr(contab, "_asegurar_hilo", lambda: None)


def _aprobado(client, lote_creditos, teso):
    lid = lote_creditos()["id"]
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    return lid


def test_el_pago_acreditado_queda_en_el_outbox_con_la_cuenta_de_origen(client, lote_creditos, teso, banco, db):
    banco.respuestas = [{"status": "ACREDITADA"}, interbanking.EnvioRechazado("CBU inexistente")]
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()

    filas = db.query(models.OutboxContable).all()
    assert len(filas) == 1                                    # sólo el acreditado, no el fallido
    f = filas[0]
    assert (f.accion, f.tipo, f.estado) == ("REGISTRAR", "PAGO_CREDITOS", "PENDIENTE")
    assert f.referencia == f"{d['codigo']}/cto-1"
    datos = f.payload["datos"]
    assert datos["cuenta_origen"] == "99900011122" and datos["importe"] == 500000.0
    assert datos["origen"] == "CREDITOS" and datos["lote_origen"] == "liquidación 2026-09-22"
    assert f.payload["modulo"] == "tesoreria"


def test_el_incierto_resuelto_va_con_la_fecha_que_queda_registrada(client, lote_creditos, teso, banco, db):
    banco.respuestas = [interbanking.EnvioIncierto("timeout"), {"status": "ACREDITADA"}]
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    pid = d["pagos"][0]["id"]
    client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/resolver", headers=teso,
                json={"resultado": "CONFIRMADO", "observacion": "Figura acreditada en el extracto"})
    p = db.get(models.Pago, pid)
    f = db.query(models.OutboxContable).filter(models.OutboxContable.referencia.endswith("/cto-1")).one()
    assert f.payload["fecha"] == p.confirmado_en.date().isoformat()
