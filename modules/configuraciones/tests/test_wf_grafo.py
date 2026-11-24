"""Funciones puras del grafo: validación, proyección al motor actual, conversión, huella y diff."""
import copy

import pytest

from app.services import wf_grafo as g

VARS = {"monto": {"nombre": "Monto", "tipo": "numero"},
        "origen": {"nombre": "Origen", "tipo": "opcion", "opciones": ["PORTAL", "SUCURSAL"]},
        "linea": {"nombre": "Línea", "tipo": "texto"},
        "urgente": {"nombre": "Urgente", "tipo": "booleano"}}


def ap(nid, nombre="Aprobación", rol="APROBAR", **kw):
    return {"id": nid, "tipo": "aprobacion", "nombre": nombre, "asignar": {"tipo": "rol", "valor": rol},
            "cuatroOjos": True, **kw}


def serie(*aprobaciones):
    """Inicio → ap… → Fin, rechazo vuelve al Inicio (lo que genera la migración)."""
    niveles = [{"orden": i, "nombre": n, "rol": r, "cuatroOjos": True, "usuarios": []}
               for i, (n, r) in enumerate(aprobaciones, start=1)]
    return g.grafo_desde_niveles(niveles)[0]


def con_decision():
    return {"schema": 1, "nodos": [
        {"id": "i", "tipo": "inicio"}, ap("a1"), {"id": "d", "tipo": "decision", "nombre": "¿Monto alto?"},
        ap("a2", "Gerencia", "SUPERVISAR"),
        {"id": "n", "tipo": "notificacion", "nombre": "Avisar", "destinatarios": [{"tipo": "iniciador"}]},
        {"id": "ok", "tipo": "fin", "resultado": "APROBADO"}, {"id": "no", "tipo": "fin", "resultado": "RECHAZADO"}],
        "conexiones": [
            {"id": "c1", "de": "i", "a": "a1"},
            {"id": "c2", "de": "a1", "a": "d", "salida": "aprobado"},
            {"id": "c3", "de": "a1", "a": "i", "salida": "rechazado"},
            {"id": "c4", "de": "d", "a": "a2", "condicion": {"modo": "todas", "reglas": [
                {"variable": "monto", "op": ">", "valor": 5000000}]}},
            {"id": "c5", "de": "d", "a": "n", "defecto": True},
            {"id": "c6", "de": "a2", "a": "n", "salida": "aprobado"},
            {"id": "c7", "de": "a2", "a": "no", "salida": "rechazado"},
            {"id": "c8", "de": "n", "a": "ok"}]}


def codigos(grafo, variables=VARS):
    return sorted({p["codigo"] for p in g.errores(g.validar(grafo, variables))})


# ── Validación ──
def test_una_serie_y_un_grafo_con_decision_son_validos():
    assert codigos(serie(("Aprobación", "APROBAR"))) == []
    assert codigos(con_decision()) == []


def test_un_inicio_exacto_y_al_menos_un_fin():
    gr = serie(("A", "APROBAR"))
    gr["nodos"].append({"id": "i2", "tipo": "inicio"})
    gr["conexiones"].append({"id": "x", "de": "i2", "a": "fin"})
    assert "INICIO_UNICO" in codigos(gr)
    gr = serie(("A", "APROBAR"))
    gr["nodos"] = [n for n in gr["nodos"] if n["tipo"] != "fin"]
    gr["conexiones"] = [c for c in gr["conexiones"] if c["a"] != "fin"]
    assert "FIN_REQUERIDO" in codigos(gr)


def test_huerfanos_y_nodos_sin_camino_a_fin():
    gr = serie(("A", "APROBAR"))
    gr["nodos"].append(ap("suelto"))
    cs = codigos(gr)
    assert "HUERFANO" in cs and "SIN_CAMINO_A_FIN" in cs and "SALIDAS_APROBACION" in cs
    probs = g.validar(gr, VARS)
    assert any(p["codigo"] == "HUERFANO" and p["nodo"] == "suelto" for p in probs)


def test_aprobacion_necesita_quien_aprueba_y_sus_dos_salidas():
    gr = serie(("A", "APROBAR"))
    gr["nodos"][1]["asignar"] = {}
    assert "SIN_ASIGNACION" in codigos(gr)
    gr["nodos"][1]["asignar"] = {"tipo": "rol", "valor": "ADMG"}
    assert "ROL_INVALIDO" in codigos(gr)
    gr["nodos"][1]["asignar"] = {"tipo": "grupo", "valor": " "}
    assert "GRUPO_VACIO" in codigos(gr)
    gr = serie(("A", "APROBAR"))
    gr["conexiones"] = [c for c in gr["conexiones"] if c.get("salida") != "rechazado"]
    assert "SALIDAS_APROBACION" in codigos(gr)


