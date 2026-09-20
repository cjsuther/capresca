"""Idempotencia de operación por Idempotency-Key.

Distinta de la unicidad del número (que evita ids repetidos): esto dedup-lica la OPERACIÓN. Si el
cliente reintenta el mismo pedido con la misma clave (doble clic, retry de red), se devuelve el MISMO
resultado en lugar de crear un segundo registro.

Contrato: el cliente manda un header `Idempotency-Key` (un UUID que él genera) en la alta mutante.
- Sin clave → se ejecuta normal (sin idempotencia).
- Con clave nueva → se reserva la clave, se ejecuta, se guarda la respuesta y se devuelve.
- Con clave ya vista → se devuelve la respuesta guardada (no se vuelve a ejecutar).
- Con clave reservada pero aún sin respuesta (dos requests idénticos en carrera) → 409 'en proceso'.

La reserva usa la PK única de `pp_idempotencia` como árbitro (mismo criterio que la unicidad
concurrente): dos requests con la misma clave no pueden ambos reservarla.
"""
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models_productos as m


def con_idempotencia(db: Session, clave: str | None, endpoint: str,
                     ejecutar: Callable[[], dict], usuario: str = "") -> dict:
    if not clave:
        return ejecutar()

    prev = db.get(m.PPIdempotencia, clave)
    if prev is not None:
        if prev.endpoint and prev.endpoint != endpoint:
            raise HTTPException(422, "Idempotency-Key ya usada para otra operación distinta.")
        if prev.respuesta is not None:
            return prev.respuesta                       # replay: misma respuesta, sin duplicar
        raise HTTPException(409, "Operación en proceso con la misma Idempotency-Key.")

    # Reservar la clave (la PK única impide que dos requests la tomen a la vez).
    try:
        db.add(m.PPIdempotencia(clave=clave, endpoint=endpoint, usuario=usuario))
        db.commit()
    except IntegrityError:
        db.rollback()
        otra = db.get(m.PPIdempotencia, clave)
        if otra is not None and otra.respuesta is not None:
            return otra.respuesta
        raise HTTPException(409, "Operación en proceso con la misma Idempotency-Key.")

    # Ejecutar la operación real; si falla, liberar la reserva para permitir reintentar.
    try:
        resultado = ejecutar()
    except Exception:
        db.rollback()
        r = db.get(m.PPIdempotencia, clave)
        if r is not None:
            db.delete(r); db.commit()
        raise

    rec = db.get(m.PPIdempotencia, clave)
    if rec is not None:
        rec.respuesta = resultado
        db.commit()
    return resultado
