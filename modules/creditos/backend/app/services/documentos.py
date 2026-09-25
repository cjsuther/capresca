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

# Cómo se le presenta cada documento al ciudadano en el portal (título y la ayuda de abajo).
TITULOS = {"DNI_FRENTE": "DNI (frente)", "DNI_DORSO": "DNI (dorso)",
           "SELFIE_DNI": "Selfie con el DNI en la mano", "RECIBO": "Recibo de sueldo",
           "CERTIFICADO_SERVICIOS": "Certificado de servicios",
           "CONSTANCIA_CBU": "Constancia de CBU"}
AYUDAS = {"SELFIE_DNI": "Una foto tuya sosteniendo el DNI, que se lean los datos.",
          "CERTIFICADO_SERVICIOS": "El que emite tu empleador con tu antigüedad y situación de revista.",
          "CONSTANCIA_CBU": "La que baja tu banco o Home Banking con el CBU a tu nombre."}

# Qué documentación pide la solicitud del portal. Se configura en Créditos → Parámetros, y cada
# oficina decide cuáles exige: no es lo mismo un microcrédito que un préstamo con garantía.
PARAMETRO = "PORTAL_DOCUMENTOS"


def habilitados(valor: str | None) -> tuple[str, ...]:
    """Los documentos que se piden, según el parámetro.

    Sin parámetro cargado se piden TODOS: es lo que hacía el portal antes de que esto se pudiera
    configurar, y es el default prudente. El parámetro vacío es una decisión explícita —no pedir
    ninguno— y se respeta: el portal saltea el paso.
    """
    if valor is None:
        return TIPOS_PORTAL
    elegidos = [t.strip().upper() for t in valor.split(",") if t.strip()]
    return tuple(t for t in TIPOS_PORTAL if t in elegidos)


def para_portal(tipos_habilitados) -> list[dict]:
    """Lo que el portal necesita para dibujar el paso de documentación."""
    return [{"tipo": t, "titulo": TITULOS.get(t, t), "ayuda": AYUDAS.get(t, "")}
            for t in tipos_habilitados]


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
