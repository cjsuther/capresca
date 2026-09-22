"""
Drenado del outbox: dry-run, drenado real gated (ALLOW_REAL_DRAIN) y escritura en DBF,
que SIEMPRE ocurre sobre la copia sandbox y jamás sobre el share productivo.
"""
import os
from datetime import date

import pytest

from app.config import settings
from app.models.interaction_log import LegacyInteractionLog
from app.models.outbox import LegacyOutbox
from app.services import dbf_writer, outbox_service

PAYLOAD_PAGO = {
    "no_recibo": 5001,
    "cod_agencia": "A01",
    "fecha_pago": "2026-02-09",
    "total": "113400.00",
    "origen": "caja",
    "cajero": "jperez",
    "formas_pago": [{"moneda": "$", "importe": "113400.00", "origen": "efectivo",
                     "sno_recibo": 1}],
    "liquidaciones": [{"cod_agencia": "A01", "cod_juego": 3, "no_sorteo": 77}],
}


def _encolar(db, operation="aplicar_pago", payload=None, clave=None, database="caja"):
    fila, creada = outbox_service.enqueue(
        db, operation=operation, database=database,
        idempotency_key=clave or f"{operation}:5001",
        payload=payload if payload is not None else PAYLOAD_PAGO,
        origin_module="cajeros", origin_user_id=7,
    )
    return fila


@pytest.fixture
def sandbox_caja(sandbox, escribir_dbf):
    """Sandbox con las tres DBF de caja que toca el writer."""
    escribir_dbf(sandbox, "cajapagos", [
        {"NO_RECIBO": "4999", "COD_AGEN": "A01", "FECHA_PAGO": "01/02/2026"},
    ])
    escribir_dbf(sandbox, "cajaforpag", [])
    escribir_dbf(sandbox, "cajaliq", [
        {"COD_AGEN": "A01", "COD_JUEGO": "3", "NO_SORTEO": "77", "IMPORTE": "113400.00",
         "PAGADO": False, "FECHA_PAGO": "", "NO_RECIBO": ""},
        {"COD_AGEN": "A01", "COD_JUEGO": "3", "NO_SORTEO": "78", "IMPORTE": "100.00",
         "PAGADO": False, "FECHA_PAGO": "", "NO_RECIBO": ""},
    ])
    return sandbox


# ── Encolado ──────────────────────────────────────────────────────────────────

def test_enqueue_es_idempotente_por_clave(db):
    primera, creada1 = outbox_service.enqueue(
        db, operation="aplicar_pago", database="caja",
        idempotency_key="aplicar_pago:1", payload={"no_recibo": 1})
    segunda, creada2 = outbox_service.enqueue(
        db, operation="aplicar_pago", database="caja",
        idempotency_key="aplicar_pago:1", payload={"no_recibo": 999})
    assert creada1 is True and creada2 is False
    assert primera.id == segunda.id and segunda.payload == {"no_recibo": 1}
    assert db.query(LegacyOutbox).count() == 1


# ── Fechas legacy ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("2026-02-09", "09/02/2026"),
    (date(2026, 2, 9), "09/02/2026"),
    ("", ""), (None, ""),
    ("09/02/2026", "09/02/2026"),   # ya viene en formato legacy: se devuelve tal cual
])
def test_to_legacy_date(entrada, esperado):
    assert dbf_writer._to_legacy_date(entrada) == esperado


def test_path_del_writer_apunta_al_sandbox_no_al_share(sandbox):
    assert dbf_writer._path("cajapagos") == f"{sandbox}/caja/cajapagos.dbf"
    assert str(settings.smb_mount_root) not in dbf_writer._path("cajapagos")


def test_path_del_writer_falla_con_tabla_desconocida():
    with pytest.raises(ValueError, match="Tabla desconocida"):
        dbf_writer._path("inventada")


def test_el_writer_falla_si_la_dbf_sandbox_no_existe(sandbox):
    with pytest.raises(FileNotFoundError, match="DBF sandbox no encontrada"):
        dbf_writer._open("cajapagos")


def test_backup_sin_archivos_no_crea_nada(sandbox):
    assert dbf_writer._backup([str(sandbox / "caja" / "no_existe.dbf")]) is None
    assert not (sandbox / "_backup").exists()


