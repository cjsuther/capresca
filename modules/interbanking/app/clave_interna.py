"""Clave de las llamadas entre módulos a `/internal/*` (header `X-Internal-Key`).

Todos los contenedores comparten la red de Docker: sin clave, cualquiera que lograra ejecutar algo en uno
de ellos (por ejemplo, el de Créditos, que el portal publica a internet) podría pedir transferencias o
leer el padrón. El que llama manda `headers()`; el que recibe exige `exigir`.

Sin `INTERNAL_SERVICE_KEY` (desarrollo y tests) no se exige: el compose la declara obligatoria.
"""
import hmac
import os

from fastapi import Header, HTTPException


def _clave() -> str:
    return os.getenv("INTERNAL_SERVICE_KEY", "")


def headers() -> dict[str, str]:
    clave = _clave()
    return {"X-Internal-Key": clave} if clave else {}


def exigir(x_internal_key: str | None = Header(None, alias="X-Internal-Key")) -> None:
    clave = _clave()
    if not clave:
        return
    if not x_internal_key or not hmac.compare_digest(x_internal_key, clave):
        raise HTTPException(status_code=401, detail="Clave interna inválida")
