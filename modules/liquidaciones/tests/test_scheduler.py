"""Ingesta automática desde el inbox y arranque/parada del scheduler."""
import pytest
from fastapi.testclient import TestClient

from app import scheduler
from app.main import app


class LoteFalso:
    def __init__(self, status="ENVIADO_CONCILIACION", id=1):
        self.status = status
        self.id = id


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    """Apunta el scheduler a un inbox temporal con una sesión de base inocua."""
    monkeypatch.setattr(scheduler.settings, "inbox_dir", str(tmp_path / "inbox"))
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: _SesionFalsa())
    return tmp_path / "inbox"


class _SesionFalsa:
    cerradas = 0

    def close(self):
        type(self).cerradas += 1


def _crear_dirs(inbox):
    base, procesados, errores = scheduler._dirs()
    return inbox, inbox / "processed", inbox / "error"


def test_crea_el_arbol_de_carpetas_del_inbox(inbox):
    base, procesados, errores = _crear_dirs(inbox)
    assert base.is_dir() and procesados.is_dir() and errores.is_dir()


def test_inbox_vacio_no_hace_nada(inbox, monkeypatch):
    llamadas = []
    monkeypatch.setattr(scheduler, "process_from_path", lambda *a: llamadas.append(a))
    scheduler.scan_inbox()
    assert llamadas == []


def test_procesa_los_zips_y_los_mueve_a_processed(inbox, monkeypatch):
    base, procesados, errores = _crear_dirs(inbox)
    (base / "LIQ0315.zip").write_bytes(b"zip")
    (base / "LIQ0316.ZIP").write_bytes(b"zip")
    (base / "notas.txt").write_text("se ignora")

    vistos = []

    def procesar(db, path, user_id):
        vistos.append((path, user_id))
        return LoteFalso()

    monkeypatch.setattr(scheduler, "process_from_path", procesar)
    scheduler.scan_inbox()

    assert len(vistos) == 2 and vistos[0][1] == scheduler.settings.inbox_default_user_id
    assert sorted(p.name for p in procesados.iterdir()) == ["LIQ0315.zip", "LIQ0316.ZIP"]
    assert list(errores.iterdir()) == []
    assert (base / "notas.txt").exists()   # lo que no es ZIP queda quieto


def test_un_lote_en_error_va_a_la_carpeta_error(inbox, monkeypatch):
    base, procesados, errores = _crear_dirs(inbox)
    (base / "LIQ0315.zip").write_bytes(b"zip")
    monkeypatch.setattr(scheduler, "process_from_path", lambda *a: LoteFalso(status="ERROR"))
    scheduler.scan_inbox()
    assert [p.name for p in errores.iterdir()] == ["LIQ0315.zip"]


def test_una_excepcion_del_pipeline_tambien_manda_el_zip_a_error(inbox, monkeypatch):
    base, procesados, errores = _crear_dirs(inbox)
    (base / "LIQ0315.zip").write_bytes(b"zip")

    def explotar(*a):
        raise RuntimeError("base de datos caída")

    monkeypatch.setattr(scheduler, "process_from_path", explotar)
    scheduler.scan_inbox()
    assert [p.name for p in errores.iterdir()] == ["LIQ0315.zip"]


def test_si_tampoco_se_puede_mover_a_error_no_se_propaga(inbox, monkeypatch):
    base, _, _ = _crear_dirs(inbox)
    (base / "LIQ0315.zip").write_bytes(b"zip")
    monkeypatch.setattr(scheduler, "process_from_path", lambda *a: LoteFalso())

    def no_mover(origen, destino):
        raise OSError("permiso denegado")

    monkeypatch.setattr(scheduler.shutil, "move", no_mover)
    scheduler.scan_inbox()   # no debe romper el ciclo del scheduler
    assert (base / "LIQ0315.zip").exists()


def test_las_carpetas_processed_y_error_no_se_reprocesan(inbox, monkeypatch):
    base, procesados, _ = _crear_dirs(inbox)
    (procesados / "viejo.zip").write_bytes(b"zip")
    llamadas = []
    monkeypatch.setattr(scheduler, "process_from_path",
                        lambda *a: llamadas.append(a) or LoteFalso())
    scheduler.scan_inbox()
    assert llamadas == []   # sólo se mira el primer nivel del inbox


# ───────────────────────── arranque / parada ─────────────────────────

def test_con_la_ingesta_deshabilitada_no_arranca_el_scheduler(inbox, monkeypatch):
    monkeypatch.setattr(scheduler.settings, "inbox_enabled", False)
    monkeypatch.setattr(scheduler, "_scheduler", None)
    scheduler.start()
    assert scheduler._scheduler is None


def test_arranca_y_para_programando_el_cron_diario(inbox, monkeypatch):
    monkeypatch.setattr(scheduler.settings, "inbox_enabled", True)
    monkeypatch.setattr(scheduler.settings, "inbox_scan_on_startup", False)
    try:
        scheduler.start()
        assert scheduler._scheduler.get_job("inbox_scan") is not None
    finally:
        scheduler.stop()
        monkeypatch.setattr(scheduler, "_scheduler", None)


def test_el_escaneo_de_arranque_no_tumba_el_servicio(inbox, monkeypatch):
    monkeypatch.setattr(scheduler.settings, "inbox_enabled", True)
    monkeypatch.setattr(scheduler.settings, "inbox_scan_on_startup", True)

    def explotar():
        raise RuntimeError("inbox inaccesible")

    monkeypatch.setattr(scheduler, "scan_inbox", explotar)
    try:
        scheduler.start()
        assert scheduler._scheduler is not None
    finally:
        scheduler.stop()
        monkeypatch.setattr(scheduler, "_scheduler", None)


def test_stop_sin_scheduler_es_inocuo(monkeypatch):
    monkeypatch.setattr(scheduler, "_scheduler", None)
    scheduler.stop()


# ───────────────────────── lifespan de la app ─────────────────────────

def test_el_lifespan_arranca_y_detiene_el_scheduler(monkeypatch):
    eventos = []
    monkeypatch.setattr(scheduler, "start", lambda: eventos.append("start"))
    monkeypatch.setattr(scheduler, "stop", lambda: eventos.append("stop"))
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
    assert eventos == ["start", "stop"]


def test_si_el_scheduler_no_arranca_la_app_igual_levanta(monkeypatch):
    def explotar():
        raise RuntimeError("APScheduler no disponible")

    monkeypatch.setattr(scheduler, "start", explotar)
    monkeypatch.setattr(scheduler, "stop", lambda: None)
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"


def test_una_carpeta_con_nombre_de_zip_se_saltea(inbox, monkeypatch):
    base, procesados, _ = _crear_dirs(inbox)
    (base / "carpeta.zip").mkdir()
    llamadas = []
    monkeypatch.setattr(scheduler, "process_from_path",
                        lambda *a: llamadas.append(a) or LoteFalso())
    scheduler.scan_inbox()
    assert llamadas == [] and (base / "carpeta.zip").is_dir()


def test_si_el_inbox_desaparece_el_escaneo_se_corta_sin_error(inbox, monkeypatch):
    _crear_dirs(inbox)

    def desaparecido(_path):
        raise FileNotFoundError("el share no está montado")

    monkeypatch.setattr(scheduler.os, "listdir", desaparecido)
    scheduler.scan_inbox()   # no propaga: el cron sigue vivo para el próximo ciclo
