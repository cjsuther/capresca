"""Encabezado `Content-Disposition` para archivos con nombre elegido por el usuario.

Los encabezados HTTP sólo admiten latin-1: un nombre con acentos, eñes o el espacio angosto que macOS
pone en las capturas ("… 11.46.03 a. m.png") hacía fallar la respuesta con 500. Se manda el nombre
en UTF-8 según RFC 6266/5987 (`filename*`) y, para navegadores viejos, una versión ASCII.
"""
import re
import unicodedata
from urllib.parse import quote


def disposicion(nombre: str, *, inline: bool = True) -> str:
    nombre = (nombre or "archivo").replace("\r", " ").replace("\n", " ").strip() or "archivo"
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    ascii_ = re.sub(r'["\\\\]', "", ascii_).strip() or "archivo"
    tipo = "inline" if inline else "attachment"
    return f"{tipo}; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre, safe='')}"
