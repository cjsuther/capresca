"""Pagos salientes automáticos: arrancan apagados y en simulación."""
import asyncio
from decimal import Decimal

import pytest

from app.config import settings
from app.models.reconciliation_payment import ReconciliationPayment
from app.services import payments_service
from conftest import FECHA, agencia, crear_registro


def correr(db, fecha=FECHA):
    return asyncio.run(payments_service.run_payments(db, fecha))


@pytest.fixture
def motor_encendido(monkeypatch):
    """Enciende el kill-switch dejando la simulación activa."""
    monkeypatch.setattr(settings, "auto_payments_enabled", True)
    monkeypatch.setattr(settings, "payments_dry_run", True)


@pytest.fixture
def motor_real(monkeypatch):
    monkeypatch.setattr(settings, "auto_payments_enabled", True)
    monkeypatch.setattr(settings, "payments_dry_run", False)


def agencia_con_saldo_a_favor(db, *, client_id=1, agency_number="A001",
                              adeudado="1000", premios="0", depositado="1500"):
    return crear_registro(db, client_id=client_id, agency_number=agency_number,
                          adeudado=adeudado, premios=premios, depositado=depositado)


# ─────────────────────────────────────────────────────────────────────────────
# Salvaguardas
# ─────────────────────────────────────────────────────────────────────────────
def test_la_configuracion_por_defecto_es_la_segura(db):
    assert settings.auto_payments_enabled is False
    assert settings.payments_dry_run is True


def test_con_el_kill_switch_apagado_no_pasa_nada(db, servicios):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db)

    assert correr(db) == {"enabled": False}
    assert db.query(ReconciliationPayment).count() == 0
    assert servicios.pagos_ejecutados == []


