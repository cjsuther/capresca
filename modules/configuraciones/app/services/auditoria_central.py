"""Detalle de auditoría que este módulo manda a la Auditoría central (módulo `auditoria`).

El gateway registra por su cuenta QUÉ operación pidió cada usuario. Acá se agrega lo que sólo sabe
el módulo: **qué registros se agregaron, modificaron o borraron**, con los campos que cambiaron. Los
dos lados se cruzan por `request_id` (header `X-Request-Id` que inyecta el gateway).

Cómo funciona, sin tocar cada endpoint:
  - un middleware guarda quién está haciendo la request (usuario, IP, request_id);
  - un listener de SQLAlchemy mira, en cada `flush`, qué filas se insertaron/actualizaron/borraron.

Sólo registra lo que pasa dentro de una request HTTP: los scripts (ETL, seeds, migraciones) no
generan ruido. Nunca frena ni voltea la operación: se encola y lo manda un hilo aparte.
"""
from __future__ import annotations

import contextvars
import logging
import os
import queue
import threading

import httpx
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

log = logging.getLogger("auditoria")

MODULO = "configuraciones"
URL = os.getenv("AUDITORIA_SERVICE_URL", "http://auditoria:8013").rstrip("/") + "/internal/auditoria/eventos"
CLAVE = os.getenv("AUDITORIA_INTERNAL_API_KEY", "")
TOPE = 2000
TOPE_FILAS = 200          # una operación masiva no manda miles de eventos: se resume

_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("auditoria_ctx", default=None)
_cola: queue.Queue = queue.Queue(maxsize=TOPE)
_hilo: threading.Thread | None = None
_lock = threading.Lock()
_excluidas: set[str] = set()


def habilitada() -> bool:
    return bool(CLAVE)


# ── Quién está operando ──────────────────────────────────────────────────────────────────────────
def instalar(app, excluir: set[str] | tuple[str, ...] = ()) -> None:
    """Middleware (contexto de la request) + listener de cambios. `excluir`: tablas que no se auditan."""
    global _excluidas
    _excluidas = set(excluir)
    if not habilitada():
        return

    @app.middleware("http")
    async def _contexto(request, call_next):             # noqa: ANN001
        fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        uid = request.headers.get("x-user-id") or ""
        token = _ctx.set({
            "usuario": request.headers.get("x-username") or "",
            "usuario_id": int(uid) if uid.isdigit() else None,
            "ip": (fwd or (request.client.host if request.client else ""))[:64],
            "request_id": (request.headers.get("x-request-id") or "")[:40],
            "ruta": request.url.path,
        })
        try:
            return await call_next(request)
        finally:
            _ctx.reset(token)

    event.listen(Session, "after_flush", _mirar_cambios)


def contexto() -> dict | None:
    return _ctx.get()


# ── Registro manual (acciones de negocio: aprobar, enviar, publicar…) ────────────────────────────
def registrar(*, usuario: str = "", usuario_id: int | None = None, operacion: str | None = None,
              entidad: str = "", entidad_id: str = "", descripcion: str = "", cambios: dict | None = None,
              detalle: str = "", request_id: str = "", ip: str = "", exito: bool = True) -> None:
    if not habilitada():
        return
    ctx = _ctx.get() or {}
    _encolar({"modulo": MODULO, "usuario": usuario or ctx.get("usuario") or "sistema",
              "usuario_id": usuario_id if usuario_id is not None else ctx.get("usuario_id"),
              "operacion": operacion, "entidad": entidad, "entidad_id": str(entidad_id or ""),
              "descripcion": descripcion, "cambios": cambios or {}, "detalle": detalle,
              "request_id": request_id or ctx.get("request_id", ""), "ip": ip or ctx.get("ip", ""),
              "ruta": ctx.get("ruta", ""), "exito": exito, "origen": "MODULO"})


def request_id_de(request) -> str:
    try:
        return (request.headers.get("x-request-id") or "")[:40]
    except Exception:                                    # pragma: no cover
        return ""


# ── Qué registros cambiaron (automático) ─────────────────────────────────────────────────────────
def _pk(obj) -> str:
    try:
        vals = inspect(obj).identity or ()
        return "/".join(str(v) for v in vals) if vals else str(getattr(obj, "id", "") or "")
    except Exception:                                    # pragma: no cover
        return ""


def _tabla(obj) -> str:
    return getattr(obj.__class__, "__tablename__", obj.__class__.__name__)


def _diff(obj) -> dict:
    """{campo: [antes, después]} de lo que realmente cambió en esta fila."""
    cambios = {}
    for attr in inspect(obj).attrs:
        hist = attr.history
        if not hist.has_changes() or not hist.deleted and not hist.added:
            continue
        antes = hist.deleted[0] if hist.deleted else None
        despues = hist.added[0] if hist.added else None
        if antes != despues:
            cambios[attr.key] = [_valor(antes), _valor(despues)]
    return cambios


def _valor(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)[:200]


def _mirar_cambios(session: Session, _ctx_flush) -> None:
    """Listener de SQLAlchemy: anota altas, modificaciones y bajas de esta transacción."""
    ctx = _ctx.get()
    if not ctx:                                          # fuera de una request (ETL, seeds): no se audita
        return
    try:
        grupos = ((session.new, "ALTA"), (session.dirty, "MODIFICACION"), (session.deleted, "BAJA"))
        for objetos, operacion in grupos:
            for obj in list(objetos)[:TOPE_FILAS]:
                tabla = _tabla(obj)
                if tabla in _excluidas:
                    continue
                cambios = _diff(obj) if operacion == "MODIFICACION" else {}
                if operacion == "MODIFICACION" and not cambios:
                    continue                             # sólo se tocó sin cambiar nada
                if operacion == "ALTA":
                    cambios = {k: [None, _valor(v)] for k, v in _fila(obj).items()}
                registrar(operacion=operacion, entidad=obj.__class__.__name__, entidad_id=_pk(obj),
                          descripcion=f"{operacion.capitalize()} en {tabla}", cambios=cambios)
    except Exception:                                    # pragma: no cover - auditar nunca rompe el negocio
        log.exception("Auditoría: no se pudieron leer los cambios de la transacción")


def _fila(obj) -> dict:
    return {c.key: getattr(obj, c.key, None) for c in inspect(obj).mapper.column_attrs}


# ── Envío ────────────────────────────────────────────────────────────────────────────────────────
def _encolar(evento: dict) -> None:
    _asegurar_hilo()
    try:
        _cola.put_nowait(evento)
    except queue.Full:                                   # pragma: no cover - sólo con Auditoría caída
        log.warning("Auditoría: cola llena, se descarta %s %s", evento.get("entidad"), evento.get("entidad_id"))


def _asegurar_hilo() -> None:
    global _hilo
    with _lock:
        if _hilo is None or not _hilo.is_alive():
            _hilo = threading.Thread(target=_enviar_siempre, name="auditoria", daemon=True)
            _hilo.start()


def _enviar_siempre() -> None:                           # pragma: no cover - hilo de fondo
    while True:
        lote = [_cola.get()]
        while len(lote) < 50:
            try:
                lote.append(_cola.get_nowait())
            except queue.Empty:
                break
        try:
            r = httpx.post(URL, json={"eventos": lote}, headers={"X-Api-Key": CLAVE}, timeout=10.0)
            if r.status_code >= 400:
                log.warning("Auditoría rechazó %s evento(s): %s", len(lote), r.status_code)
        except Exception as e:
            log.warning("Auditoría no recibió %s evento(s): %s", len(lote), e)
