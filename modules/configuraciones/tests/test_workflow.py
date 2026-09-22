"""Definición del workflow de aprobaciones."""
from app import models


def _reglas(client, h, modulo="creditos"):
    return client.get(f"/api/configuraciones/workflow?modulo={modulo}", headers=h).json()


def _linea(client, h):
    return next(r for r in _reglas(client, h)["reglas"] if r["objeto"] == "LINEA")


def test_listar_siembra_el_catalogo_inactivo(client, admin):
    d = _reglas(client, admin)
    assert [r["objeto"] for r in d["reglas"]] == ["LINEA", "SOLICITUD", "DESEMBOLSO", "REFINANCIACION"]
    assert all(not r["activo"] and len(r["niveles"]) == 1 for r in d["reglas"])
    assert d["reglas"][0]["niveles"][0] == {**d["reglas"][0]["niveles"][0], "orden": 1, "rol": "APROBAR", "cuatroOjos": True}
    assert d["roles"] == ["APROBAR", "SUPERVISAR"] and d["puedeEditar"] is True


def test_el_lector_ve_pero_no_edita(client, lector):
    r = _linea(client, lector)
    assert _reglas(client, lector)["puedeEditar"] is False
    assert client.put(f"/api/configuraciones/workflow/reglas/{r['id']}", headers=lector,
                      json={"activo": True}).status_code == 403


def test_activar_y_sumar_un_nivel_de_supervision(client, admin):
    r = _linea(client, admin)
    r = client.put(f"/api/configuraciones/workflow/reglas/{r['id']}", headers=admin, json={"activo": True}).json()
    assert r["activo"] is True
    r = client.post(f"/api/configuraciones/workflow/reglas/{r['id']}/niveles", headers=admin,
                    json={"nombre": "Gerencia", "rol": "supervisar", "cuatroOjos": True}).json()
    assert [(n["orden"], n["rol"]) for n in r["niveles"]] == [(1, "APROBAR"), (2, "SUPERVISAR")]


def test_rol_invalido_es_422(client, admin):
    r = _linea(client, admin)
    assert client.post(f"/api/configuraciones/workflow/reglas/{r['id']}/niveles", headers=admin,
                       json={"rol": "ADMG"}).status_code == 422
    nid = r["niveles"][0]["id"]
    assert client.put(f"/api/configuraciones/workflow/niveles/{nid}", headers=admin,
                      json={"nombre": "x", "rol": "ADMG"}).status_code == 422


def test_borrar_nivel_recompacta_y_no_deja_la_regla_vacia(client, admin):
    r = _linea(client, admin)
    for nombre in ("Dos", "Tres"):
        r = client.post(f"/api/configuraciones/workflow/reglas/{r['id']}/niveles", headers=admin, json={"nombre": nombre}).json()
    r = client.delete(f"/api/configuraciones/workflow/niveles/{r['niveles'][1]['id']}", headers=admin).json()
    assert [(n["orden"], n["nombre"]) for n in r["niveles"]] == [(1, "Aprobación"), (2, "Tres")]
    client.delete(f"/api/configuraciones/workflow/niveles/{r['niveles'][1]['id']}", headers=admin)
    ultimo = _linea(client, admin)["niveles"][0]["id"]
    assert client.delete(f"/api/configuraciones/workflow/niveles/{ultimo}", headers=admin).status_code == 409


def test_overrides_por_usuario(client, admin, db):
    nid = _linea(client, admin)["niveles"][0]["id"]
    r = client.post(f"/api/configuraciones/workflow/niveles/{nid}/usuarios", headers=admin,
                    json={"username": " pz.gerente ", "modo": "INCLUIR"}).json()
    assert r["niveles"][0]["usuarios"][0]["username"] == "pz.gerente"
    # el mismo usuario cambia de modo, no se duplica
    r = client.post(f"/api/configuraciones/workflow/niveles/{nid}/usuarios", headers=admin,
                    json={"username": "pz.gerente", "modo": "EXCLUIR"}).json()
    usuarios = r["niveles"][0]["usuarios"]
    assert len(usuarios) == 1 and usuarios[0]["modo"] == "EXCLUIR"
    assert client.post(f"/api/configuraciones/workflow/niveles/{nid}/usuarios", headers=admin,
                       json={"username": "x", "modo": "QUIZAS"}).status_code == 422
    r = client.delete(f"/api/configuraciones/workflow/usuarios/{usuarios[0]['id']}", headers=admin).json()
    assert r["niveles"][0]["usuarios"] == []
    assert db.query(models.WorkflowNivelUsuario).count() == 0


def test_inexistentes_son_404(client, admin):
    assert client.put("/api/configuraciones/workflow/reglas/999", headers=admin, json={}).status_code == 404
    assert client.delete("/api/configuraciones/workflow/niveles/999", headers=admin).status_code == 404
    assert client.delete("/api/configuraciones/workflow/usuarios/999", headers=admin).status_code == 404
