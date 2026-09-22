"""
Scheduler de sincronización (respeta kill switch y salud del share) y cliente
fire-and-forget de notificaciones.
"""
import httpx

from app import scheduler
from app.config import settings
from app.services import smb_health, sync_service
from app.services.notifications_client import NotificationsClient


# ── Scheduler ─────────────────────────────────────────────────────────────────

def test_los_grupos_solo_agrupan_tablas_sincronizables():
    from app.sync_spec import SYNCABLE_TABLES
    assert set(scheduler.GROUPS) == {"caja", "creditos", "maestros"}
    todas = {t for tablas in scheduler.GROUPS.values() for t in tablas}
    assert todas <= set(SYNCABLE_TABLES)


def test_el_scheduler_no_sincroniza_con_la_integracion_apagada(monkeypatch, share):
    monkeypatch.setattr(settings, "integration_enabled", False)
    llamadas = []
    monkeypatch.setattr(sync_service, "sync_table", lambda *a, **k: llamadas.append(a))
    scheduler._run_group("caja")
    assert llamadas == []


def test_el_scheduler_no_sincroniza_si_el_share_no_esta_montado(monkeypatch):
    monkeypatch.setattr(settings, "smb_mount_root", "/ruta/inexistente")
    llamadas = []
    monkeypatch.setattr(sync_service, "sync_table", lambda *a, **k: llamadas.append(a))
    assert smb_health.is_available() is False
    scheduler._run_group("caja")
    assert llamadas == []


def test_el_scheduler_sincroniza_todas_las_tablas_del_grupo(monkeypatch, share, db):
    llamadas = []
    monkeypatch.setattr(sync_service, "sync_table",
                        lambda sesion, tabla, origin_module=None: llamadas.append((tabla, origin_module)))
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    scheduler._run_group("maestros")
    assert [t for t, _ in llamadas] == scheduler.GROUPS["maestros"]
    assert {o for _, o in llamadas} == {"legacy-scheduler"}


def test_el_scheduler_no_arranca_si_esta_desactivado(monkeypatch):
    monkeypatch.setattr(settings, "sync_enabled", False)
    scheduler.start()
    assert scheduler._scheduler is None


def test_el_scheduler_registra_un_job_por_grupo_con_cadencia_positiva(monkeypatch):
    monkeypatch.setattr(settings, "sync_enabled", True)
    monkeypatch.setattr(settings, "sync_caja_minutes", 10)
    monkeypatch.setattr(settings, "sync_creditos_minutes", 60)
    monkeypatch.setattr(settings, "sync_maestros_minutes", 0)   # grupo desactivado
    try:
        scheduler.start()
        jobs = {j.id for j in scheduler._scheduler.get_jobs()}
        assert jobs == {"sync_caja", "sync_creditos"}
    finally:
        scheduler.stop()
    assert scheduler._scheduler is None


def test_stop_es_seguro_sin_scheduler_arrancado():
    scheduler._scheduler = None
    scheduler.stop()      # no debe romper
    assert scheduler._scheduler is None


# ── Cliente de notificaciones ─────────────────────────────────────────────────

def test_el_cliente_arma_el_payload_esperado(monkeypatch):
    enviados = {}

    class ClienteFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json, timeout):
            enviados.update(url=url, json=json, timeout=timeout)

    monkeypatch.setattr(httpx, "Client", ClienteFalso)
    NotificationsClient().notify(user_id=7, title="T", message="M", module="legacy",
                                 entity_type="outbox", entity_id=3,
                                 redirect_path="/modules/legacy")

    assert enviados["url"].endswith("/internal/notifications")
    assert enviados["timeout"] == 3.0
    aviso = enviados["json"]["notifications"][0]
    assert aviso == {"user_id": 7, "title": "T", "message": "M", "module": "legacy",
                     "entity_type": "outbox", "entity_id": 3,
                     "redirect_path": "/modules/legacy", "created_by_module": "legacy"}


def test_una_falla_al_notificar_no_se_propaga(monkeypatch):
    def _explota():
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx, "Client", _explota)
    # no debe levantar excepción: es fire-and-forget
    NotificationsClient().notify(user_id=7, title="T", message="M", module="legacy")
