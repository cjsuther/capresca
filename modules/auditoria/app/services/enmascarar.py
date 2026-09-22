"""Enmascarado de datos sensibles antes de guardarlos en la auditoría.

La auditoría tiene que dejar reconstruir qué pasó, no ser una segunda copia de los datos delicados:
una clave nunca se guarda y un CBU/documento queda reconocible (últimos dígitos) pero no utilizable.
"""
from __future__ import annotations

# Nunca se guardan: el valor se reemplaza entero.
SECRETOS = ("password", "contrasena", "contraseña", "clave", "secret", "token", "api_key", "apikey",
            "authorization", "hashed", "pin", "cvv")
# Se guardan parcialmente (últimos dígitos) para poder identificar el registro sin exponerlo.
PARCIALES = ("cbu", "cuil", "cuit", "dni", "documento", "tarjeta", "cbu_destino", "numero_cuenta",
             "account_number")
OCULTO = "•••"


def _parcial(valor: str) -> str:
    v = str(valor)
    return OCULTO if len(v) <= 4 else f"{OCULTO}{v[-4:]}"


def campo(nombre: str, valor):
    """Valor a guardar para ese campo (ya enmascarado si corresponde)."""
    n = (nombre or "").lower()
    if valor is None or valor == "":
        return valor
    if any(s in n for s in SECRETOS):
        return OCULTO
    if any(p == n or n.endswith(f"_{p}") or n.startswith(f"{p}_") for p in PARCIALES):
        return _parcial(valor)
    if isinstance(valor, dict):
        return {k: campo(k, v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [campo(nombre, v) for v in valor]
    return valor


def cambios(datos: dict | None) -> dict:
    """{campo: [antes, después]} enmascarado. Recorta lo enorme para que un evento no pese de más."""
    out: dict = {}
    for k, v in (datos or {}).items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            out[k] = [_recortar(campo(k, v[0])), _recortar(campo(k, v[1]))]
        else:
            out[k] = _recortar(campo(k, v))
    return out


def _recortar(v, tope: int = 500):
    return v[:tope] + "…" if isinstance(v, str) and len(v) > tope else v