def test_el_backup_incluye_el_memo_fpt_si_existe(sandbox, escribir_dbf):
    ruta = escribir_dbf(sandbox, "cajapagos", [])
    (sandbox / "caja" / "cajapagos.fpt").write_bytes(b"memo")
    destino = dbf_writer._backup([ruta])
    assert sorted(os.listdir(destino)) == ["cajapagos.dbf", "cajapagos.fpt"]


# ── Drenado real (sandbox) ────────────────────────────────────────────────────

def test_drenado_real_aplica_el_pago_en_las_tres_tablas(db, sandbox_caja, leer_dbf):
    fila = _encolar(db)
    r = outbox_service.drain_real(db)

    assert r["mode"] == "real_sandbox"
    assert (r["applied"], r["skipped"], r["failed"]) == (1, 0, 0)
    assert r["entries"][0]["result"]["rows"] == {"cajapagos": 1, "cajaforpag": 1, "cajaliq": 1}

    db.expire_all()
    fila = db.get(LegacyOutbox, fila.id)
    assert fila.status == "APPLIED" and fila.attempts == 1
    assert fila.applied_at is not None and fila.last_error is None

    pagos = leer_dbf(str(sandbox_caja / "caja" / "cajapagos.dbf"))
    assert [p["NO_RECIBO"] for p in pagos] == ["4999", "5001"]
    nuevo = pagos[1]
    assert nuevo["FECHA_PAGO"] == "09/02/2026" and nuevo["TOTAL"] == "113400.00"
    assert nuevo["PESOS"] == "113400.00" and nuevo["BONOS"] == "0"
    assert nuevo["CAJERO"] == "jperez"

    formas = leer_dbf(str(sandbox_caja / "caja" / "cajaforpag.dbf"))
    assert formas == [{"NO_RECIBO": "5001", "SNO_RECIBO": "1", "MONEDA": "$",
                       "ORIGEN": "efectivo", "FECHA_PAGO": "09/02/2026", "ANULADO": False}]

    liqs = leer_dbf(str(sandbox_caja / "caja" / "cajaliq.dbf"))
    pagada = [l for l in liqs if l["NO_SORTEO"] == "77"][0]
    intacta = [l for l in liqs if l["NO_SORTEO"] == "78"][0]
    assert pagada["PAGADO"] is True and pagada["NO_RECIBO"] == "5001"
    assert intacta["PAGADO"] is False and intacta["NO_RECIBO"] == ""

    traza = db.query(LegacyInteractionLog).one()
    assert traza.direction == "OUT" and traza.status == "OK" and traza.rows_affected == 3
    assert traza.payload_summary["sandbox"] is True


def test_drenado_real_nunca_escribe_sobre_el_share_productivo(db, share, sandbox_caja, escribir_dbf, leer_dbf):
    """El share está montado read-only: el writer sólo puede tocar el sandbox."""
    ruta_share = escribir_dbf(share, "cajapagos", [{"NO_RECIBO": "4999"}])
    antes = open(ruta_share, "rb").read()

    _encolar(db)
    assert outbox_service.drain_real(db)["applied"] == 1

    assert open(ruta_share, "rb").read() == antes
    assert leer_dbf(ruta_share) == [{"NO_RECIBO": "4999", "COD_AGEN": "", "FECHA_PAGO": "",
                                     "ORIGEN": "", "TOTAL": "", "BONOS": "", "PESOS": "",
                                     "CAJERO": ""}]


def test_drenado_real_hace_backup_antes_de_tocar_las_dbf(db, sandbox_caja):
    _encolar(db)
    outbox_service.drain_real(db)
    backups = os.listdir(str(sandbox_caja / "_backup"))
    assert len(backups) == 1
    copiadas = set(os.listdir(str(sandbox_caja / "_backup" / backups[0])))
    assert copiadas == {"cajapagos.dbf", "cajaforpag.dbf", "cajaliq.dbf"}


