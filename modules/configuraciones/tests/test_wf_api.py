"""Workflow gráfico versionado: migración de las reglas, borrador/publicación/retiro, permisos,
auditoría y EQUIVALENCIA de la API interna que leen Créditos y Tesorería."""
import copy

import pytest
from sqlalchemy.exc import IntegrityError

from app import models
from app.seed import sembrar
from app.services import wf_procesos
from app.services.workflow import CATALOGO

B = "/api/configuraciones/workflow"
CLAVES_NIVEL = {"id", "orden", "nombre", "rol", "cuatroOjos", "usuarios"}


def _procesos(client, h):
    return client.get(f"{B}/procesos", headers=h).json()["procesos"]


def _proceso(client, h, modulo="tesoreria", objeto="LOTE_PAGO"):
    return next(p for p in _procesos(client, h) if (p["modulo"], p["objeto"]) == (modulo, objeto))


def _interna(client, interna, modulo="tesoreria", objeto="LOTE_PAGO"):
    r = client.get(f"/internal/configuraciones/workflow/{modulo}/{objeto}", headers=interna)
    assert r.status_code == 200
    return r.json()


def _todas_internas(client, interna):
    return {(m, o): _interna(client, interna, m, o) for m, objs in CATALOGO.items() for (o, *_) in objs}


def _borrador(client, h, pid):
    r = client.post(f"{B}/procesos/{pid}/borrador", headers=h, json={})
    assert r.status_code == 201, r.text
    return r.json()


def _guardar(client, h, v, grafo, layout=None):
    r = client.put(f"{B}/versiones/{v['id']}", headers=h,
                   json={"grafo": grafo, "layout": layout or v["layout"], "revision": v["revision"]})
    assert r.status_code == 200, r.text
    return r.json()


def _sumar_supervision(grafo):
    """Agrega un nivel SUPERVISAR al final de la serie (como lo haría el editor)."""
    gr = copy.deepcopy(grafo)
    a_fin = next(c for c in gr["conexiones"] if c["a"] == "fin")
    gr["nodos"].insert(-1, {"id": "sup", "tipo": "aprobacion", "nombre": "Gerencia",
                            "asignar": {"tipo": "rol", "valor": "SUPERVISAR"}, "cuatroOjos": True,
                            "incluir": ["pz.gerente"], "excluir": []})
    a_fin["a"] = "sup"
    gr["conexiones"] += [{"id": "s1", "de": "sup", "a": "fin", "salida": "aprobado"},
                         {"id": "s2", "de": "sup", "a": "inicio", "salida": "rechazado"}]
    return gr


@pytest.fixture
def auditoria(monkeypatch):
    eventos = []
    monkeypatch.setattr(wf_procesos.central, "registrar", lambda **kw: eventos.append(kw))
    return eventos


# ── Migración automática ──
def test_cada_regla_queda_como_version_1_publicada_e_idempotente(client, admin, db):
    ps = _procesos(client, admin)
    assert {(p["modulo"], p["objeto"]) for p in ps} == {(m, o) for m, objs in CATALOGO.items() for (o, *_) in objs}
    assert all(p["publicada"]["numero"] == 1 and p["borrador"] is None for p in ps)
    assert next(p for p in ps if p["objeto"] == "LOTE_PAGO")["habilitado"] is True    # copia `activo`
    assert next(p for p in ps if p["objeto"] == "LINEA")["habilitado"] is False
    _procesos(client, admin)
    sembrar(db)
    assert db.query(models.WfVersion).count() == len(ps)          # no duplica
    assert db.query(models.WorkflowRegla).count() == len(ps)      # no toca las reglas viejas


def test_la_version_migrada_es_la_misma_regla(client, admin, interna):
    p = _proceso(client, admin)
    v = client.get(f"{B}/versiones/{p['publicada']['id']}", headers=admin).json()
    assert v["problemas"] == [] and v["compatibleMotorActual"] is True
    assert [n["tipo"] for n in v["grafo"]["nodos"]] == ["inicio", "aprobacion", "fin"]
    nivel = _interna(client, interna)["niveles"][0]
    ap = v["grafo"]["nodos"][1]
    assert (ap["nombre"], ap["asignar"]["valor"], ap["cuatroOjos"]) == (nivel["nombre"], nivel["rol"], nivel["cuatroOjos"])


