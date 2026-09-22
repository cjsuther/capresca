"""Reglas de los documentos del cliente: formatos, tamaño, alta idempotente y encabezado de descarga."""
import hashlib
import re
import unicodedata
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import ClientDocument

TIPOS = {"DNI_FRENTE": "DNI (frente)", "DNI_DORSO": "DNI (dorso)", "RECIBO": "Recibo de sueldo", "OTRO": "Otro"}
FORMATOS = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_BYTES = 10 * 1024 * 1024


def serial(d: ClientDocument) -> dict:
    return {"id": d.id, "tipo": d.tipo, "nombre": d.nombre, "content_type": d.content_type,
            "tamano": d.tamano, "origen": d.origen,
            "created_at": d.created_at.isoformat() if d.created_at else None}


def guardar(db: Session, client_id: int, *, contenido: bytes, nombre: str, content_type: str,
            tipo: str = "OTRO", origen: str = "Carga manual", user_id: int | None = None) -> tuple[ClientDocument, bool]:
    """Valida y guarda. Si el cliente ya tiene ese mismo archivo (mismo contenido), no lo duplica:
    devuelve el existente y `False`."""
    tipo = tipo if tipo in TIPOS else "OTRO"
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type not in FORMATOS:
        raise HTTPException(422, "Formato no permitido (JPG, PNG, WEBP o PDF).")
    if not contenido:
        raise HTTPException(422, "El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise HTTPException(422, "El archivo supera los 10 MB.")
    sha = hashlib.sha256(contenido).hexdigest()
    ya = db.query(ClientDocument).filter_by(client_id=client_id, sha256=sha).first()
    if ya:
        return ya, False
    doc = ClientDocument(client_id=client_id, tipo=tipo, nombre=(nombre or "documento")[:255],
                         content_type=content_type, tamano=len(contenido), sha256=sha, contenido=contenido,
                         origen=(origen or "Carga manual")[:120], created_by_user_id=user_id)
    db.add(doc)
    return doc, True


def disposicion(nombre: str) -> str:
    """Content-Disposition con el nombre en UTF-8 (RFC 6266) y respaldo ASCII: los encabezados HTTP sólo
    admiten latin-1 y un nombre de captura de macOS (espacio angosto antes de "a. m.") rompía la respuesta."""
    nombre = (nombre or "documento").replace("\r", " ").replace("\n", " ").strip() or "documento"
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    ascii_ = re.sub(r'["\\\\]', "", ascii_).strip() or "documento"
    return f"inline; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre, safe='')}"