def test_drenado_real_es_idempotente_por_no_recibo(db, sandbox_caja, leer_dbf):
    _encolar(db)
    outbox_service.drain_real(db)

    # se vuelve a encolar la misma operación con otra clave: el recibo ya está en la DBF
    _encolar(db, clave="aplicar_pago:5001-reintento")
    r = outbox_service.drain_real(db)
    assert (r["applied"], r["skipped"]) == (0, 1)
    assert "ya existe en cajapagos" in r["entries"][0]["result"]["reason"]

    db.expire_all()
    estados = {f.idempotency_key: f.status for f in db.query(LegacyOutbox)}
    assert estados == {"aplicar_pago:5001": "APPLIED", "aplicar_pago:5001-reintento": "SKIPPED"}
    assert len(leer_dbf(str(sandbox_caja / "caja" / "cajapagos.dbf"))) == 2


def test_drenado_real_de_un_pago_sin_detalle(db, sandbox_caja):
    _encolar(db, payload={"no_recibo": 7000, "cod_agencia": "A01",
                          "fecha_pago": "2026-02-09", "total": "1.00"},
             clave="aplicar_pago:7000")
    r = outbox_service.drain_real(db)
    assert r["entries"][0]["result"]["rows"] == {"cajapagos": 1, "cajaforpag": 0, "cajaliq": 0}


def test_drenado_real_anula_el_pago(db, sandbox_caja, leer_dbf):
    _encolar(db)
    outbox_service.drain_real(db)

    _encolar(db, operation="anular_pago", payload={"no_recibo": 5001, "motivo": "error"})
    r = outbox_service.drain_real(db)
    assert r["applied"] == 1
    assert r["entries"][0]["result"]["rows"] == {"cajaforpag": 1, "cajaliq": 1}

    formas = leer_dbf(str(sandbox_caja / "caja" / "cajaforpag.dbf"))
    assert formas[0]["ANULADO"] is True
    liq = [l for l in leer_dbf(str(sandbox_caja / "caja" / "cajaliq.dbf"))
           if l["NO_SORTEO"] == "77"][0]
    assert liq["PAGADO"] is False and liq["NO_RECIBO"] == ""


def test_operacion_sin_handler_queda_fallida(db, sandbox_caja):
    fila = _encolar(db, operation="consolidar_creditos", database="creditos",
                    payload={"fecha": "2026-02-09"})
    r = outbox_service.drain_real(db)
    assert (r["applied"], r["failed"]) == (0, 1)
    assert r["entries"][0]["status"] == "FAILED"

    db.expire_all()
    fila = db.get(LegacyOutbox, fila.id)
    assert fila.status == "FAILED" and fila.attempts == 1
    assert "Sin handler de escritura" in fila.last_error

    traza = db.query(LegacyInteractionLog).one()
    assert traza.status == "ERROR" and traza.table_name == "maecuotas"
    assert traza.database == "creditos"


def test_si_falta_la_dbf_sandbox_la_operacion_queda_fallida(db, sandbox):
    """Sin sandbox montado no se aplica nada y el error queda registrado."""
    fila = _encolar(db)
    r = outbox_service.drain_real(db)
    assert (r["applied"], r["failed"]) == (0, 1)
    assert "DBF sandbox no encontrada" in r["entries"][0]["error"]

    db.expire_all()
    fila = db.get(LegacyOutbox, fila.id)
    assert fila.status == "FAILED" and "DBF sandbox no encontrada" in fila.last_error
    assert db.query(LegacyInteractionLog).one().status == "ERROR"


def test_el_drenado_real_solo_toma_las_pendientes(db, sandbox_caja):
    fila = _encolar(db)
    fila.status = "APPLIED"
    db.commit()
    r = outbox_service.drain_real(db)
    assert r == {"mode": "real_sandbox", "applied": 0, "skipped": 0, "failed": 0, "entries": []}


# ── Gating desde la API ───────────────────────────────────────────────────────

def test_la_api_permite_el_drenado_real_solo_con_el_flag_encendido(client, db, sandbox_caja,
                                                                   monkeypatch, notificaciones):
    _encolar(db)
    assert client.post("/api/legacy/outbox/drain?mode=real").status_code == 409

    monkeypatch.setattr(settings, "allow_real_drain", True)
    body = client.post("/api/legacy/outbox/drain?mode=real",
                       headers={"X-User-Id": "7"}).json()
    assert body["mode"] == "real_sandbox" and body["applied"] == 1
    assert "Modo real_sandbox: 1 aplicado(s)" in notificaciones[0]["message"]
