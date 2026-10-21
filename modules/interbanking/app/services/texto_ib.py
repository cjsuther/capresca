"""Textos libres que viajan a Interbanking (description, reason, comments).

Interbanking rechaza el envío entero si alguno trae caracteres especiales: 400 "1047 - El campo
comments no admite caracteres especiales" (producción, 21/10/2026, por un " - Cargo: admin").
Se admiten letras sin acento, números y espacios; los acentos y la ñ se pasan a su letra base.
"""
import re
import unicodedata

PERMITIDO = re.compile(r"[A-Za-z0-9 ]")


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))


def no_permitidos(texto: str) -> list[str]:
    """Los caracteres que Interbanking rechazaría (sin contar acentos ni ñ, que se convierten)."""
    vistos: list[str] = []
    for c in sin_acentos(texto):
        if not PERMITIDO.fullmatch(c) and c not in vistos:
            vistos.append(c)
    return vistos


def limpiar(texto: str) -> str:
    """El texto como lo acepta Interbanking: sin acentos y cada carácter especial cambiado por un espacio."""
    s = "".join(c if PERMITIDO.fullmatch(c) else " " for c in sin_acentos(texto))
    return re.sub(r" {2,}", " ", s).strip()
