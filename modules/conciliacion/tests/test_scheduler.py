"""Arranque de la app, scheduler del cruce automático y seed de demo."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, scheduler, seed_demo
from app.config import settings
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_status_history import ReconciliationStatusHistory
from app.services import cbu_cache_service
from conftest import FECHA, TestSession, agencia


class RelojFijo:
    """`datetime` congelado: el cruce automático no debe depender del día real."""
    AHORA = datetime(2026, 3, 10, 9, 0, 0)

    @staticmethod
    def now(tz=None):
        return RelojFijo.AHORA


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan de la app
# ─────────────────────────────────────────────────────────────────────────────
def test_el_arranque_reconstruye_el_cache_e_inicia_el_scheduler(monkeypatch, servicios, db):
    eventos = []
    servicios.agencias = [agencia(1, "A001", "0720099620000001234501")]
    monkeypatch.setattr(main, "SessionLocal", lambda: TestSession())
    monkeypatch.setattr(scheduler, "start", lambda: eventos.append("start"))
    monkeypatch.setattr(scheduler, "stop", lambda: eventos.append("stop"))

    with TestClient(main.app) as c:
        assert c.get("/health").status_code == 200

    assert eventos == ["start", "stop"]
    assert len(cbu_cache_service.get_all(db)) == 1


def test_el_arranque_tolera_que_falle_el_cache_y_el_scheduler(monkeypatch, capsys):
    async def _explota(db):
        raise RuntimeError("clientes no responde")

    def _falla_scheduler():
        raise RuntimeError("no arranca APScheduler")

    monkeypatch.setattr(main, "SessionLocal", lambda: TestSession())
    monkeypatch.setattr(main.cbu_cache_service, "rebuild_cache", _explota)
    monkeypatch.setattr(scheduler, "start", _falla_scheduler)
    monkeypatch.setattr(scheduler, "stop", lambda: None)

    with TestClient(main.app) as c:
        assert c.get("/health").json()["status"] == "ok"

    salida = capsys.readouterr().out
    assert "could not rebuild CBU cache" in salida
    assert "no se pudo iniciar el scheduler" in salida


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────────────
class SchedulerFalso:
    creados: list["SchedulerFalso"] = []

    def __init__(self, timezone=None):
        self.timezone = timezone
        self.jobs = []
        self.arrancado = False
        self.apagado = False
        SchedulerFalso.creados.append(self)

    def add_job(self, func, trigger, **kw):
        self.jobs.append((func, trigger, kw))

    def start(self):
        self.arrancado = True

    def shutdown(self, wait=True):
        self.apagado = True


@pytest.fixture
def scheduler_falso(monkeypatch):
    SchedulerFalso.creados = []
    monkeypatch.setattr(scheduler, "_scheduler", None)
    monkeypatch.setattr(scheduler, "BackgroundScheduler", SchedulerFalso)
    monkeypatch.setattr(scheduler, "datetime", RelojFijo)
    return SchedulerFalso


def test_el_scheduler_registra_el_job_del_cruce(scheduler_falso, monkeypatch):
    monkeypatch.setattr(settings, "auto_match_enabled", True)
    monkeypatch.setattr(settings, "auto_match_interval_minutes", 30)

    scheduler.start()

    sch = scheduler_falso.creados[0]
    assert sch.arrancado is True and sch.timezone == settings.scheduler_timezone
    func, trigger, kw = sch.jobs[0]
    assert func is scheduler._run_auto_match and trigger == "interval"
    assert kw["minutes"] == 30 and kw["id"] == "auto_match"
    assert kw["next_run_time"] == RelojFijo.AHORA       # corre una vez al arrancar
    assert kw["max_instances"] == 1 and kw["coalesce"] is True

    scheduler.stop()
    assert sch.apagado is True


def test_con_el_cruce_automatico_apagado_no_se_crea_scheduler(scheduler_falso, monkeypatch):
    monkeypatch.setattr(settings, "auto_match_enabled", False)

    scheduler.start()

    assert scheduler_falso.creados == []
    scheduler.stop()                                   # sin scheduler, no rompe


def test_el_cruce_automatico_procesa_hoy_y_los_dias_de_lookback(monkeypatch, db):
    fechas, pagos = [], []

    async def _load_date(sesion, fecha):
        fechas.append(fecha)
        return [], []

    async def _run_payments(sesion, fecha):
        pagos.append(fecha)
        return {"enabled": False}

    monkeypatch.setattr(scheduler, "datetime", RelojFijo)
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: TestSession())
    monkeypatch.setattr(scheduler.matching_service, "load_date", _load_date)
    monkeypatch.setattr(scheduler.payments_service, "run_payments", _run_payments)
    monkeypatch.setattr(settings, "auto_match_lookback_days", 2)

    scheduler._run_auto_match()

    hoy = RelojFijo.AHORA.date()
    assert fechas == [hoy, hoy - timedelta(days=1), hoy - timedelta(days=2)]
    assert pagos == fechas


def test_si_falla_el_cruce_de_un_dia_sigue_con_los_pagos_y_el_resto(monkeypatch, caplog):
    pagos = []

    async def _load_date(sesion, fecha):
        raise RuntimeError("interbanking caído")

    async def _run_payments(sesion, fecha):
        pagos.append(fecha)
        raise RuntimeError("banco caído")

    monkeypatch.setattr(scheduler, "datetime", RelojFijo)
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: TestSession())
    monkeypatch.setattr(scheduler.matching_service, "load_date", _load_date)
    monkeypatch.setattr(scheduler.payments_service, "run_payments", _run_payments)
    monkeypatch.setattr(settings, "auto_match_lookback_days", 0)

    scheduler._run_auto_match()                        # no propaga

    assert pagos == [RelojFijo.AHORA.date()]
    assert "Cruce automático falló" in caplog.text
    assert "Motor de pagos falló" in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# Seed de demo
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def seed_fijo(monkeypatch):
    monkeypatch.setattr(seed_demo, "SessionLocal", lambda: TestSession())
    monkeypatch.setattr(seed_demo, "TODAY", FECHA)
    monkeypatch.setattr(seed_demo, "NOW", datetime(2026, 3, 10, 12, tzinfo=timezone.utc))


def test_el_seed_carga_los_seis_escenarios(seed_fijo, db, capsys):
    seed_demo.run()

    registros = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == FECHA).all()
    assert len(registros) == 6
    por_num = {r.agency_number: r for r in registros}
    assert por_num["A001"].status == "CONSOLIDADO" and float(por_num["A001"].importe_neto) == 0.0
    assert por_num["A003"].status == "CONSOLIDADO_MANUAL"
    assert float(por_num["A006"].importe_neto) == -8000.0
    assert db.query(ReconciliationIbLink).count() == 5
    assert db.query(ReconciliationStatusHistory).count() == 3   # sólo los no A_VERIFICAR
    assert len(cbu_cache_service.get_all(db)) == 6
    assert "registros demo cargados" in capsys.readouterr().out


def test_el_seed_se_puede_correr_dos_veces(seed_fijo, db, capsys):
    seed_demo.run()
    seed_demo.run()

    assert db.query(ReconciliationRecord).count() == 6
    assert "Eliminando para re-seed" in capsys.readouterr().out


def test_el_seed_aborta_con_codigo_1_si_los_datos_estan_mal(seed_fijo, monkeypatch):
    monkeypatch.setattr(seed_demo, "AGENCIES", [{"client_id": 1}])   # sin "cbu"

    with pytest.raises(SystemExit) as e:
        seed_demo.run()

    assert e.value.code == 1


def test_el_seed_usa_la_fecha_de_hoy_por_defecto():
    assert seed_demo.TODAY == date.today()
