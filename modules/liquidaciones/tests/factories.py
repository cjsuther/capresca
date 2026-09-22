"""Generadores de archivos DBF y ZIP de liquidación para los tests.

El módulo parsea DBFs reales con dbfread, así que armamos bytes dBase III válidos
en vez de mockear el parser: así los tests ejercitan el camino completo.
"""
import datetime
import io
import struct
import zipfile

# (nombre, tipo, largo, decimales) — el legacy manda todo como Character salvo importes.
CAMPOS_DETALLE = [
    ("N_AGEN", "C", 6, 0),
    ("C_JUEGO", "C", 6, 0),
    ("D_JUEGO", "C", 20, 0),
    ("N_SORTEO", "C", 5, 0),
    ("C_CODIGO", "C", 3, 0),
    ("D_CODIGO", "C", 50, 0),
    ("D_OPERAC", "C", 10, 0),
    ("IMPORTE", "C", 15, 0),
    ("C_MONEDA", "C", 2, 0),
    ("C_RESUMEN", "C", 10, 0),
]

CAMPOS_RESUMEN = [
    ("C_JUEGO", "C", 3, 0),
    ("N_AGEN", "C", 6, 0),
    ("D_OPERAC", "C", 10, 0),
    ("IMPORTE", "C", 15, 0),
    ("C_MONEDA", "C", 2, 0),
    ("C_RESUMEN", "C", 10, 0),
    ("F_MOVIN", "C", 5, 0),
]


def construir_dbf(campos, registros) -> bytes:
    """Serializa una tabla dBase III (sin memos) a bytes."""
    largo_cabecera = 32 + 32 * len(campos) + 1
    largo_registro = 1 + sum(c[2] for c in campos)
    hoy = datetime.date.today()

    out = bytearray()
    out += struct.pack(
        "<BBBBIHH20x", 0x03, hoy.year - 1900, hoy.month, hoy.day,
        len(registros), largo_cabecera, largo_registro,
    )
    for nombre, tipo, largo, decimales in campos:
        out += struct.pack(
            "<11sc4xBB14x", nombre.encode("ascii"), tipo.encode("ascii"), largo, decimales,
        )
    out += b"\x0d"

    for reg in registros:
        out += b" "  # marca de borrado
        for nombre, tipo, largo, _dec in campos:
            valor = str(reg.get(nombre, ""))
            crudo = valor.encode("latin-1", "replace")[:largo]
            out += crudo.rjust(largo) if tipo == "N" else crudo.ljust(largo)
    out += b"\x1a"
    return bytes(out)


def detalle(n_agen="000123", c_juego="50", d_juego="QUINIELA", n_sorteo="1001",
            c_codigo="1", d_codigo="RECAUDACION", d_operac="15/03/2025",
            importe="1000.00", c_moneda="$", c_resumen="777"):
    """Un registro del M.dbf con valores por defecto razonables."""
    return {
        "N_AGEN": n_agen, "C_JUEGO": c_juego, "D_JUEGO": d_juego, "N_SORTEO": n_sorteo,
        "C_CODIGO": c_codigo, "D_CODIGO": d_codigo, "D_OPERAC": d_operac,
        "IMPORTE": importe, "C_MONEDA": c_moneda, "C_RESUMEN": c_resumen,
    }


def resumen(n_agen="000123", c_juego="50", d_operac="15/03/2025", importe="1000.00",
            c_moneda="$", c_resumen="777", f_movin="0315"):
    """Un registro del R.dbf."""
    return {
        "C_JUEGO": c_juego, "N_AGEN": n_agen, "D_OPERAC": d_operac, "IMPORTE": importe,
        "C_MONEDA": c_moneda, "C_RESUMEN": c_resumen, "F_MOVIN": f_movin,
    }


def construir_zip(detalles=None, resumenes=None, *, extra=None,
                  nombre_detalle="LIQ0315M.DBF", nombre_resumen="LIQ0315R.DBF",
                  con_detalle=True, con_resumen=True) -> bytes:
    """Arma el ZIP tal como lo entrega el sistema de juegos."""
    detalles = [detalle()] if detalles is None else detalles
    resumenes = [resumen()] if resumenes is None else resumenes

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if con_detalle:
            zf.writestr(nombre_detalle, construir_dbf(CAMPOS_DETALLE, detalles))
        if con_resumen:
            zf.writestr(nombre_resumen, construir_dbf(CAMPOS_RESUMEN, resumenes))
        for nombre, contenido in (extra or {}).items():
            zf.writestr(nombre, contenido)
    return buf.getvalue()


def zip_coherente(agencia="000123", importe="1000.00"):
    """ZIP donde el resumen cuadra con el detalle (código 1 = recaudación, total=importe)."""
    return construir_zip(
        detalles=[detalle(n_agen=agencia, c_codigo="1", importe=importe)],
        resumenes=[resumen(n_agen=agencia, importe=importe)],
    )
