"""Códigos autogenerados del sistema nuevo (no legacy)."""
import uuid


def codigo_cliente(pk: int) -> str:
    """Código de cliente autogenerado a partir del PK (surrogate). Es del namespace del sistema nuevo
    (prefijo CL-), distinto del CIDCLIENTE legacy (numérico) que trae la migración por ETL. Así el "ID"
    del maestro NUNCA es el CUIL ni un N° de solicitud (H-169)."""
    return f"CL-{pk:06d}"


def codigo_cliente_provisorio() -> str:
    """Placeholder único para el id_cliente antes de conocer el PK (la columna es NOT NULL + unique).
    Se reemplaza por `codigo_cliente(pk)` tras el flush; el uuid evita choques entre altas concurrentes."""
    return f"TMP-{uuid.uuid4().hex[:10]}"
