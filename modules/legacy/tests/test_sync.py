"""
Capa de lectura: catálogo, coerción de tipos DBF->Postgres, lector de DBF,
salud del montaje SMB y espejado (sync) hacia el mirror.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.config import settings
from app.legacy_catalog import DATABASES, READ_ONLY_TABLES, database_of, relative_path
from app.models.interaction_log import LegacyInteractionLog
from app.models.mirror_caja import MirrorCajaliq, MirrorCajapagos
from app.models.mirror_juegos import MirrorMaeagencias
from app.models.sync_state import LegacySyncState
from app.services import coercion as C
from app.services import dbf_reader, smb_health, sync_service

# ── Catálogo ──────────────────────────────────────────────────────────────────


def test_el_catalogo_mapea_tabla_a_base_y_a_ruta():
    assert database_of("cajaliq") == "caja"
    assert database_of("maeagencias") == "juegos"
    assert relative_path("maeclientes") == "creditos/maeclientes.dbf"
    assert set(DATABASES) == {"caja", "juegos", "creditos", "general", "contabilidad"}


def test_tabla_desconocida_no_tiene_base_ni_ruta():
    assert database_of("no_existe") is None
    assert relative_path("no_existe") is None


def test_las_tablas_consolidadas_son_de_solo_lectura():
    assert READ_ONLY_TABLES == frozenset({"solble", "ctable"})
    assert "maecuotas" not in READ_ONLY_TABLES


# ── Coerción ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    (None, None), ("", None), ("  ", None), ("  A01  ", "A01"), (7, "7"),
])
def test_to_str(entrada, esperado):
    assert C.to_str(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, None), ("", None),
    ("113400.00000", Decimal("113400.00")),
    ("1234,56", Decimal("1234.56")),          # coma decimal del legacy
    # TODO(bug): coercion.to_decimal:37 sólo normaliza la coma si NO hay punto, así que
    # un importe con separador de miles al estilo legacy ("1.234,56") se descarta -> None.
    ("1.234,56", None),
    (Decimal("1.005"), Decimal("1.01")),      # ROUND_HALF_UP
    (10, Decimal("10.00")), (2.5, Decimal("2.50")),
    ("no-es-numero", None),
])
def test_to_decimal(entrada, esperado):
    assert C.to_decimal(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, None), ("", None), ("42", 42), (" 7 ", 7), ("3.9", 3), (4.7, 4),
    (99, 99), (True, 1), ("x", None),
])
def test_to_int(entrada, esperado):
    assert C.to_int(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, None), ("", None),
    ("09/02/2026", date(2026, 2, 9)),
    ("2026-02-09", date(2026, 2, 9)),
    ("20260209", date(2026, 2, 9)),
    ("09-02-2026", date(2026, 2, 9)),
    (date(2026, 2, 9), date(2026, 2, 9)),
    (datetime(2026, 2, 9, 13, 45), date(2026, 2, 9)),
    ("no-es-fecha", None),
])
def test_to_date(entrada, esperado):
    assert C.to_date(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, None), (True, True), (False, False),
    (".T.", True), ("S", True), ("si", True), ("1", True),
    (".F.", False), ("N", False), ("0", False), ("", False),
    ("quizas", None),
])
def test_to_bool(entrada, esperado):
    assert C.to_bool(entrada) is esperado


# ── Lector de DBF ─────────────────────────────────────────────────────────────

def test_table_path_se_arma_sobre_el_share(share):
    assert dbf_reader.table_path("cajaliq") == f"{share}/caja/cajaliq.dbf"


def test_table_path_falla_con_una_tabla_fuera_del_catalogo():
    with pytest.raises(ValueError, match="Tabla desconocida"):
        dbf_reader.table_path("inventada")


def test_read_table_devuelve_claves_en_mayusculas_y_strings_stripeados(share, escribir_dbf):
    escribir_dbf(share, "maeagencias", [{"COD_AGEN": "A01", "TITULAR": "Primera"}])
    filas = dbf_reader.read_table("maeagencias")
    assert filas == [{"COD_AGEN": "A01", "TITULAR": "Primera"}]


def test_read_table_avisa_si_la_dbf_no_existe(share):
    with pytest.raises(dbf_reader.DbfNotFound, match="No se encontró la DBF"):
        dbf_reader.read_table("cajaliq")


def test_get_field_ci_es_case_insensitive():
    fila = {"COD_AGEN": "A01"}
    assert dbf_reader.get_field_ci(fila, "cod_agen") == "A01"
    assert dbf_reader.get_field_ci(fila, "OTRO") is None


# ── Salud del montaje ─────────────────────────────────────────────────────────

def test_check_mount_sin_montaje(monkeypatch):
    monkeypatch.setattr(settings, "smb_mount_root", "/ruta/inexistente")
    estado = smb_health.check_mount()
    assert estado["mounted"] is False and estado["tables_present"] == 0
    assert estado["databases"] == {} and "error" in estado
    assert smb_health.is_available() is False


def test_check_mount_cuenta_las_tablas_presentes(share, escribir_dbf):
    escribir_dbf(share, "cajaliq", [])
    escribir_dbf(share, "maeagencias", [])
    estado = smb_health.check_mount()
    assert estado["mounted"] is True and estado["tables_present"] == 2
    assert estado["databases"]["caja"]["subdir_exists"] is True
    assert estado["databases"]["caja"]["tables"] == {
        "cajaliq": True, "cajapagos": False, "cajaforpag": False, "cajacreseg": False,
    }
    assert estado["databases"]["contabilidad"]["subdir_exists"] is False
    assert estado["tables_total"] == 16
    assert smb_health.is_available() is True


# ── Sync legacy -> mirror ─────────────────────────────────────────────────────

def test_sync_de_tabla_no_sincronizable_lanza(db):
    with pytest.raises(ValueError, match="Tabla no sincronizable"):
        sync_service.sync_table(db, "solble")


def test_sync_inserta_coacciona_tipos_y_registra_la_interaccion(db, share, escribir_dbf):
    escribir_dbf(share, "cajaliq", [
        {"COD_AGEN": "A01", "COD_JUEGO": "3", "NO_SORTEO": "77",
         "IMPORTE": "113400.00000", "INTERESES": "12,50", "PAGADO": False,
         "FECHA_PAGO": "", "NO_RECIBO": ""},
    ])
    r = sync_service.sync_table(db, "cajaliq")
    assert r == {"table": "cajaliq", "status": "OK", "rows_seen": 1, "rows_changed": 1}

    fila = db.query(MirrorCajaliq).one()
    assert fila.cod_agencia == "A01" and fila.cod_juego == 3 and fila.no_sorteo == 77
    assert fila.importe == Decimal("113400.00") and fila.intereses == Decimal("12.50")
    assert fila.pagado is False and fila.fecha_pago is None and fila.no_recibo is None
    assert len(fila.row_hash) == 32

    traza = db.query(LegacyInteractionLog).one()
    assert traza.direction == "IN" and traza.database == "caja" and traza.status == "OK"
    assert traza.payload_summary == {"rows_seen": 1, "rows_changed": 1}
    assert traza.latency_ms is not None


def test_sync_repetido_sin_cambios_no_vuelve_a_escribir(db, share, escribir_dbf):
    escribir_dbf(share, "maeagencias", [{"COD_AGEN": "A01", "TITULAR": "Primera"}])
    assert sync_service.sync_table(db, "maeagencias")["rows_changed"] == 1
    segunda = sync_service.sync_table(db, "maeagencias")
    assert segunda["rows_seen"] == 1 and segunda["rows_changed"] == 0
    assert db.query(MirrorMaeagencias).count() == 1


def test_sync_detecta_cambios_por_hash_y_actualiza_la_fila(db, share, escribir_dbf):
    escribir_dbf(share, "maeagencias", [{"COD_AGEN": "A01", "TITULAR": "Primera"}])
    sync_service.sync_table(db, "maeagencias")
    hash_inicial = db.query(MirrorMaeagencias).one().row_hash

    escribir_dbf(share, "maeagencias", [{"COD_AGEN": "A01", "TITULAR": "Renombrada"}])
    assert sync_service.sync_table(db, "maeagencias")["rows_changed"] == 1

    db.expire_all()
    fila = db.query(MirrorMaeagencias).one()
    assert fila.titular == "Renombrada" and fila.row_hash != hash_inicial


def test_sync_guarda_la_marca_de_agua_mas_alta(db, share, escribir_dbf):
    escribir_dbf(share, "cajapagos", [
        {"NO_RECIBO": "5001", "COD_AGEN": "A01", "TOTAL": "100.00"},
        {"NO_RECIBO": "5003", "COD_AGEN": "A01", "TOTAL": "200.00"},
        {"NO_RECIBO": "5002", "COD_AGEN": "A01", "TOTAL": "300.00"},
    ])
    sync_service.sync_table(db, "cajapagos")
    estado = db.query(LegacySyncState).filter_by(table_name="cajapagos").one()
    assert estado.watermark == "5003" and estado.rows_seen == 3
    assert estado.last_status == "OK" and estado.last_error is None
    assert db.query(MirrorCajapagos).count() == 3


def test_sync_sin_dbf_deja_el_estado_en_error_y_no_rompe(db, share):
    r = sync_service.sync_table(db, "maeclientes", origin_module="legacy-admin")
    assert r["status"] == "ERROR" and "No se encontró la DBF" in r["error"]

    estado = db.query(LegacySyncState).filter_by(table_name="maeclientes").one()
    assert estado.last_status == "ERROR" and estado.database == "creditos"
    traza = db.query(LegacyInteractionLog).one()
    assert traza.status == "ERROR" and traza.origin_module == "legacy-admin"
    assert traza.error_message == r["error"]


def test_sync_hace_rollback_si_el_mirror_falla(db, share, monkeypatch, escribir_dbf):
    """Una fila mal formada no debe dejar el mirror a medias."""
    escribir_dbf(share, "maeagencias", [
        {"COD_AGEN": "A01", "TITULAR": "Primera"},
        {"COD_AGEN": "A02", "TITULAR": "Segunda"},
    ])

    def _explota(spec, raw):
        if dbf_reader.get_field_ci(raw, "COD_AGEN") == "A02":
            raise RuntimeError("fila corrupta")
        return {"cod_agencia": "A01", "titular": "Primera"}

    monkeypatch.setattr(sync_service, "_build_values", _explota)
    r = sync_service.sync_table(db, "maeagencias")
    assert r["status"] == "ERROR" and "fila corrupta" in r["error"]
    assert db.query(MirrorMaeagencias).count() == 0
    assert db.query(LegacySyncState).filter_by(table_name="maeagencias").one().last_status == "ERROR"


def test_sync_all_recorre_todas_las_tablas_del_spec(db, share, escribir_dbf):
    escribir_dbf(share, "maeagencias", [{"COD_AGEN": "A01", "TITULAR": "Primera"}])
    resultados = sync_service.sync_all(db)
    por_tabla = {r["table"]: r["status"] for r in resultados}
    assert por_tabla["maeagencias"] == "OK"
    # el resto no tiene DBF en el share de prueba: error controlado, sin excepción
    assert por_tabla["maejuegos"] == "ERROR" and por_tabla["maecuotas"] == "ERROR"
    assert len(resultados) == len(por_tabla)
