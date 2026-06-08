"""
Scopes Interbanking y su flujo OAuth asociado.

El scope/grant es determinado por el endpoint que se está llamando, no por la
credencial. Una misma credencial puede operar con distintos scopes y cada uno
obtiene su propio token.
"""
from typing import Literal

# Scopes oficiales de Interbanking
INFO_FINANCIERA = "info-financiera"          # Cuentas, Saldos, Movimientos, Extractos, Transferencias (consulta)
TRANSFERENCIAS_CONFECCION = "transferencias-confeccion"  # Confección y envío de transferencias / pagos

Scope = Literal["info-financiera", "transferencias-confeccion"]

# Cada scope usa un grant distinto
SCOPE_TO_GRANT: dict[str, str] = {
    INFO_FINANCIERA: "client_credentials",
    TRANSFERENCIAS_CONFECCION: "password",
}


def grant_for(scope: str) -> str:
    if scope not in SCOPE_TO_GRANT:
        raise ValueError(f"Scope desconocido: {scope}")
    return SCOPE_TO_GRANT[scope]
