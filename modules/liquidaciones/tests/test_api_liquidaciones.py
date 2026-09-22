"""API pública del módulo (detrás del gateway, que inyecta X-User-Id)."""
from datetime import date, datetime, timedelta

import pytest

from app.models.archivo import LiquidacionArchivo
from app.models.batch import LiquidacionBatch
from app.models.detalle_raw import LiquidacionDetalleRaw
from app.models.procesada import LiquidacionProcesada
from app.models.validacion import LiquidacionValidacion
from app.routers import liquidaciones as router_mod
from factories import zip_coherente


def _lote(db, *, status="VALIDADO", zip_filename="LIQ.zip", operation_date=None,
          creado=None, created_by=7):
    lote = LiquidacionBatch(
        zip_filename=zip_filename, status=status, created_by=created_by,
        operation_date=operation_date, created_at=creado or datetime(2025, 3, 15, 10, 0),
    )
    db.add(lote)
    db.commit()
    return lote


def test_health_no_pide_identidad(client):
    assert client.get("/health").json() == {"status": "ok", "service": "liquidaciones"}


def test_sin_header_de_usuario_la_api_rechaza(client):
    assert client.get("/api/liquidaciones/batches").status_code == 422


def test_header_de_usuario_no_numerico_da_401(client):
    r = client.get("/api/liquidaciones/batches", headers={"X-User-Id": "pepe"})
    assert r.status_code == 401 and r.json()["detail"] == "Header X-User-Id inválido"


# ───────────────────────── upload / process ─────────────────────────

def test_upload_procesa_el_zip_y_devuelve_el_lote(client, h, servicios):
    r = client.post("/api/liquidaciones/upload", headers=h,
                    files={"file": ("LIQ0315.zip", zip_coherente(), "application/zip")})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ENVIADO_CONCILIACION" and cuerpo["created_by"] == 7
    assert cuerpo["operation_date"] == "2025-03-15" and cuerpo["total_agencies"] == 1
    assert servicios.envios == [cuerpo["id"]]


def test_upload_rechaza_lo_que_no_sea_zip(client, h):
    r = client.post("/api/liquidaciones/upload", headers=h,
                    files={"file": ("liquidacion.rar", b"cualquier cosa", "application/x-rar")})
    assert r.status_code == 400 and r.json()["detail"] == "El archivo debe ser un ZIP"


def test_upload_acepta_la_extension_en_mayusculas(client, h):
    r = client.post("/api/liquidaciones/upload", headers=h,
                    files={"file": ("LIQ0315.ZIP", zip_coherente(), "application/zip")})
    assert r.status_code == 200 and r.json()["status"] == "ENVIADO_CONCILIACION"


def test_upload_de_un_zip_corrupto_devuelve_el_lote_en_error(client, h):
    r = client.post("/api/liquidaciones/upload", headers=h,
                    files={"file": ("LIQ0315.zip", b"no soy un zip", "application/zip")})
    assert r.status_code == 200 and r.json()["status"] == "ERROR"


def test_process_toma_el_zip_del_directorio_de_entrada(client, h, inbox):
    archivo = inbox / "LIQ0315.zip"
    archivo.write_bytes(zip_coherente())
    r = client.post("/api/liquidaciones/process", headers=h, json={"zip_path": str(archivo)})
    assert r.status_code == 200 and r.json()["status"] == "ENVIADO_CONCILIACION"
    # También se acepta el nombre relativo al INBOX_DIR
    r = client.post("/api/liquidaciones/process", headers=h, json={"zip_path": "LIQ0315.zip"})
    assert r.status_code == 200


def test_process_no_sale_del_directorio_de_entrada(client, h, tmp_path, inbox):
    """El path lo manda el cliente: fuera del INBOX_DIR se rechaza (lectura de archivos arbitrarios)."""
    afuera = tmp_path / "secreto.zip"
    afuera.write_bytes(zip_coherente())
    for ruta in (str(afuera), "../../etc/passwd", "/etc/hostname", str(inbox / "notas.txt")):
        r = client.post("/api/liquidaciones/process", headers=h, json={"zip_path": ruta})
        assert r.status_code == 400, ruta
        assert "no permitida" in r.json()["detail"]


def test_process_con_ruta_inexistente_da_400(client, h):
    r = client.post("/api/liquidaciones/process", headers=h, json={"zip_path": "no-existe.zip"})
    assert r.status_code == 400


# ───────────────────────── listados y filtros ─────────────────────────

def test_listado_ordena_por_fecha_de_creacion_descendente(client, h, db):
    _lote(db, zip_filename="viejo.zip", creado=datetime(2025, 1, 1))
    _lote(db, zip_filename="nuevo.zip", creado=datetime(2025, 6, 1))
    nombres = [b["zip_filename"] for b in client.get("/api/liquidaciones/batches", headers=h).json()]
    assert nombres == ["nuevo.zip", "viejo.zip"]


def test_listado_filtra_por_estado(client, h, db):
    _lote(db, status="ERROR", zip_filename="fallido.zip")
    _lote(db, status="ENVIADO_CONCILIACION", zip_filename="ok.zip")
    r = client.get("/api/liquidaciones/batches", headers=h, params={"status": "ERROR"}).json()
    assert [b["zip_filename"] for b in r] == ["fallido.zip"]


