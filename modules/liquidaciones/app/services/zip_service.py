import zipfile
import io
import re


# Tope de lo descomprimido (todo queda en memoria): un ZIP chico puede expandirse a gigas (zip bomb).
MAX_DESCOMPRIMIDO = 300 * 1024 * 1024


def _leer(zf: zipfile.ZipFile, name: str, restante: int) -> bytes:
    """Lee un miembro sin pasar `restante` bytes (el tamaño declarado en el ZIP puede mentir)."""
    with zf.open(name) as src:
        data = src.read(restante + 1)
    if len(data) > restante:
        raise ValueError("El ZIP descomprimido supera el máximo permitido")
    return data


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
        if sum(i.file_size for i in zf.infolist()) > MAX_DESCOMPRIMIDO:
            raise ValueError("El ZIP descomprimido supera el máximo permitido")
        restante = MAX_DESCOMPRIMIDO
        for name in zf.namelist():
            basename = name.rsplit("/", 1)[-1]
            if name.startswith("__MACOSX/") or basename.startswith("._"):
                continue
            data = _leer(zf, name, restante)
            restante -= len(data)
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
