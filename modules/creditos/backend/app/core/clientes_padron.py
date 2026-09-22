"""
Padrón de clientes: vive en el módulo Clientes de Portezuelo.

Créditos no tiene maestro propio. La tabla `clientes` de este módulo es un ESPEJO de sólo lectura
(identidad) más los datos crediticios propios (sueldo, organismo, débito automático). El espejo se
sincroniza contra el servicio de Clientes por su API interna, que no sale del gateway.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app import models

log = logging.getLogger(__name__)
TIMEOUT = 8.0


class PadronNoDisponible(RuntimeError):
    """El servicio de Clientes no respondió: el llamador decide si sigue con el espejo viejo."""


class DocumentoEspejadoConOtroId(RuntimeError):
    """El documento ya está en el espejo con otro id (falta migrar el maestro viejo)."""


def _url(path: str) -> str:
    return f"{get_settings().clientes_service_url.rstrip('/')}{path}"


def ficha(cliente_id: int) -> dict | None:
    """Identidad del cliente en el padrón. None si no existe."""
    try:
        r = httpx.get(_url(f"/internal/clientes/{cliente_id}/ficha"), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json() or None
    except httpx.HTTPError as e:
        raise PadronNoDisponible(str(e)) from e


def ids_por_documento(documentos: list[str]) -> dict[str, int]:
    """Resuelve documentos (DNI/CUIL/CUIT) a ids del padrón, en lote."""
    if not documentos:
        return {}
    try:
        r = httpx.post(_url("/internal/clientes/buscar-por-documento"),
                       json={"documentos": documentos}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("encontrados", {})
    except httpx.HTTPError as e:
        raise PadronNoDisponible(str(e)) from e


def importar(personas: list[dict]) -> dict:
    """Alta/actualización de personas en el padrón (idempotente por documento)."""
    r = httpx.post(_url("/internal/clientes/importar"), json={"personas": personas}, timeout=60.0)
    r.raise_for_status()
    return r.json()


def copiar_documentos(cliente_id: int, documentos: list[dict]) -> dict:
    """Guarda documentos en la ficha del cliente (módulo Clientes). Idempotente: lo que ya tiene no se
    duplica. Cada documento: {nombre, content_type, tipo, origen, contenido_base64}."""
    try:
        r = httpx.post(_url(f"/internal/clientes/{cliente_id}/documentos"),
                       json={"documentos": documentos}, timeout=60.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise PadronNoDisponible(str(e)) from e


def _aplicar(espejo: models.Cliente, f: dict) -> models.Cliente:
    """Vuelca la ficha del padrón sobre el espejo (sólo los campos de identidad)."""
    espejo.apellido_nombre = (f.get("nombre") or "")[:80]
    espejo.cuil = (f.get("documento") or "")[:11]
    espejo.dni = (f.get("documento") or "")[:9]
    espejo.domicilio = (f.get("domicilio") or "")[:120]
    espejo.localidad = (f.get("localidad") or "")[:40]
    espejo.telefono = (f.get("telefono") or "")[:30]
    espejo.email = (f.get("email") or "")[:80]
    espejo.cbu = (f.get("cbu") or "")[:23]
    espejo.baja = not f.get("activo", True)
    espejo.sincronizado_en = datetime.now(timezone.utc)
    return espejo


def sincronizar(db: Session, cliente_id: int) -> models.Cliente | None:
    """
    Trae la identidad del padrón y actualiza (o crea) la fila espejo. Devuelve el espejo, o el que
    ya estaba si el padrón no responde: una caída del servicio de Clientes no puede voltear las
    pantallas de Créditos (degradación elegante).
    """
    espejo = db.get(models.Cliente, cliente_id)
    try:
        f = ficha(cliente_id)
    except PadronNoDisponible as e:
        log.warning("padrón no disponible para cliente %s: %s", cliente_id, e)
        return espejo
    if not f:
        return espejo
    if espejo is None:
        espejo = models.Cliente(id=cliente_id, id_cliente=str(cliente_id))
        db.add(espejo)
    _aplicar(espejo, f)
    try:
        db.commit()
    except IntegrityError:
        # El documento ya figura en el espejo con OTRO id: quedó una fila del maestro viejo sin
        # migrar (o el padrón tiene la persona duplicada). No se adivina: se avisa.
        db.rollback()
        raise DocumentoEspejadoConOtroId(
            f"El documento del cliente {cliente_id} ya está espejado con otro id en Créditos. "
            f"Corré la migración del padrón (app.etl.migrar_padron_clientes).")
    db.refresh(espejo)
    return espejo


def obtener(db: Session, cliente_id: int, refrescar: bool = False) -> models.Cliente | None:
    """Espejo del cliente; lo sincroniza si no está o si se pide expresamente."""
    espejo = db.get(models.Cliente, cliente_id)
    if espejo is None or refrescar:
        return sincronizar(db, cliente_id)
    return espejo
