"""Documentación adjunta a solicitudes: validación, límites y serialización.

Los bytes viven en `pp_solicitud_documento.contenido` (DB). A escala real esto migraría a
object storage; para el portal/migración alcanza con la DB (self-contained, sirve en PG y SQLite)."""
from __future__ import annotations

MAX_BYTES = 5 * 1024 * 1024   # 5 MB por archivo
ALLOWED = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
TIPOS = {"DNI_FRENTE", "DNI_DORSO", "RECIBO", "OTRO"}
MAX_POR_SOLICITUD = 10


def normalizar_tipo(tipo: str | None) -> str:
    t = (tipo or "OTRO").upper()
    return t if t in TIPOS else "OTRO"


def validar(content_type: str | None, tamano: int) -> None:
    """Levanta ValueError con un mensaje claro si el archivo no es válido."""
    if (content_type or "") not in ALLOWED:
        raise ValueError("Formato no permitido. Subí una imagen (JPG, PNG, WEBP) o un PDF.")
    if tamano <= 0:
        raise ValueError("El archivo está vacío.")
    if tamano > MAX_BYTES:
        raise ValueError(f"El archivo supera el máximo de {MAX_BYTES // 1024 // 1024} MB.")


def serial(d) -> dict:
    """Metadata (sin los bytes)."""
    return {"id": d.id, "tipo": d.tipo, "nombre": d.nombre, "content_type": d.content_type,
            "tamano": d.tamano, "subido_por": d.subido_por,
            "subido_en": str(d.subido_en) if d.subido_en else ""}