def test_en_simulacion_registra_la_intencion_pero_no_paga(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    rec = agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")

    res = correr(db)

    assert res == {"enabled": True, "dry_run": True, "enviados": 0, "simulados": 1,
                   "sin_cbu": 0, "errores": 0}
    assert servicios.pagos_ejecutados == []          # el banco no se tocó
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "DRY_RUN"
    assert Decimal(str(pago.amount)) == Decimal("500")
    assert pago.cbu_destino == "0720099620000001234501"
    assert pago.ib_transfer_id is None and pago.error_message is None
    db.refresh(rec)
    assert rec.status == "A_PAGAR"


def test_en_simulacion_no_pisa_un_estado_que_no_sea_a_verificar(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    rec = agencia_con_saldo_a_favor(db, depositado="1500")
    rec.status = "CONSOLIDADO_MANUAL"
    db.commit()

    correr(db)

    db.refresh(rec)
    assert rec.status == "CONSOLIDADO_MANUAL"
    assert db.query(ReconciliationPayment).one().status == "DRY_RUN"


def test_una_agencia_sin_saldo_a_favor_no_genera_pago(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1000")   # neto 0
    crear_registro(db, client_id=2, agency_number="A002", adeudado="1000", depositado="200")

    res = correr(db)

    assert res["simulados"] == 0
    assert db.query(ReconciliationPayment).count() == 0


def test_los_premios_cuentan_como_saldo_a_favor(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db, adeudado="1000", premios="300", depositado="1000")

    correr(db)

    assert Decimal(str(db.query(ReconciliationPayment).one().amount)) == Decimal("300")


def test_sin_cbu_de_cobro_queda_marcado_sin_cbu(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", cbus=[])]
    agencia_con_saldo_a_favor(db)

    res = correr(db)

    assert res["sin_cbu"] == 1 and res["simulados"] == 0
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "SIN_CBU" and pago.cbu_destino is None
    assert "no tiene cuenta de cobro" in pago.error_message


def test_se_elige_el_cbu_marcado_como_cuenta_de_cobro(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", cbus=[
        {"cbu": "0000000000000000000001", "is_payment_account": False},
        {"cbu": "0720099620000009999999", "is_payment_account": True},
    ])]
    agencia_con_saldo_a_favor(db)

    correr(db)

    assert db.query(ReconciliationPayment).one().cbu_destino == "0720099620000009999999"


def test_sin_cuenta_marcada_se_usa_el_primer_cbu(db, servicios, motor_encendido):
    servicios.agencias = [agencia(1, "A001", cbus=[
        {"cbu": "0000000000000000000001"}, {"cbu": "0000000000000000000002"},
    ])]
    agencia_con_saldo_a_favor(db)

    correr(db)
    assert db.query(ReconciliationPayment).one().cbu_destino == "0000000000000000000001"


# ─────────────────────────────────────────────────────────────────────────────
# Pago real (sólo con dry-run apagado)
# ─────────────────────────────────────────────────────────────────────────────
def test_con_dry_run_apagado_se_ejecuta_la_transferencia(db, servicios, motor_real):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.respuesta_pago = {"id": 555}
    rec = agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")

    res = correr(db)

    assert res["enviados"] == 1 and res["dry_run"] is False
    assert servicios.pagos_ejecutados == [
        ("0720099620000001234501", 500.0, settings.payment_concepto)]
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "ENVIADO" and pago.ib_transfer_id == 555
    db.refresh(rec)
    assert rec.status == "PAGADO"


def test_un_pago_enviado_no_se_repite(db, servicios, motor_real):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")
    correr(db)

    res = correr(db)

    assert res["enviados"] == 0
    assert len(servicios.pagos_ejecutados) == 1
    assert db.query(ReconciliationPayment).count() == 1


def test_una_simulacion_previa_se_convierte_en_envio(db, servicios, monkeypatch):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")
    monkeypatch.setattr(settings, "auto_payments_enabled", True)
    monkeypatch.setattr(settings, "payments_dry_run", True)
    correr(db)
    assert db.query(ReconciliationPayment).one().status == "DRY_RUN"

    monkeypatch.setattr(settings, "payments_dry_run", False)
    correr(db)

    pago = db.query(ReconciliationPayment).one()          # mismo registro, no uno nuevo
    assert pago.status == "ENVIADO"


def test_si_el_banco_falla_queda_registrado_el_error(db, servicios, motor_real):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.error_pago = RuntimeError("Interbanking no disponible")
    rec = agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")

    res = correr(db)

    assert res["errores"] == 1 and res["enviados"] == 0
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "ERROR"
    assert pago.error_message == "Interbanking no disponible"
    db.refresh(rec)
    assert rec.status == "A_VERIFICAR"                    # no se marca pagado


def test_un_pago_con_error_se_reintenta_en_la_corrida_siguiente(db, servicios, motor_real):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    servicios.error_pago = RuntimeError("timeout")
    agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")
    correr(db)

    servicios.error_pago = None
    res = correr(db)

    assert res["enviados"] == 1
    assert db.query(ReconciliationPayment).one().status == "ENVIADO"


def test_solo_se_pagan_los_registros_de_la_fecha_pedida(db, servicios, motor_encendido):
    from conftest import OTRA_FECHA
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501"),
                          agencia(2, "A002", "0110012820000034567803")]
    agencia_con_saldo_a_favor(db, client_id=1)
    crear_registro(db, client_id=2, agency_number="A002", fecha=OTRA_FECHA,
                   adeudado="0", depositado="900")

    res = correr(db, FECHA)

    assert res["simulados"] == 1
    assert db.query(ReconciliationPayment).one().client_id == 1


# ─────────────────────────────────────────────────────────────────────────────
# Por Tesorería (H-216): el pago no sale directo al banco, va en un lote a aprobar
# ─────────────────────────────────────────────────────────────────────────────
from app.models.reconciliation_record import ReconciliationRecord
from app.services import tesoreria_client

CLAVE_TESO = "clave-teso"
AVISO = "/internal/conciliacion/tesoreria/resultado"


class TesoreriaFalsa:
    def __init__(self):
        self.lotes, self.caida, self.rechazar = [], False, {}

    def __call__(self, referencia, descripcion, pagos):
        if self.caida:
            raise tesoreria_client.TesoreriaNoDisponible("connection refused")
        self.lotes.append({"referencia": referencia, "pagos": pagos})
        ok = [p for p in pagos if p["referencia_externa"] not in self.rechazar]
        return {"codigo": f"LOT-2026-{len(self.lotes):05d}",
                "pagos": [{"referencia_externa": p["referencia_externa"], "estado": "PENDIENTE"} for p in ok],
                "rechazados": [{"referencia_externa": r, "motivo": m} for r, m in self.rechazar.items()]}


@pytest.fixture
def teso(monkeypatch):
    monkeypatch.setattr(settings, "auto_payments_enabled", True)
    monkeypatch.setattr(settings, "payments_dry_run", True)          # no aplica con Tesorería
    monkeypatch.setattr(settings, "payments_via_tesoreria", True)
    monkeypatch.setattr(settings, "tesoreria_internal_api_key", CLAVE_TESO)
    falsa = TesoreriaFalsa()
    monkeypatch.setattr(tesoreria_client, "enviar_lote", falsa)
    return falsa


def _avisar(client, lote, rec, estado, motivo="", clave=CLAVE_TESO):
    return client.post(AVISO, headers={"X-Api-Key": clave}, json={
        "lote": lote, "pagos": [{"referencia_externa": f"rec-{rec.id}", "estado": estado, "motivo": motivo}]})


def test_por_tesoreria_arma_un_lote_y_no_paga_directo(db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501", tax_id="30-11111111-7")]
    rec = agencia_con_saldo_a_favor(db, adeudado="1000", depositado="1500")

    res = correr(db)

    assert res["en_tesoreria"] == 1 and res["lote"] == "LOT-2026-00001" and res["errores"] == 0
    assert servicios.pagos_ejecutados == []
    p = teso.lotes[0]["pagos"][0]
    assert p == {"referencia_externa": f"rec-{rec.id}", "beneficiario": "Agencia A001 S.A.", "documento": "30111111117",
                 "cbu": "0720099620000001234501", "monto": 500.0, "concepto": "Pago Capresca A001 2026-03-10"}
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "EN_TESORERIA" and pago.tesoreria_lote == "LOT-2026-00001"
    correr(db)
    assert len(teso.lotes) == 1                                      # no lo manda dos veces


def test_confirmado_por_tesoreria_queda_pagado(client, db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    rec = agencia_con_saldo_a_favor(db)
    correr(db)

    assert _avisar(client, "LOT-2026-00001", rec, "CONFIRMADO").json()["pagados"] == 1
    db.expire_all()
    assert db.query(ReconciliationPayment).one().status == "ENVIADO"
    assert db.get(ReconciliationRecord, rec.id).status == "PAGADO"
    assert _avisar(client, "LOT-2026-00001", rec, "CONFIRMADO").json()["ignorados"] == 1


def test_el_aviso_exige_la_clave(client, db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    rec = agencia_con_saldo_a_favor(db)
    correr(db)
    assert _avisar(client, "LOT-2026-00001", rec, "CONFIRMADO", clave="otra").status_code == 401
    assert db.query(ReconciliationPayment).one().status == "EN_TESORERIA"


def test_excluido_queda_observado_y_no_se_reenvia_solo(client, db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    rec = agencia_con_saldo_a_favor(db)
    correr(db)
    assert _avisar(client, "LOT-VIEJO", rec, "EXCLUIDO").json()["ignorados"] == 1    # otro lote: no aplica

    _avisar(client, "LOT-2026-00001", rec, "EXCLUIDO", "Monto a revisar")
    db.expire_all()
    pago = db.query(ReconciliationPayment).one()
    assert pago.status == "OBSERVADO" and "Monto a revisar" in pago.error_message
    correr(db)
    assert len(teso.lotes) == 1
    # Si el tesorero lo reintentó allá y se acreditó, igual queda pagado.
    _avisar(client, "LOT-2026-00001", rec, "CONFIRMADO")
    db.expire_all()
    assert db.query(ReconciliationPayment).one().status == "ENVIADO"


def test_tesoreria_caida_deja_error_y_se_reintenta_en_la_proxima_corrida(db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    agencia_con_saldo_a_favor(db)
    teso.caida = True
    assert correr(db)["errores"] == 1
    assert db.query(ReconciliationPayment).one().status == "ERROR"
    teso.caida = False
    assert correr(db)["en_tesoreria"] == 1


def test_rechazo_de_tesoreria_al_cargar(db, servicios, teso):
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501"), agencia(2, "A002", "0720099620000001234502")]
    r1 = agencia_con_saldo_a_favor(db, client_id=1, agency_number="A001")
    r2 = agencia_con_saldo_a_favor(db, client_id=2, agency_number="A002")
    teso.rechazar = {f"rec-{r1.id}": "CBU inválido.", f"rec-{r2.id}": "Ya está en el lote LOT-2026-00009 (PENDIENTE)."}
    res = correr(db)
    assert res["errores"] == 1 and res["en_tesoreria"] == 1
    por_rec = {p.reconciliation_record_id: p for p in db.query(ReconciliationPayment).all()}
    assert por_rec[r1.id].status == "ERROR" and "CBU inválido" in por_rec[r1.id].error_message
    assert por_rec[r2.id].status == "EN_TESORERIA" and por_rec[r2.id].tesoreria_lote == "LOT-2026-00009"
