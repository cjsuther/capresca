"""Endpoints internos (módulo a módulo), autenticados con X-Api-Key."""
from datetime import date

import pytest

from app.models.batch import LiquidacionBatch
from app.models.procesada import LiquidacionProcesada
from app.routers import internal as internal_mod
from factories import zip_coherente

URL_UPLOAD = "/internal/liquidaciones/upload"


def _archivo(nombre="LIQ0315.zip", contenido=None):
    return {"file": (nombre, contenido if contenido is not None else zip_coherente(),
                     "application/zip")}


def test_upload_interno_procesa_y_devuelve_el_resumen_del_lote(client, hk, servicios):
    r = client.post(URL_UPLOAD, headers=hk, files=_archivo())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ENVIADO_CONCILIACION"
    assert cuerpo["total_detail_records"] == 1 and cuerpo["total_agencies"] == 1
    assert cuerpo["error_message"] is None
    assert set(cuerpo) == {"id", "status", "error_message",
                           "total_detail_records", "total_agencies"}


def test_el_lote_interno_queda_a_nombre_del_usuario_sistema(client, hk, db):
    r = client.post(URL_UPLOAD, headers=hk, files=_archivo())
    lote = db.query(LiquidacionBatch).filter_by(id=r.json()["id"]).one()
    assert lote.created_by == 0


def test_api_key_invalida_da_401(client):
    r = client.post(URL_UPLOAD, headers={"X-Api-Key": "otra-cosa"}, files=_archivo())
    assert r.status_code == 401 and r.json()["detail"] == "API key inválida"


def test_sin_api_key_falta_el_header_obligatorio(client):
    r = client.post(URL_UPLOAD, files=_archivo())
    assert r.status_code == 422   # Header(...) obligatorio: no llega a evaluarse la clave


def test_api_key_no_configurada_devuelve_503(client, hk, monkeypatch):
    monkeypatch.setattr(internal_mod.settings, "internal_api_key", "")
    r = client.post(URL_UPLOAD, headers=hk, files=_archivo())
    assert r.status_code == 503 and r.json()["detail"] == "API key no configurada"


def test_upload_interno_rechaza_lo_que_no_sea_zip(client, hk):
    r = client.post(URL_UPLOAD, headers=hk, files=_archivo(nombre="liquidacion.txt",
                                                           contenido=b"hola"))
    assert r.status_code == 400 and r.json()["detail"] == "El archivo debe ser un ZIP"


def test_upload_interno_de_un_zip_roto_devuelve_el_lote_en_error(client, hk):
    r = client.post(URL_UPLOAD, headers=hk, files=_archivo(contenido=b"no soy un zip"))
    assert r.status_code == 200 and r.json()["status"] == "ERROR"
    assert r.json()["error_message"]


# ───────────────────────── totales por agencia ─────────────────────────

def _lote_con_procesadas(db, filas, operation_date=date(2025, 3, 15)):
    lote = LiquidacionBatch(zip_filename="LIQ.zip", status="ENVIADO_CONCILIACION",
                            created_by=7, operation_date=operation_date)
    db.add(lote)
    db.flush()
    for i, (agen, total, premios, recaudacion, comision) in enumerate(filas):
        db.add(LiquidacionProcesada(
            batch_id=lote.id, n_agen=agen, c_juego=7, n_sorteo=i, modalidad=0, moneda="$",
            recaudacion=recaudacion, premios=premios, comision=comision, fdo_gtia="0",
            ing_brutos="0", debitos="0", creditos="0", total=total, no_recibo=1))
    db.commit()
    return lote


def test_totales_por_agencia_suman_todos_los_juegos_del_lote(client, db, api_key):
    lote = _lote_con_procesadas(db, [
        ("000123", "1000.00", "200.00", "1200.00", "120.00"),
        ("000123", "500.00", "100.00", "600.00", "60.00"),
        ("000456", "300.00", "0.00", "300.00", "30.00"),
    ])
    r = client.get(f"/internal/liquidaciones/batch/{lote.id}/agency-totals", headers=api_key).json()

    assert r["batch_id"] == lote.id and r["operation_date"] == "2025-03-15"
    assert [a["agency_number"] for a in r["agencies"]] == ["000123", "000456"]  # ordenadas
    primera = r["agencies"][0]
    assert primera["total"] == 1500.0 and primera["premios"] == 300.0
    assert primera["adeudado"] == 1200.0   # total - premios
    assert primera["recaudacion"] == 1800.0 and primera["comision"] == 180.0


def test_totales_por_agencia_recortan_los_espacios_del_numero(client, db, api_key):
    lote = _lote_con_procesadas(db, [("123   ", "10.00", "0.00", "10.00", "0.00")])
    r = client.get(f"/internal/liquidaciones/batch/{lote.id}/agency-totals", headers=api_key).json()
    assert r["agencies"][0]["agency_number"] == "123"


def test_totales_de_un_lote_sin_procesadas_ni_fecha(client, db, api_key):
    lote = _lote_con_procesadas(db, [], operation_date=None)
    r = client.get(f"/internal/liquidaciones/batch/{lote.id}/agency-totals", headers=api_key).json()
    assert r["agencies"] == [] and r["operation_date"] is None


def test_totales_de_un_lote_inexistente_da_404(client, api_key):
    r = client.get("/internal/liquidaciones/batch/999/agency-totals", headers=api_key)
    assert r.status_code == 404 and r.json()["detail"] == "Lote no encontrado"


def test_los_totales_por_agencia_exigen_api_key(client, db, api_key):
    """nginx publica /internal/liquidaciones/ hacia afuera: TODO el router pide X-Api-Key."""
    lote = _lote_con_procesadas(db, [("000123", "10.00", "0.00", "10.00", "0.00")])
    url = f"/internal/liquidaciones/batch/{lote.id}/agency-totals"
    assert client.get(url).status_code == 422                                   # falta el header
    assert client.get(url, headers={"X-Api-Key": "otra"}).status_code == 401    # clave incorrecta
    assert client.get(url, headers=api_key).status_code == 200
