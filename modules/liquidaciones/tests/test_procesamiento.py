"""Pipeline de procesamiento del ZIP: estados del lote, persistencia y avisos."""
from datetime import date
from decimal import Decimal

import httpx

from app.models.archivo import LiquidacionArchivo
from app.models.batch import LiquidacionBatch
from app.models.detalle_raw import LiquidacionDetalleRaw
from app.models.procesada import LiquidacionProcesada
from app.models.resumen_raw import LiquidacionResumenRaw
from app.models.validacion import LiquidacionValidacion
from app.services import processing
from factories import construir_zip, detalle, resumen, zip_coherente


def test_lote_ok_queda_enviado_a_conciliacion(db, servicios):
    lote = processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)

    assert lote.status == "ENVIADO_CONCILIACION"
    assert lote.sent_to_conciliacion_at is not None and lote.error_message is None
    assert lote.operation_date == date(2025, 3, 15)
    assert lote.resumen_number == "777"
    assert lote.total_detail_records == 1 and lote.total_summary_records == 1
    assert lote.total_agencies == 1 and lote.created_by == 7
    assert servicios.envios == [lote.id]


def test_lote_ok_persiste_archivos_crudos_procesadas_y_validaciones(db):
    contenido = construir_zip(
        detalles=[detalle(c_codigo="1", importe="1000.00")],
        resumenes=[resumen(importe="1000.00")],
        extra={"MOVIMIENTOS.PDF": b"%PDF-mov", "RESUMENES.PDF": b"%PDF-res"},
    )
    lote = processing.process_from_upload(db, contenido, "LIQ0315.zip", user_id=7)

    archivos = db.query(LiquidacionArchivo).filter_by(batch_id=lote.id).all()
    assert {a.file_type for a in archivos} == {
        "ZIP", "DBF_DETALLE", "DBF_RESUMEN", "PDF_MOVIMIENTOS", "PDF_RESUMENES"}
    assert all(a.file_size == len(a.file_data) for a in archivos)

    crudo = db.query(LiquidacionDetalleRaw).filter_by(batch_id=lote.id).one()
    assert crudo.n_agen == "000123" and crudo.importe == Decimal("1000.00")
    assert db.query(LiquidacionResumenRaw).filter_by(batch_id=lote.id).one().f_movin == "0315"

    p = db.query(LiquidacionProcesada).filter_by(batch_id=lote.id).one()
    assert p.recaudacion == Decimal("1000.00") and p.total == Decimal("1000.00")
    assert p.operation_date == date(2025, 3, 15) and p.no_recibo == 777
    assert db.query(LiquidacionValidacion).filter_by(batch_id=lote.id).count() == 3


def test_estado_procesando_mientras_corre_el_pipeline(db, monkeypatch):
    """El lote se persiste como PROCESANDO antes de tocar el ZIP."""
    visto = {}
    original = processing.extract_zip

    def espiar(zip_bytes):
        visto["estado"] = db.query(LiquidacionBatch).one().status
        return original(zip_bytes)

    monkeypatch.setattr(processing, "extract_zip", espiar)
    processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)
    assert visto["estado"] == "PROCESANDO"


def test_conciliacion_caida_deja_el_lote_validado_con_el_error(db, servicios):
    servicios.error_conciliacion = httpx.ConnectError("conexión rechazada")
    lote = processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)

    assert lote.status == "VALIDADO" and lote.sent_to_conciliacion_at is None
    assert "falló envío a conciliación" in lote.error_message


def test_validacion_fallida_deja_el_lote_en_error(db):
    contenido = construir_zip(
        detalles=[detalle(c_codigo="1", importe="1000.00")],
        resumenes=[resumen(importe="999.00")],
    )
    lote = processing.process_from_upload(db, contenido, "LIQ0315.zip", user_id=7)

    assert lote.status == "ERROR"
    assert lote.error_message == "2 validación(es) fallida(s)"
    # el lote fallido igual conserva sus datos procesados para poder auditarlo
    assert db.query(LiquidacionProcesada).filter_by(batch_id=lote.id).count() == 1


def test_archivo_que_no_es_zip_deja_el_lote_en_error(db, servicios):
    lote = processing.process_from_upload(db, b"esto no es un zip", "roto.zip", user_id=7)

    assert lote.status == "ERROR" and lote.total_detail_records is None
    assert lote.processed_at is not None
    # el rollback descarta todo lo del intento fallido
    assert db.query(LiquidacionArchivo).count() == 0
    assert servicios.envios == []


def test_agencia_no_registrada_en_clientes_aborta_el_lote(db, servicios):
    servicios.agencias = {"000456"}
    lote = processing.process_from_upload(db, zip_coherente(agencia="000123"),
                                          "LIQ0315.zip", user_id=7)
    assert lote.status == "ERROR"
    assert "Agencia(s) no registrada(s)" in lote.error_message and "000123" in lote.error_message


def test_modulo_clientes_caido_aborta_el_lote(db, servicios):
    servicios.error_clientes = httpx.ConnectError("clientes no responde")
    lote = processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)
    assert lote.status == "ERROR"
    assert "No se pudo validar agencias contra módulo Clientes" in lote.error_message


def test_procesa_un_zip_desde_una_ruta_del_filesystem(db, inbox):
    ruta = inbox / "subcarpeta"
    ruta.mkdir(exist_ok=True)
    archivo = ruta / "LIQ0315.zip"
    archivo.write_bytes(zip_coherente())

    lote = processing.process_from_path(db, str(archivo), user_id=3)
    assert lote.status == "ENVIADO_CONCILIACION"
    assert lote.zip_filename == "LIQ0315.zip"   # se queda sólo con el nombre, no la ruta


def test_ruta_sin_barras_usa_el_nombre_tal_cual(db, tmp_path, monkeypatch):
    monkeypatch.setattr(processing, "read_zip_from_path", lambda p: zip_coherente())
    lote = processing.process_from_path(db, "LIQ0315.zip", user_id=3)
    assert lote.zip_filename == "LIQ0315.zip"


# ───────────────────────── notificaciones ─────────────────────────

def test_avisa_al_usuario_cuando_el_lote_se_envia(db, servicios):
    lote = processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)
    aviso = servicios.notificaciones[-1]
    assert aviso["user_id"] == 7 and aviso["title"] == "Liquidación procesada"
    assert aviso["module"] == "liquidaciones" and aviso["entity_id"] == lote.id
    assert aviso["redirect_path"] == f"/modules/liquidaciones/batches/{lote.id}"


def test_avisa_cuando_valido_pero_no_pudo_enviarse(db, servicios):
    servicios.error_conciliacion = RuntimeError("timeout")
    processing.process_from_upload(db, zip_coherente(), "LIQ0315.zip", user_id=7)
    assert servicios.notificaciones[-1]["title"] == "Liquidación validada"


def test_avisa_cuando_el_lote_falla(db, servicios):
    processing.process_from_upload(db, b"no-zip", "roto.zip", user_id=7)
    aviso = servicios.notificaciones[-1]
    assert aviso["title"] == "Liquidación con errores" and "no pudo procesarse" in aviso["message"]


def test_sin_usuario_no_se_notifica(db, servicios):
    lote = LiquidacionBatch(zip_filename="x.zip", status="VALIDADO", created_by=None)
    processing._notify_batch_outcome(lote)
    assert servicios.notificaciones == []