def test_la_migracion_respeta_niveles_y_excepciones_existentes(client, admin, db, interna):
    sembrar(db)          # antes de migrar: la regla vieja tiene 2 niveles y excepciones cargadas a mano
    db.query(models.WfVersion).delete()
    db.query(models.WfProceso).delete()
    r = db.query(models.WorkflowRegla).filter_by(modulo="creditos", objeto="SOLICITUD").one()
    r.niveles[0].usuarios.append(models.WorkflowNivelUsuario(username="ana", modo="EXCLUIR"))
    r.niveles.append(models.WorkflowNivel(orden=2, nombre="Gerencia", rol="SUPERVISAR", cuatro_ojos=False))
    db.commit()
    antes = _interna(client, interna, "creditos", "SOLICITUD")
    p = _proceso(client, admin, "creditos", "SOLICITUD")
    v = client.get(f"{B}/versiones/{p['publicada']['id']}", headers=admin).json()
    aps = [n for n in v["grafo"]["nodos"] if n["tipo"] == "aprobacion"]
    assert [(n["nombre"], n["asignar"]["valor"], n["cuatroOjos"], n["excluir"]) for n in aps] == [
        ("Aprobación", "APROBAR", True, ["ana"]), ("Gerencia", "SUPERVISAR", False, [])]
    assert _interna(client, interna, "creditos", "SOLICITUD") == antes


# ── Equivalencia de la API interna (lo que leen Créditos y Tesorería) ──
def test_migrar_no_cambia_nada_de_la_api_interna(client, admin, interna):
    antes = _todas_internas(client, interna)
    _procesos(client, admin)
    assert _todas_internas(client, interna) == antes


