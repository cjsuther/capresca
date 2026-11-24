"""Vista lista del workflow (reglas en serie): sólo lectura desde el editor gráfico."""
import pytest


def _reglas(client, h, modulo="creditos"):
    return client.get(f"/api/configuraciones/workflow?modulo={modulo}", headers=h).json()


def test_listar_siembra_el_catalogo_inactivo(client, admin):
    d = _reglas(client, admin)
    assert [r["objeto"] for r in d["reglas"]] == ["LINEA", "SOLICITUD", "DESEMBOLSO", "REFINANCIACION"]
    assert all(not r["activo"] and len(r["niveles"]) == 1 for r in d["reglas"])
    assert d["reglas"][0]["niveles"][0] == {**d["reglas"][0]["niveles"][0], "orden": 1, "rol": "APROBAR", "cuatroOjos": True}
    assert d["roles"] == ["APROBAR", "SUPERVISAR"]


def test_la_vista_lista_no_edita_y_apunta_al_proceso(client, admin):
    d = _reglas(client, admin)
    assert d["puedeEditar"] is False
    assert all(r["procesoId"] and r["versionPublicada"] == 1 for r in d["reglas"])


@pytest.mark.parametrize("metodo,ruta", [
    ("put", "/api/configuraciones/workflow/reglas/1"),
    ("post", "/api/configuraciones/workflow/reglas/1/niveles"),
    ("put", "/api/configuraciones/workflow/niveles/1"),
    ("delete", "/api/configuraciones/workflow/niveles/1"),
    ("post", "/api/configuraciones/workflow/niveles/1/usuarios"),
    ("delete", "/api/configuraciones/workflow/usuarios/1"),
])
def test_las_escrituras_viejas_ya_no_existen(client, admin, metodo, ruta):
    _reglas(client, admin)
    kw = {"json": {}} if metodo in ("put", "post") else {}
    assert getattr(client, metodo)(ruta, headers=admin, **kw).status_code in (404, 405)
