"""Los procesos automáticos (sin request) también quedan auditados, a nombre del proceso."""
from app.services import auditoria_central as central


def test_como_sistema_pone_y_saca_el_autor():
    assert central.contexto() is None
    with central.como_sistema("cruce-automatico"):
        assert central.contexto()["usuario"] == "sistema:cruce-automatico"
    assert central.contexto() is None
