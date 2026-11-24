"""Catálogo de objetos aprobables por módulo y reglas por defecto.

Como el catálogo de permisos en Seguridad, cada módulo declara acá qué objetos pasan por el
workflow. La regla por defecto es un nivel `APROBAR` con cuatro-ojos. En Créditos arranca INACTIVA (con un único
administrador el sistema opera sin bloquearse, H-141); los pagos de Tesorería arrancan ACTIVOS.
"""
from sqlalchemy.orm import Session

from app import models

ROLES = ("APROBAR", "SUPERVISAR")   # permisos `<modulo>:aprobaciones:aprobar|supervisar` en Seguridad

CATALOGO: dict[str, list[tuple]] = {
    # (objeto, nombre, descripción[, activa por defecto]) — sin el cuarto valor, arranca inactiva.
    "creditos": [
        ("LINEA", "Publicación de línea de crédito", "Aprobar/publicar una versión de línea (Configurar Créditos)"),
        ("SOLICITUD", "Aprobación de solicitud de crédito", "Resolver una solicitud EN_EVALUACION"),
        ("DESEMBOLSO", "Otorgamiento / desembolso de contrato", "Aprobar el desembolso de un crédito"),
        ("REFINANCIACION", "Refinanciación de contrato", "Aprobar una refinanciación"),
    ],
    # Mover dinero exige aprobación desde el primer día: la regla arranca ACTIVA (un nivel del tesorero).
    "tesoreria": [
        ("LOTE_PAGO", "Aprobación de lote de pagos", "Aprobar el envío de un lote de pagos por Interbanking", True),
    ],
}


# Variables que cada proceso ofrece para las condiciones de las decisiones del editor gráfico.
# Hoy sólo sirven para diseñar y validar: el motor que las evalúa llega con la fase 3 (cada módulo
# pasará a declararlas él mismo). tipo: numero | texto | opcion | booleano.
VARIABLES: dict[tuple[str, str], dict[str, dict]] = {
    ("creditos", "SOLICITUD"): {
        "monto": {"nombre": "Monto solicitado", "tipo": "numero"},
        "plazo": {"nombre": "Plazo (cuotas)", "tipo": "numero"},
        "origen": {"nombre": "Origen", "tipo": "opcion", "opciones": ["PORTAL", "SUCURSAL"]},
        "linea": {"nombre": "Línea de crédito", "tipo": "texto"},
    },
    ("creditos", "DESEMBOLSO"): {
        "monto": {"nombre": "Monto a desembolsar", "tipo": "numero"},
    },
    ("creditos", "REFINANCIACION"): {
        "monto": {"nombre": "Saldo refinanciado", "tipo": "numero"},
        "plazo": {"nombre": "Plazo nuevo (cuotas)", "tipo": "numero"},
    },
    ("creditos", "LINEA"): {},
    ("tesoreria", "LOTE_PAGO"): {
        "importe_total": {"nombre": "Importe total del lote", "tipo": "numero"},
        "cantidad_pagos": {"nombre": "Cantidad de pagos", "tipo": "numero"},
        "origen": {"nombre": "Origen del lote", "tipo": "opcion", "opciones": ["CREDITOS", "CONCILIACION", "MANUAL"]},
    },
}


def sembrar_reglas(db: Session) -> int:
    """Crea las reglas del catálogo que falten (idempotente). Devuelve cuántas creó."""
    nuevas = 0
    for modulo, objetos in CATALOGO.items():
        for objeto, nombre, descripcion, *resto in objetos:
            activa = bool(resto[0]) if resto else False
            if db.query(models.WorkflowRegla).filter_by(modulo=modulo, objeto=objeto).first():
                continue
            regla = models.WorkflowRegla(modulo=modulo, objeto=objeto, nombre=nombre,
                                         descripcion=descripcion, activo=activa)
            regla.niveles.append(models.WorkflowNivel(orden=1, nombre="Aprobación", rol="APROBAR",
                                                      cuatro_ojos=True))
            db.add(regla)
            nuevas += 1
    db.commit()
    return nuevas


def serial_regla(r: models.WorkflowRegla) -> dict:
    return {
        "id": r.id, "modulo": r.modulo, "objeto": r.objeto, "nombre": r.nombre,
        "descripcion": r.descripcion, "activo": r.activo,
        "niveles": [{
            "id": n.id, "orden": n.orden, "nombre": n.nombre, "rol": n.rol, "cuatroOjos": n.cuatro_ojos,
            "usuarios": [{"id": u.id, "username": u.username, "modo": u.modo} for u in n.usuarios],
        } for n in sorted(r.niveles, key=lambda x: x.orden)],
    }