def test_usuario_incluido_y_excluido_a_la_vez():
    gr = serie(("A", "APROBAR"))
    gr["nodos"][1].update(incluir=["ana"], excluir=["ana"])
    assert "USUARIO_INCLUIDO_Y_EXCLUIDO" in codigos(gr)


def test_sin_cuatro_ojos_es_solo_un_aviso():
    gr = serie(("A", "APROBAR"))
    gr["nodos"][1]["cuatroOjos"] = False
    assert codigos(gr) == []
    assert [p["codigo"] for p in g.validar(gr, VARS) if p["nivel"] == "aviso"] == ["SIN_CUATRO_OJOS"]


def test_decision_con_defecto_unico_y_condiciones_bien_tipadas():
    gr = con_decision()
    gr["conexiones"][4].pop("defecto")
    gr["conexiones"][4]["condicion"] = {"reglas": [{"variable": "origen", "op": "=", "valor": "PORTAL"}]}
    assert "DECISION_SIN_DEFECTO" in codigos(gr)

    for regla, ok in [({"variable": "monto", "op": ">", "valor": "mucho"}, False),
                      ({"variable": "monto", "op": "contiene", "valor": 3}, False),
                      ({"variable": "nada", "op": "=", "valor": 1}, False),
                      ({"variable": "origen", "op": "=", "valor": "OTRO"}, False),
                      ({"variable": "origen", "op": "en", "valor": ["PORTAL", "SUCURSAL"]}, True),
                      ({"variable": "linea", "op": "contiene", "valor": "Emprend"}, True),
                      ({"variable": "urgente", "op": "=", "valor": True}, True),
                      ({"variable": "urgente", "op": "=", "valor": 1}, False),
                      ({"variable": "monto", "op": ">", "valor": True}, False)]:
        gr = con_decision()
        gr["conexiones"][3]["condicion"]["reglas"] = [regla]
        assert (codigos(gr) == []) is ok, regla


def test_decision_con_una_sola_salida():
    gr = con_decision()
    gr["conexiones"] = [c for c in gr["conexiones"] if c["id"] != "c4"]
    assert "SALIDAS_DECISION" in codigos(gr)


def test_notificacion_necesita_destinatarios():
    gr = con_decision()
    gr["nodos"][4]["destinatarios"] = []
    assert "NOTIFICACION_SIN_DESTINO" in codigos(gr)
    gr["nodos"][4]["destinatarios"] = [{"tipo": "grupo", "valor": ""}]
    assert "DESTINATARIO_INVALIDO" in codigos(gr)


def test_fin_sin_salidas_y_con_resultado():
    gr = serie(("A", "APROBAR"))
    gr["nodos"][-1]["resultado"] = ""
    gr["conexiones"].append({"id": "x", "de": "fin", "a": "inicio"})
    cs = codigos(gr)
    assert "FIN_SIN_RESULTADO" in cs and "FIN_CON_SALIDA" in cs


def test_ciclo_sin_aprobacion_es_error_y_volver_al_inicio_por_rechazo_no():
    gr = con_decision()
    assert codigos(gr) == []           # a1 → (rechazado) → i → a1 pasa por una aprobación
    gr["conexiones"][7] = {"id": "c8", "de": "n", "a": "d"}   # n → d → (defecto) n: vuelta automática
    assert "CICLO_SIN_APROBACION" in codigos(gr)


def test_conexiones_rotas_ids_duplicados_y_tipos_desconocidos():
    gr = serie(("A", "APROBAR"))
    gr["conexiones"].append({"id": "x", "de": "ap1", "a": "fantasma"})
    gr["nodos"].append({"id": "ap1", "tipo": "aprobacion"})
    gr["nodos"].append({"id": "z", "tipo": "subflujo"})
    cs = codigos(gr)
    assert {"CONEXION_ROTA", "ID_DUPLICADO", "TIPO_INVALIDO"} <= set(cs)


def test_salidas_y_condiciones_fuera_de_lugar():
    gr = con_decision()
    gr["conexiones"][0]["salida"] = "aprobado"
    gr["conexiones"][7]["condicion"] = {"reglas": [{"variable": "monto", "op": ">", "valor": 1}]}
    cs = codigos(gr)
    assert "SALIDA_FUERA_DE_APROBACION" in cs and "CONDICION_FUERA_DE_DECISION" in cs


# ── Proyección (lo que se puede publicar hoy) ──
def test_una_serie_se_proyecta_en_niveles():
    gr = serie(("Analista", "APROBAR"), ("Gerencia", "SUPERVISAR"))
    gr["nodos"][2].update(incluir=["zoe"], excluir=["abel"], cuatroOjos=False)
    niveles, motivos = g.proyectar(gr)
    assert motivos == []
    assert niveles == [
        {"orden": 1, "nombre": "Analista", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []},
        {"orden": 2, "nombre": "Gerencia", "rol": "SUPERVISAR", "cuatroOjos": False,
         "usuarios": [{"username": "abel", "modo": "EXCLUIR"}, {"username": "zoe", "modo": "INCLUIR"}]}]


