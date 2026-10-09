"""Requisitos de la solicitud por línea de crédito: qué documentación adjunta el ciudadano y qué datos
completa (combos de selección única o múltiple).

Viven en el componente REQUIREMENTS ("Documentación y datos") de la versión del producto, porque
cada línea pide cosas distintas: un crédito para la salud pide la orden médica y el presupuesto del
prestador, uno personal no. Una línea que no activa el componente pide la documentación general del
parámetro PORTAL_DOCUMENTOS (Créditos → Parámetros), como antes de que esto existiera, y ningún dato.

    config = {"documentos": [{"codigo", "titulo", "ayuda", "obligatorio"}],
              "campos": [{"codigo", "etiqueta", "ayuda", "tipo": UNICA|MULTIPLE, "opciones", "obligatorio"}]}
"""
from __future__ import annotations

import re

from app import models
from app.services import documentos as docs_generales

COMPONENTE = "REQUIREMENTS"
TIPOS_CAMPO = ("UNICA", "MULTIPLE")
MAX_CODIGO = 40            # pp_solicitud_documento.tipo
CODIGO_VALIDO = re.compile(r"^[A-Z0-9_]+$")


def config_activa(v) -> dict | None:
    """La config del componente si la versión lo tiene activo; si no, None."""
    if v is None:
        return None
    row = next((c for c in v.componentes if c.componente_codigo == COMPONENTE), None)
    return (row.config or {}) if row and row.activo else None


def errores(config: dict) -> list[str]:
    """Lo que está mal en la configuración (se valida al guardar el producto)."""
    e: list[str] = []
    vistos: set[str] = set()
    for i, d in enumerate(config.get("documentos") or [], 1):
        cod = str(d.get("codigo") or "")
        if not str(d.get("titulo") or "").strip():
            e.append(f"documento #{i}: falta el título")
        if not CODIGO_VALIDO.match(cod) or len(cod) > MAX_CODIGO:
            e.append(f"documento #{i}: el código debe tener hasta {MAX_CODIGO} letras, números o _")
        elif cod in vistos:
            e.append(f"documento #{i}: el código {cod} está repetido")
        vistos.add(cod)
    vistos = set()
    for i, c in enumerate(config.get("campos") or [], 1):
        cod = str(c.get("codigo") or "")
        nombre = str(c.get("etiqueta") or "").strip() or f"#{i}"
        if not str(c.get("etiqueta") or "").strip():
            e.append(f"dato #{i}: falta la pregunta")
        if not CODIGO_VALIDO.match(cod):
            e.append(f"dato {nombre}: el código sólo admite letras, números o _")
        elif cod in vistos:
            e.append(f"dato {nombre}: el código {cod} está repetido")
        vistos.add(cod)
        if c.get("tipo") not in TIPOS_CAMPO:
            e.append(f"dato {nombre}: el tipo debe ser selección única o múltiple")
        opciones = [str(o).strip() for o in (c.get("opciones") or [])]
        if len([o for o in opciones if o]) < 2:
            e.append(f"dato {nombre}: necesita al menos dos opciones")
        if any(not o for o in opciones):
            e.append(f"dato {nombre}: hay una opción vacía")
        if len(set(opciones)) != len(opciones):
            e.append(f"dato {nombre}: hay opciones repetidas")
    return e


def documentos(v, parametro: str | None) -> list[dict]:
    """La documentación que pide la solicitud de esta versión, con lo que el portal necesita mostrar."""
    cfg = config_activa(v)
    if cfg is None:
        return [{**d, "obligatorio": True}
                for d in docs_generales.para_portal(docs_generales.habilitados(parametro))]
    return [{"tipo": d["codigo"], "titulo": d["titulo"].strip(), "ayuda": (d.get("ayuda") or "").strip(),
             "obligatorio": bool(d.get("obligatorio", True))} for d in cfg.get("documentos") or []]


def documentos_de(db, v) -> list[dict]:
    """Igual que `documentos`, leyendo el parámetro de la documentación general."""
    p = db.query(models.Parametro).filter(models.Parametro.clave == docs_generales.PARAMETRO).first()
    return documentos(v, p.valor if p else None)


def campos(v) -> list[dict]:
    cfg = config_activa(v) or {}
    return [{"codigo": c["codigo"], "etiqueta": c["etiqueta"].strip(), "ayuda": (c.get("ayuda") or "").strip(),
             "tipo": c["tipo"], "opciones": [str(o).strip() for o in c.get("opciones") or []],
             "obligatorio": bool(c.get("obligatorio", False))} for c in cfg.get("campos") or []]


def respuestas(v, recibidas: dict[str, list[str]] | None) -> list[dict]:
    """Valida lo que completó el ciudadano y lo devuelve listo para guardar en la solicitud.

    Se guarda con la pregunta y las opciones tal como estaban: si después cambia la configuración,
    la solicitud sigue diciendo lo que se le preguntó y lo que contestó. Levanta ValueError."""
    recibidas = recibidas or {}
    definidos = campos(v)
    sobrantes = set(recibidas) - {c["codigo"] for c in definidos}
    if sobrantes:
        raise ValueError(f"Esta línea no pide: {', '.join(sorted(sobrantes))}.")
    out = []
    for c in definidos:
        elegidas = [str(x).strip() for x in (recibidas.get(c["codigo"]) or []) if str(x).strip()]
        if c["obligatorio"] and not elegidas:
            raise ValueError(f"Completá «{c['etiqueta']}».")
        if c["tipo"] == "UNICA" and len(elegidas) > 1:
            raise ValueError(f"En «{c['etiqueta']}» se elige una sola opción.")
        invalidas = [x for x in elegidas if x not in c["opciones"]]
        if invalidas:
            raise ValueError(f"«{invalidas[0]}» no es una opción de «{c['etiqueta']}».")
        # Sin duplicados y en el orden de las opciones, no en el de los clics.
        valores = [o for o in c["opciones"] if o in elegidas]
        out.append({"codigo": c["codigo"], "etiqueta": c["etiqueta"], "tipo": c["tipo"], "valores": valores})
    return out
