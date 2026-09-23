"""Documentación adjunta a solicitudes: validación, límites y serialización.

Los bytes viven en `pp_solicitud_documento.contenido` (DB). A escala real esto migraría a
object storage; para el portal/migración alcanza con la DB (self-contained, sirve en PG y SQLite)."""
from __future__ import annotations

MAX_BYTES = 5 * 1024 * 1024   # 5 MB por archivo
ALLOWED = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
TIPOS = {"DNI_FRENTE", "DNI_DORSO", "SELFIE_DNI", "RECIBO", "CERTIFICADO_SERVICIOS",
         "CONSTANCIA_CBU", "OTRO"}
# Lo que adjunta el ciudadano desde el portal: uno de cada uno, y nada más.
TIPOS_PORTAL = ("DNI_FRENTE", "DNI_DORSO", "SELFIE_DNI", "RECIBO", "CERTIFICADO_SERVICIOS",
                "CONSTANCIA_CBU")
ETIQUETAS = {"DNI_FRENTE": "el DNI (frente)", "DNI_DORSO": "el DNI (dorso)",
             "SELFIE_DNI": "la selfie con el DNI en la mano", "RECIBO": "el recibo de sueldo",
             "CERTIFICADO_SERVICIOS": "el certificado de servicios",
             "CONSTANCIA_CBU": "la constancia de CBU",
             "OTRO": "otro documento"}


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
