"""Creación de entidades con identificador único generado como 'el primer libre',
tolerante a concurrencia multi-usuario.

El problema: calcular 'el próximo número libre' y luego insertar es un TOCTOU. Dos requests
simultáneos leen el mismo hueco, ambos arman el mismo número y el segundo INSERT choca con la
constraint única (Error 500).

La solución correcta NO es un lock aplicativo (que no escala y puede quedar colgado): es dejar que
la **constraint única de la base sea el árbitro** y **reintentar** ante el conflicto. Cada intento
va dentro de un SAVEPOINT (`begin_nested`), así una colisión sólo descarta ese intento y no rompe la
transacción externa (ni el trabajo ya hecho). Es idempotente respecto del número: el resultado final
siempre es un identificador único válido, sin importar cuántos requests compitan.
"""
from typing import Callable, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

T = TypeVar("T")


def crear_con_numero_unico(db: Session, gen_numero: Callable[[], str],
                           construir: Callable[[str], T], intentos: int = 8) -> T:
    """Crea una entidad con número/código único, reintentando ante colisión concurrente.

    - `gen_numero()` lee la DB y devuelve el próximo número/código libre.
    - `construir(numero)` arma y `db.add()` la entidad (y lo que dependa del número) y la devuelve.

    Cada intento corre en un SAVEPOINT y fuerza el INSERT con `flush()`; si otro request tomó ese
    número entremedio, la `IntegrityError` revierte sólo el savepoint y se reintenta con un número
    fresco. Tras `intentos` colisiones consecutivas (contención extrema) se propaga el error.
    """
    ultimo: IntegrityError | None = None
    for _ in range(max(1, intentos)):
        numero = gen_numero()
        try:
            with db.begin_nested():
                obj = construir(numero)
                db.flush()
            return obj
        except IntegrityError as e:          # otro request tomó ese número → reintentar
            ultimo = e
    assert ultimo is not None
    raise ultimo