def test_publicar_proyecta_en_la_regla_con_el_mismo_formato_y_volver_atras_deja_todo_igual(
        client, admin, interna, auditoria):
    original = _interna(client, interna)
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    v = _guardar(client, admin, v, _sumar_supervision(v["grafo"]))
    r = client.post(f"{B}/versiones/{v['id']}/publicar", headers=admin, json={"nota": "Gerencia firma"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "PUBLICADA" and "Gerencia" in r.json()["diffResumen"]

    dos = _interna(client, interna)
    assert {k: v for k, v in dos.items() if k != "niveles"} == {k: v for k, v in original.items() if k != "niveles"}
    assert all(set(n) == CLAVES_NIVEL for n in dos["niveles"])
    assert dos["niveles"][0] == original["niveles"][0]                       # el nivel 1 conserva su id
    assert [(n["orden"], n["rol"], n["nombre"]) for n in dos["niveles"]] == [(1, "APROBAR", "Aprobación"),
                                                                            (2, "SUPERVISAR", "Gerencia")]
    assert [(u["username"], u["modo"]) for u in dos["niveles"][1]["usuarios"]] == [("pz.gerente", "INCLUIR")]

    # Vuelta atrás: una versión nueva igual a la 1 → la API interna devuelve EXACTAMENTE lo de antes.
    v3 = _borrador(client, admin, p["id"])
    v1 = client.get(f"{B}/versiones/{p['publicada']['id']}", headers=admin).json()
    v3 = _guardar(client, admin, v3, v1["grafo"])
    assert client.post(f"{B}/versiones/{v3['id']}/publicar", headers=admin, json={}).status_code == 200
    assert _interna(client, interna) == original
    assert [e["descripcion"] for e in auditoria] == [
        "Publica la versión 2 del workflow tesoreria/LOTE_PAGO", "Publica la versión 3 del workflow tesoreria/LOTE_PAGO"]


# ── Borradores ──
def test_un_solo_borrador_por_proceso(client, admin):
    p = _proceso(client, admin)
    _borrador(client, admin, p["id"])
    assert client.post(f"{B}/procesos/{p['id']}/borrador", headers=admin, json={}).status_code == 409


def test_el_borrador_clona_la_version_pedida(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    assert v["numero"] == 2 and v["basadaEn"] == 1 and v["estado"] == "BORRADOR"
    assert client.post(f"{B}/procesos/{p['id']}/borrador", headers=admin, json={"desde": 9}).status_code == 409
    client.delete(f"{B}/versiones/{v['id']}", headers=admin)
    assert client.post(f"{B}/procesos/{p['id']}/borrador", headers=admin, json={"desde": 9}).status_code == 404


def test_autosave_guarda_aunque_tenga_errores_y_controla_la_revision(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    roto = copy.deepcopy(v["grafo"])
    roto["nodos"].append({"id": "suelto", "tipo": "notificacion", "nombre": "Avisar"})
    v2 = _guardar(client, admin, v, roto, {**v["layout"], "suelto": {"x": 50, "y": 60}})
    assert v2["revision"] == v["revision"] + 1 and v2["layout"]["suelto"] == {"x": 50.0, "y": 60.0}
    assert {"HUERFANO", "NOTIFICACION_SIN_DESTINO"} <= {x["codigo"] for x in v2["problemas"]}
    assert v2["compatibleMotorActual"] is False
    # Otro guardado con la revisión vieja (otra pestaña / otro usuario): 409, no pisa.
    r = client.put(f"{B}/versiones/{v['id']}", headers=admin, json={"grafo": v["grafo"], "revision": v["revision"]})
    assert r.status_code == 409


def test_una_version_publicada_no_se_edita_ni_se_descarta(client, admin):
    p = _proceso(client, admin)
    vid = p["publicada"]["id"]
    v = client.get(f"{B}/versiones/{vid}", headers=admin).json()
    assert client.put(f"{B}/versiones/{vid}", headers=admin,
                      json={"grafo": v["grafo"], "revision": v["revision"]}).status_code == 409
    assert client.delete(f"{B}/versiones/{vid}", headers=admin).status_code == 409


def test_grafo_mal_formado_es_422(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    r = client.put(f"{B}/versiones/{v['id']}", headers=admin, json={"grafo": {"nodos": "x"}, "revision": v["revision"]})
    assert r.status_code == 422


# ── Publicación ──
def test_no_se_publica_con_errores(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    roto = copy.deepcopy(v["grafo"])
    roto["nodos"][1]["asignar"] = {}
    v = _guardar(client, admin, v, roto)
    r = client.post(f"{B}/versiones/{v['id']}/publicar", headers=admin, json={})
    assert r.status_code == 422
    assert r.json()["detail"]["problemas"][0]["codigo"] == "SIN_ASIGNACION"


def test_no_se_publica_lo_que_el_motor_actual_no_ejecuta(client, admin, interna):
    original = _interna(client, interna)
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    gr = copy.deepcopy(v["grafo"])
    gr["nodos"][1]["asignar"] = {"tipo": "grupo", "valor": "Tesoreros", "id": 4}
    v = _guardar(client, admin, v, gr)
    assert v["problemas"] == [] and v["compatibleMotorActual"] is False
    r = client.post(f"{B}/versiones/{v['id']}/publicar", headers=admin, json={})
    assert r.status_code == 409 and "grupo" in r.json()["detail"]["problemas"][0]
    assert _interna(client, interna) == original


def test_no_se_publica_una_copia_identica(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    assert client.post(f"{B}/versiones/{v['id']}/publicar", headers=admin, json={}).status_code == 409


def test_publicar_retira_la_anterior_y_la_db_impide_dos_publicadas(client, admin, db):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    v = _guardar(client, admin, v, _sumar_supervision(v["grafo"]))
    client.post(f"{B}/versiones/{v['id']}/publicar", headers=admin, json={})
    d = client.get(f"{B}/procesos/{p['id']}", headers=admin).json()
    assert [(x["numero"], x["estado"]) for x in d["versiones"]] == [(2, "PUBLICADA"), (1, "RETIRADA")]
    assert d["versiones"][1]["retiradaPor"] == "ana"
    db.add(models.WfVersion(proceso_id=p["id"], numero=9, estado="PUBLICADA", grafo={}, layout={}))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_editor_arma_borradores_pero_no_publica_y_el_lector_solo_mira(client, editor, lector, admin):
    p = _proceso(client, admin)
    assert client.post(f"{B}/procesos/{p['id']}/borrador", headers=lector, json={}).status_code == 403
    v = _borrador(client, editor, p["id"])
    v = _guardar(client, editor, v, _sumar_supervision(v["grafo"]))
    assert client.post(f"{B}/versiones/{v['id']}/publicar", headers=editor, json={}).status_code == 403
    assert client.post(f"{B}/procesos/{p['id']}/habilitado", headers=editor, json={"habilitado": False}).status_code == 403
    assert client.get(f"{B}/versiones/{v['id']}", headers=lector).json()["puede"] == {"editar": False, "publicar": False}
    assert client.get(f"{B}/catalogo", headers=editor).json()["puede"] == {"editar": True, "publicar": False}
    assert client.get(f"{B}/procesos", headers={"X-User-Id": "3"}).status_code == 403


# ── Retiro y habilitación ──
def test_retirar_deshabilita_y_no_se_republica_solo(client, admin, interna, db, auditoria):
    p = _proceso(client, admin)
    r = client.post(f"{B}/versiones/{p['publicada']['id']}/retirar", headers=admin)
    assert r.status_code == 200 and r.json()["estado"] == "RETIRADA"
    assert _interna(client, interna)["activo"] is False
    sembrar(db)
    p = _proceso(client, admin)
    assert p["publicada"] is None and p["habilitado"] is False
    assert client.post(f"{B}/procesos/{p['id']}/habilitado", headers=admin, json={"habilitado": True}).status_code == 409
    assert "Retira la versión 1" in auditoria[-1]["descripcion"]


def test_habilitar_y_deshabilitar_mueve_activo_de_la_regla(client, admin, interna):
    p = _proceso(client, admin, "creditos", "LINEA")
    r = client.post(f"{B}/procesos/{p['id']}/habilitado", headers=admin, json={"habilitado": True})
    assert r.status_code == 200 and r.json()["habilitado"] is True
    assert _interna(client, interna, "creditos", "LINEA")["activo"] is True
    client.post(f"{B}/procesos/{p['id']}/habilitado", headers=admin, json={"habilitado": False})
    assert _interna(client, interna, "creditos", "LINEA")["activo"] is False


# ── Import interno (ETL de Créditos) ──
def test_lo_importado_por_la_api_interna_queda_como_nueva_version(client, admin, interna):
    _procesos(client, admin)
    r = client.post("/internal/configuraciones/importar", headers=interna, json={
        "modulo": "creditos", "workflow": [{"objeto": "LINEA", "activo": True, "niveles": [
            {"orden": 1, "nombre": "Analista"}, {"orden": 2, "nombre": "Jefe", "rol": "SUPERVISAR"}]}]})
    assert r.status_code == 200
    p = _proceso(client, admin, "creditos", "LINEA")
    assert p["publicada"]["numero"] == 2 and p["habilitado"] is True
    v = client.get(f"{B}/versiones/{p['publicada']['id']}", headers=admin).json()
    assert [n["nombre"] for n in v["grafo"]["nodos"] if n["tipo"] == "aprobacion"] == ["Analista", "Jefe"]


# ── Comparar ──
def test_comparar_dos_versiones(client, admin):
    p = _proceso(client, admin)
    v = _borrador(client, admin, p["id"])
    v = _guardar(client, admin, v, _sumar_supervision(v["grafo"]))
    d = client.get(f"{B}/comparar", headers=admin, params={"a": p["publicada"]["id"], "b": v["id"]}).json()
    assert d["diff"]["nodos"]["agregados"] == ["sup"] and d["a"]["numero"] == 1 and d["b"]["numero"] == 2
    otro = _proceso(client, admin, "creditos", "LINEA")
    assert client.get(f"{B}/comparar", headers=admin,
                      params={"a": otro["publicada"]["id"], "b": v["id"]}).status_code == 422


def test_inexistentes_son_404(client, admin):
    assert client.get(f"{B}/procesos/999", headers=admin).status_code == 404
    assert client.get(f"{B}/versiones/999", headers=admin).status_code == 404
    assert client.post(f"{B}/versiones/999/publicar", headers=admin, json={}).status_code == 404
