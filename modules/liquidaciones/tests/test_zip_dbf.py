"""Extracción del ZIP y parseo de los DBF del sistema de juegos."""
from decimal import Decimal

import pytest

from app.services import zip_service
from app.services.dbf_parser import parse_dbf, parse_importe
from factories import CAMPOS_DETALLE, construir_dbf, construir_zip, detalle, resumen


# ───────────────────────── zip_service ─────────────────────────

def test_extraccion_clasifica_dbfs_y_pdfs():
    contenido = construir_zip(extra={
        "MOVIMIENTOS_POR_CODIGO.PDF": b"%PDF-mov",
        "ESTADO_DE_RESUMENES.PDF": b"%PDF-res",
    })
    r = zip_service.extract_zip(contenido)

    assert r["dbf_detail"][:1] == b"\x03" and r["dbf_summary"][:1] == b"\x03"
    assert r["pdf_movimientos"] == b"%PDF-mov"
    assert r["pdf_resumenes"] == b"%PDF-res"
    assert r["filenames"]["dbf_detail"] == "LIQ0315M.DBF"


def test_extraccion_ignora_basura_de_macos():
    contenido = construir_zip(extra={
        "__MACOSX/LIQ0315M.DBF": b"basura",
        "._LIQ0315R.DBF": b"basura",
    })
    r = zip_service.extract_zip(contenido)
    assert r["dbf_detail"] != b"basura" and r["dbf_summary"] != b"basura"


def test_pdfs_sin_nombre_reconocible_caen_en_los_slots_libres():
    contenido = construir_zip(extra={"a_uno.pdf": b"%PDF-1", "b_dos.pdf": b"%PDF-2",
                                     "c_tres.pdf": b"%PDF-3"})
    r = zip_service.extract_zip(contenido)
    assert r["pdf_movimientos"] == b"%PDF-1"
    assert r["pdf_resumenes"] == b"%PDF-2"  # el tercero se descarta en silencio


def test_zip_sin_detalle_o_sin_resumen_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="detalle"):
        zip_service.extract_zip(construir_zip(con_detalle=False))
    with pytest.raises(ValueError, match="resumen"):
        zip_service.extract_zip(construir_zip(con_resumen=False))


def test_lee_el_zip_desde_el_filesystem(tmp_path):
    ruta = tmp_path / "liq.zip"
    ruta.write_bytes(b"contenido-zip")
    assert zip_service.read_zip_from_path(str(ruta)) == b"contenido-zip"


# ───────────────────────── dbf_parser ─────────────────────────

def test_parse_dbf_devuelve_dicts_con_los_strings_recortados():
    crudo = construir_dbf(CAMPOS_DETALLE, [detalle(n_agen="123", importe="5.50")])
    filas = parse_dbf(crudo)
    assert len(filas) == 1
    assert filas[0]["N_AGEN"] == "123"          # sin el padding de la columna C(6)
    assert filas[0]["D_JUEGO"] == "QUINIELA"
    assert filas[0]["IMPORTE"] == "5.50"


def test_parse_dbf_de_tabla_vacia():
    assert parse_dbf(construir_dbf(CAMPOS_DETALLE, [])) == []


@pytest.mark.parametrize("entrada,esperado", [
    (Decimal("10.005"), Decimal("10.01")),   # redondeo HALF_UP
    (3, Decimal("3.00")),
    (2.5, Decimal("2.50")),
    ("  1234.567 ", Decimal("1234.57")),
    ("", Decimal("0.00")),
    ("no-es-un-numero", Decimal("0.00")),
    (None, Decimal("0.00")),
])
def test_parse_importe_normaliza_a_dos_decimales(entrada, esperado):
    assert parse_importe(entrada) == esperado


def test_resumen_dbf_se_parsea_con_sus_campos():
    from factories import CAMPOS_RESUMEN
    filas = parse_dbf(construir_dbf(CAMPOS_RESUMEN, [resumen(importe="-300.00")]))
    assert filas[0]["N_AGEN"] == "000123" and filas[0]["F_MOVIN"] == "0315"
    assert parse_importe(filas[0]["IMPORTE"]) == Decimal("-300.00")


def test_los_campos_numericos_del_dbf_no_se_tocan():
    """Los valores no-string (N/F) vuelven tal cual del parser, sin strip."""
    campos = [("N_AGEN", "C", 6, 0), ("IMPORTE", "N", 12, 2)]
    filas = parse_dbf(construir_dbf(campos, [{"N_AGEN": "000123", "IMPORTE": "1500.25"}]))
    assert filas[0]["IMPORTE"] == Decimal("1500.25")
    assert parse_importe(filas[0]["IMPORTE"]) == Decimal("1500.25")