def test_rechazo_a_un_fin_rechazado_tambien_es_serie():
    gr = serie(("A", "APROBAR"))
    gr["nodos"].append({"id": "no", "tipo": "fin", "resultado": "RECHAZADO"})
    next(c for c in gr["conexiones"] if c.get("salida") == "rechazado")["a"] = "no"
    assert g.proyectar(gr)[0] is not None


@pytest.mark.parametrize("cambio,motivo", [
    (lambda gr: gr.update(con_decision()), "decisión"),
    (lambda gr: gr["nodos"][1].update(asignar={"tipo": "grupo", "valor": "Gerencia"}), "grupo"),
    (lambda gr: gr["nodos"].append(ap("suelto")), "fuera de la cadena"),
    (lambda gr: next(n for n in gr["nodos"] if n["tipo"] == "fin").update(resultado="RECHAZADO"), "Fin Aprobado"),
])
def test_lo_que_el_motor_actual_no_ejecuta_no_se_proyecta(cambio, motivo):
    gr = serie(("A", "APROBAR"))
    cambio(gr)
    niveles, motivos = g.proyectar(gr)
    assert niveles is None and any(motivo in m for m in motivos), motivos


def test_sin_aprobaciones_no_se_proyecta():
    gr = {"schema": 1, "nodos": [{"id": "i", "tipo": "inicio"}, {"id": "f", "tipo": "fin", "resultado": "APROBADO"}],
          "conexiones": [{"id": "c", "de": "i", "a": "f"}]}
    assert g.proyectar(gr)[0] is None


def test_ida_y_vuelta_regla_grafo_regla():
    niveles = [{"orden": 1, "nombre": "Uno", "rol": "APROBAR", "cuatroOjos": True,
                "usuarios": [{"username": "b", "modo": "EXCLUIR"}, {"username": "c", "modo": "INCLUIR"}]},
               {"orden": 2, "nombre": "Dos", "rol": "SUPERVISAR", "cuatroOjos": False, "usuarios": []}]
    grafo, layout = g.grafo_desde_niveles(niveles)
    assert codigos(grafo) == [] and set(layout) == {n["id"] for n in grafo["nodos"]}
    assert g.proyectar(grafo) == (niveles, [])


# ── Huella, diff y normalización ──
def test_la_huella_no_depende_del_orden_ni_de_los_ids_de_conexion():
    a = serie(("A", "APROBAR"), ("B", "SUPERVISAR"))
    b = copy.deepcopy(a)
    b["nodos"].reverse()
    b["conexiones"].reverse()
    for i, c in enumerate(b["conexiones"]):
        c["id"] = f"otra{i}"
    assert g.huella(a) == g.huella(b)
    b["nodos"][0]["nombre"] = "cambio"
    assert g.huella(a) != g.huella(b)


def test_comparar_resume_en_castellano():
    a = serie(("A", "APROBAR"))
    b = serie(("A", "APROBAR"), ("Gerencia", "SUPERVISAR"))
    b["nodos"][1]["cuatroOjos"] = False
    d = g.comparar(a, b)
    assert d["nodos"]["agregados"] == ["ap2"]
    assert d["nodos"]["modificados"] == [{"id": "ap1", "campos": ["cuatroOjos"]}]
    assert "+ aprobacion «Gerencia»" in d["resumen"] and not d["iguales"]
    assert g.comparar(a, copy.deepcopy(a))["iguales"]


def test_normalizar_descarta_claves_desconocidas_y_recorta():
    gr = g.normalizar({"nodos": [{"id": " a ", "tipo": "aprobacion", "nombre": "x" * 300, "hack": 1,
                                  "asignar": {"tipo": "rol", "valor": "APROBAR", "otra": 2},
                                  "incluir": ["z", " z ", "a", ""]}],
                       "conexiones": [{"id": "c", "de": "a", "a": "b", "defecto": True,
                                       "condicion": {"reglas": []}, "xss": "<b>"}]})
    n, c = gr["nodos"][0], gr["conexiones"][0]
    assert n["id"] == "a" and "hack" not in n and len(n["nombre"]) == 120
    assert n["asignar"] == {"tipo": "rol", "valor": "APROBAR"} and n["incluir"] == ["a", "z"]
    assert c == {"id": "c", "de": "a", "a": "b", "defecto": True}
    with pytest.raises(ValueError):
        g.normalizar({"nodos": "no"})
    with pytest.raises(ValueError):
        g.normalizar({"nodos": [{"id": str(i)} for i in range(g.MAX_NODOS + 1)]})


def test_layout_sólo_de_nodos_existentes():
    gr = serie(("A", "APROBAR"))
    assert g.normalizar_layout({"ap1": {"x": "10.26", "y": 3}, "otro": {"x": 1, "y": 1}, "fin": {"x": "?"}}, gr) \
        == {"ap1": {"x": 10.3, "y": 3.0}}
