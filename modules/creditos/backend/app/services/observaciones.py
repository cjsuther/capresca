"""Solicitud OBSERVADA: el asesor le pide al ciudadano que corrija algo antes de seguir evaluando.

El asesor explica qué pasa (texto libre, obligatorio) y puede marcar qué documentos tiene que adjuntar
o reemplazar y si tiene que corregir el CBU. La solicitud queda OBSERVADA: no se aprueba ni se rechaza
hasta que el ciudadano corrige desde el portal y la reenvía (vuelve a EN_EVALUACION).

Cada observación queda en `datos_adicionales["correcciones"]` (historial; la vigente es la última),
con lo que había adjuntado en ese momento: un documento pedido se da por cumplido cuando hay uno de
ese tipo que no estaba al observar. Así no dependemos de comparar relojes de la app y de la base.
"""
from __future__ import annotations

from datetime import datetime

from app import models_productos as m
from app.services import requisitos

ESTADO = "OBSERVADA"


def historial(s: m.PPSolicitud) -> list[dict]:
    return list((s.datos_adicionales or {}).get("correcciones") or [])


def vigente(s: m.PPSolicitud) -> dict | None:
    """La observación que el ciudadano tiene que responder (sólo mientras la solicitud está OBSERVADA)."""
    hist = historial(s)
    return hist[-1] if (s.estado == ESTADO and hist) else None


def _guardar(s: m.PPSolicitud, hist: list[dict]) -> None:
    s.datos_adicionales = {**(s.datos_adicionales or {}), "correcciones": hist}


def observar(db, s: m.PPSolicitud, v, detalle: str, documentos: list[str], cbu: bool, por: str) -> None:
    """Pasa la solicitud a OBSERVADA. Levanta ValueError si el pedido no tiene sentido."""
    detalle = (detalle or "").strip()
    if not detalle:
        raise ValueError("Explicá qué tiene que corregir el solicitante.")
    pedidos = {d["tipo"] for d in requisitos.documentos_de(db, v)}
    documentos = list(dict.fromkeys(str(t).upper() for t in documentos or []))
    ajenos = [t for t in documentos if t not in pedidos]
    if ajenos:
        raise ValueError(f"Esta línea no pide: {', '.join(ajenos)}.")
    previos = [d.id for d in db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id).all()]
    _guardar(s, historial(s) + [{
        "detalle": detalle[:1000], "documentos": documentos, "cbu": bool(cbu),
        "fecha": datetime.now().isoformat(timespec="seconds"), "por": por,
        "docs_previos": previos, "cbu_corregido": False, "respondida": None}])
    s.estado = ESTADO


def documentos_listos(db, s: m.PPSolicitud, obs: dict) -> dict[str, bool]:
    """Para cada documento pedido en la observación: si ya adjuntó uno nuevo."""
    previos = set(obs.get("docs_previos") or [])
    nuevos = {d.tipo for d in db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id).all()
              if d.id not in previos}
    return {t: t in nuevos for t in obs.get("documentos") or []}


def pendientes(db, s: m.PPSolicitud, titulos: dict[str, str]) -> list[str]:
    """Lo que todavía falta para poder reenviar, en palabras del ciudadano."""
    obs = vigente(s)
    if obs is None:
        return []
    faltan = [titulos.get(t, t) for t, ok in documentos_listos(db, s, obs).items() if not ok]
    if obs.get("cbu") and not obs.get("cbu_corregido"):
        faltan.append("el CBU")
    return faltan


def corregir_cbu(s: m.PPSolicitud, cbu: str) -> None:
    obs = vigente(s)
    if obs is None or not obs.get("cbu"):
        raise ValueError("En esta solicitud no se pidió corregir el CBU.")
    cbu = "".join(ch for ch in (cbu or "") if ch.isdigit())
    if len(cbu) != 22:
        raise ValueError("El CBU debe tener 22 dígitos.")
    hist = historial(s)
    hist[-1] = {**obs, "cbu_corregido": True}
    _guardar(s, hist)
    s.datos_adicionales = {**s.datos_adicionales, "cbu": cbu}


def reenviar(s: m.PPSolicitud) -> None:
    hist = historial(s)
    hist[-1] = {**hist[-1], "respondida": datetime.now().isoformat(timespec="seconds")}
    _guardar(s, hist)
    s.estado = "EN_EVALUACION"
