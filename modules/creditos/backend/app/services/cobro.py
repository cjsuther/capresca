"""Forma de cobro de una línea de crédito (componente COLLECTION, "Forma de cobro").

Muchas líneas se cobran por **código de descuento**: el organismo empleador retiene la cuota del sueldo y
el empleado la ve detallada en su recibo de haberes, con el código y el concepto que tiene asignados la
línea. La solicitud se lo avisa al final, para que sepa cómo le va a venir en el recibo.

    config = {"modalidad": CODIGO_DESCUENTO | VENTANILLA | DEBITO_AUTOMATICO,
              "codigoDescuento": "4521", "conceptoRecibo": "CAPRESCA PREST PERSONAL", "detalle": ""}
"""
from __future__ import annotations

COMPONENTE = "COLLECTION"
CODIGO_DESCUENTO = "CODIGO_DESCUENTO"
MODALIDADES = {CODIGO_DESCUENTO: "Código de descuento en el recibo de sueldo",
               "VENTANILLA": "Pago en ventanilla", "DEBITO_AUTOMATICO": "Débito automático"}
MAX_CODIGO, MAX_CONCEPTO, MAX_DETALLE = 20, 60, 300


def errores(config: dict) -> list[str]:
    """Lo que está mal en la configuración (se valida al guardar el producto)."""
    e = []
    modalidad = config.get("modalidad")
    if modalidad not in MODALIDADES:
        e.append("forma de cobro: elegí la modalidad")
    if modalidad == CODIGO_DESCUENTO:
        if not str(config.get("codigoDescuento") or "").strip():
            e.append("forma de cobro: falta el código de descuento")
        if not str(config.get("conceptoRecibo") or "").strip():
            e.append("forma de cobro: falta cómo figura en el recibo de sueldo")
    if len(str(config.get("codigoDescuento") or "")) > MAX_CODIGO:
        e.append(f"forma de cobro: el código de descuento tiene hasta {MAX_CODIGO} caracteres")
    if len(str(config.get("conceptoRecibo") or "")) > MAX_CONCEPTO:
        e.append(f"forma de cobro: el concepto del recibo tiene hasta {MAX_CONCEPTO} caracteres")
    if len(str(config.get("detalle") or "")) > MAX_DETALLE:
        e.append(f"forma de cobro: la aclaración tiene hasta {MAX_DETALLE} caracteres")
    return e


def de(v) -> dict | None:
    """La forma de cobro de la versión, lista para mostrar; None si la línea no la configura."""
    if v is None:
        return None
    row = next((c for c in v.componentes if c.componente_codigo == COMPONENTE), None)
    if row is None or not row.activo:
        return None
    c = row.config or {}
    modalidad = c.get("modalidad") if c.get("modalidad") in MODALIDADES else CODIGO_DESCUENTO
    return {"modalidad": modalidad, "modalidadTexto": MODALIDADES[modalidad],
            "codigoDescuento": str(c.get("codigoDescuento") or "").strip(),
            "conceptoRecibo": str(c.get("conceptoRecibo") or "").strip(),
            "detalle": str(c.get("detalle") or "").strip()}