def test_listado_filtra_por_rango_de_fecha_de_operacion(client, h, db):
    _lote(db, zip_filename="enero.zip", operation_date=date(2025, 1, 10))
    _lote(db, zip_filename="marzo.zip", operation_date=date(2025, 3, 10))
    _lote(db, zip_filename="junio.zip", operation_date=date(2025, 6, 10))

    r = client.get("/api/liquidaciones/batches", headers=h,
                   params={"date_from": "2025-02-01", "date_to": "2025-05-01"}).json()
    assert [b["zip_filename"] for b in r] == ["marzo.zip"]


def test_listado_pagina_con_limit_y_offset(client, h, db):
    for i in range(3):
        _lote(db, zip_filename=f"l{i}.zip", creado=datetime(2025, 1, 1) + timedelta(days=i))
    r = client.get("/api/liquidaciones/batches", headers=h,
                   params={"limit": 1, "offset": 1}).json()
    assert [b["zip_filename"] for b in r] == ["l1.zip"]


@pytest.mark.parametrize("params", [{"limit": 500}, {"offset": -1}])
def test_listado_valida_los_limites_de_paginado(client, h, params):
    assert client.get("/api/liquidaciones/batches", headers=h, params=params).status_code == 422


def test_detalle_de_un_lote_inexistente_da_404(client, h):
    r = client.get("/api/liquidaciones/batches/999", headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "Lote no encontrado"


def test_detalle_de_un_lote(client, h, db):
    lote = _lote(db, zip_filename="LIQ.zip")
    assert client.get(f"/api/liquidaciones/batches/{lote.id}", headers=h).json()["id"] == lote.id


# ───────────────────────── procesadas, validaciones y crudos ─────────────────────────

def _procesada(db, lote_id, n_agen="000123", c_juego=7, total="100.00"):
    p = LiquidacionProcesada(batch_id=lote_id, n_agen=n_agen, c_juego=c_juego, n_sorteo=1,
                             modalidad=0, moneda="$", recaudacion=total, premios="0",
                             comision="0", fdo_gtia="0", ing_brutos="0", debitos="0",
                             creditos="0", total=total, no_recibo=1)
    db.add(p)
    db.commit()
    return p


def test_procesadas_del_lote_se_pueden_filtrar_por_agencia(client, h, db):
    lote = _lote(db)
    _procesada(db, lote.id, n_agen="000123")
    _procesada(db, lote.id, n_agen="000456")
    otro = _lote(db, zip_filename="otro.zip")
    _procesada(db, otro.id, n_agen="000123")

    todas = client.get(f"/api/liquidaciones/batches/{lote.id}/detalle", headers=h).json()
    assert len(todas) == 2
    una = client.get(f"/api/liquidaciones/batches/{lote.id}/detalle", headers=h,
                     params={"agency": "000456"}).json()
    assert [p["n_agen"] for p in una] == ["000456"]


def test_procesadas_vienen_ordenadas_por_agencia_y_juego(client, h, db):
    lote = _lote(db)
    _procesada(db, lote.id, n_agen="000456", c_juego=1)
    _procesada(db, lote.id, n_agen="000123", c_juego=9)
    _procesada(db, lote.id, n_agen="000123", c_juego=2)
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/detalle", headers=h).json()
    assert [(p["n_agen"], p["c_juego"]) for p in r] == [("000123", 2), ("000123", 9), ("000456", 1)]


def test_validaciones_del_lote(client, h, db):
    lote = _lote(db)
    db.add(LiquidacionValidacion(batch_id=lote.id, validation_type="AGENCY_COUNT", passed=True,
                                 detail_message="ok"))
    db.add(LiquidacionValidacion(batch_id=lote.id, validation_type="DETAIL_VS_SUMMARY",
                                 agency_number="000123", passed=False, detail_message="no cuadra"))
    db.commit()
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/validaciones", headers=h).json()
    assert [v["validation_type"] for v in r] == ["AGENCY_COUNT", "DETAIL_VS_SUMMARY"]
    assert r[1]["passed"] is False


def test_crudos_del_lote_con_filtro_y_paginado(client, h, db):
    lote = _lote(db)
    for i, agen in enumerate(["000123", "000123", "000456"]):
        db.add(LiquidacionDetalleRaw(batch_id=lote.id, n_agen=agen, c_juego="7",
                                     d_juego="QUINIELA", n_sorteo=str(i), c_codigo="1",
                                     d_codigo="REC", d_operac="15/03/2025", importe="10.00"))
    db.commit()
    url = f"/api/liquidaciones/batches/{lote.id}/raw"
    assert len(client.get(url, headers=h).json()) == 3
    assert len(client.get(url, headers=h, params={"agency": "000123"}).json()) == 2
    assert len(client.get(url, headers=h, params={"limit": 1, "offset": 2}).json()) == 1
    assert client.get(url, headers=h, params={"limit": 501}).status_code == 422


# ───────────────────────── archivos adjuntos ─────────────────────────

def _archivo(db, lote_id, *, file_type="ZIP", nombre="LIQ.zip", data=b"contenido"):
    a = LiquidacionArchivo(batch_id=lote_id, file_type=file_type, original_filename=nombre,
                           file_data=data, file_size=len(data))
    db.add(a)
    db.commit()
    return a


def test_listado_de_adjuntos_no_expone_los_bytes(client, h, db):
    lote = _lote(db)
    _archivo(db, lote.id, file_type="ZIP")
    _archivo(db, lote.id, file_type="PDF_RESUMENES", nombre="res.pdf", data=b"%PDF")
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/archivos", headers=h).json()
    assert {a["file_type"] for a in r} == {"ZIP", "PDF_RESUMENES"}
    assert "file_data" not in r[0] and r[0]["file_size"] == 9


@pytest.mark.parametrize("file_type,content_type", [
    ("ZIP", "application/zip"),
    ("PDF_MOVIMIENTOS", "application/pdf"),
    ("PDF_RESUMENES", "application/pdf"),
    ("DBF_DETALLE", "application/octet-stream"),
    ("DESCONOCIDO", "application/octet-stream"),
])
def test_descarga_usa_el_content_type_del_tipo_de_archivo(client, h, db, file_type, content_type):
    lote = _lote(db)
    a = _archivo(db, lote.id, file_type=file_type, data=b"bytes-del-archivo")
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/archivos/{a.id}", headers=h)
    assert r.status_code == 200 and r.content == b"bytes-del-archivo"
    assert r.headers["content-type"].startswith(content_type)
    assert 'attachment; filename="LIQ.zip"' in r.headers["content-disposition"]


def test_no_se_puede_bajar_un_adjunto_de_otro_lote(client, h, db):
    lote = _lote(db)
    otro = _lote(db, zip_filename="otro.zip")
    ajeno = _archivo(db, otro.id)
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/archivos/{ajeno.id}", headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "Archivo no encontrado"


def test_adjunto_inexistente_da_404(client, h, db):
    lote = _lote(db)
    assert client.get(f"/api/liquidaciones/batches/{lote.id}/archivos/999",
                      headers=h).status_code == 404


def test_el_nombre_del_adjunto_viaja_sin_sanitizar_en_el_content_disposition(client, h, db):
    """TODO(bug): original_filename sale del ZIP y se interpola crudo en el header.

    Un ZIP con entradas tipo `../../etc/passwd` o con comillas embebidas termina en el
    Content-Disposition tal cual (el archivo se sirve desde la base, así que no hay
    lectura de disco, pero el nombre sugerido al navegador es atacable).
    """
    lote = _lote(db)
    a = _archivo(db, lote.id, nombre='../../etc/passwd')
    r = client.get(f"/api/liquidaciones/batches/{lote.id}/archivos/{a.id}", headers=h)
    assert r.headers["content-disposition"] == 'attachment; filename="../../etc/passwd"'


# ───────────────────────── reintento de envío ─────────────────────────

def test_reintento_envia_a_conciliacion_y_marca_el_lote(client, h, db, monkeypatch):
    enviados = []
    monkeypatch.setattr(router_mod, "send_to_conciliacion",
                        lambda db_, lote: enviados.append(lote.id))
    lote = _lote(db, status="VALIDADO")
    lote.error_message = "Validación OK pero falló envío a conciliación: timeout"
    db.commit()

    r = client.post(f"/api/liquidaciones/batches/{lote.id}/retry-conciliacion", headers=h)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ENVIADO_CONCILIACION" and cuerpo["error_message"] is None
    assert cuerpo["sent_to_conciliacion_at"] is not None
    assert enviados == [lote.id]


def test_reintento_fallido_deja_el_error_registrado_y_devuelve_500(client, h, db, monkeypatch):
    def explotar(db_, lote):
        raise RuntimeError("conciliación no responde")

    monkeypatch.setattr(router_mod, "send_to_conciliacion", explotar)
    lote = _lote(db, status="VALIDADO")

    r = client.post(f"/api/liquidaciones/batches/{lote.id}/retry-conciliacion", headers=h)
    assert r.status_code == 500 and r.json()["detail"] == "conciliación no responde"
    db.refresh(lote)
    assert lote.status == "VALIDADO"
    assert lote.error_message == "Error al enviar a conciliación: conciliación no responde"


@pytest.mark.parametrize("estado", ["ERROR", "ENVIADO_CONCILIACION", "PROCESANDO"])
def test_solo_se_reintenta_un_lote_validado(client, h, db, estado):
    lote = _lote(db, status=estado)
    r = client.post(f"/api/liquidaciones/batches/{lote.id}/retry-conciliacion", headers=h)
    assert r.status_code == 400 and estado in r.json()["detail"]


def test_reintento_sobre_un_lote_inexistente_da_404(client, h):
    assert client.post("/api/liquidaciones/batches/999/retry-conciliacion",
                       headers=h).status_code == 404


def test_el_username_del_gateway_es_opcional():
    from app.dependencies.auth import get_current_username
    assert get_current_username("cjsuther") == "cjsuther"
    assert get_current_username(None) is None
