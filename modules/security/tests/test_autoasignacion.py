"""Nadie se asigna roles ni grupos a sí mismo (revisión de seguridad 2026-10)."""
import pytest
from fastapi import HTTPException

from app.routers.users import _no_a_si_mismo


def test_asignarse_roles_a_uno_mismo_se_rechaza():
    with pytest.raises(HTTPException) as e:
        _no_a_si_mismo(7, "7")
    assert e.value.status_code == 403


@pytest.mark.parametrize("quien", ["8", None, ""])
def test_a_otro_usuario_o_sin_identidad_se_permite(quien):
    _no_a_si_mismo(7, quien)
