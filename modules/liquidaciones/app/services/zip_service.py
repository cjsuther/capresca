import zipfile
import io
import re


def extract_zip(zip_bytes: bytes) -> dict:
    """Extract ZIP and classify files by type."""
    result = {
        "dbf_detail": None,
        "dbf_summary": None,
        "pdf_movimientos": None,
        "pdf_resumenes": None,
        "filenames": {},
    }

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            data = zf.read(name)
            upper = name.upper()

            if upper.endswith("M.DBF"):
                result["dbf_detail"] = data
                result["filenames"]["dbf_detail"] = name
            elif upper.endswith("R.DBF"):
                result["dbf_summary"] = data
                result["filenames"]["dbf_summary"] = name
            elif upper.endswith(".PDF"):
                lower = name.lower()
                if "movimiento" in lower or "codigo" in lower:
                    result["pdf_movimientos"] = data
                    result["filenames"]["pdf_movimientos"] = name
                elif "resumen" in lower or "estado" in lower:
                    result["pdf_resumenes"] = data
                    result["filenames"]["pdf_resumenes"] = name
                else:
                    # Assign to first available PDF slot
                    if result["pdf_movimientos"] is None:
                        result["pdf_movimientos"] = data
                        result["filenames"]["pdf_movimientos"] = name
                    elif result["pdf_resumenes"] is None:
                        result["pdf_resumenes"] = data
                        result["filenames"]["pdf_resumenes"] = name

    if result["dbf_detail"] is None:
        raise ValueError("No se encontró archivo de detalle (*M.dbf) en el ZIP")
    if result["dbf_summary"] is None:
        raise ValueError("No se encontró archivo de resumen (*R.dbf) en el ZIP")

    return result


def read_zip_from_path(file_path: str) -> bytes:
    """Read ZIP file from filesystem path."""
    with open(file_path, "rb") as f:
        return f.read()
