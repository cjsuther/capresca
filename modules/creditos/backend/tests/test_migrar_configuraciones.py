"""Migración de impuestos, índices, feriados y reglas del workflow de Créditos a Configuraciones."""
from sqlalchemy import text

from app.core.database import engine
from app.etl import migrar_configuraciones as mig

TABLAS_VIEJAS = """
CREATE TABLE impuestos (id INTEGER PRIMARY KEY, codigo VARCHAR, nombre VARCHAR, tipo VARCHAR, alicuota NUMERIC,
  base VARCHAR, cuenta_contable VARCHAR, jurisdiccion VARCHAR, vigente_desde DATE, vigente_hasta DATE, activo BOOLEAN);
CREATE TABLE indices_referencia (id INTEGER PRIMARY KEY, codigo VARCHAR, nombre VARCHAR, valor NUMERIC, fuente VARCHAR,
  fecha_valor DATE, activo BOOLEAN);
CREATE TABLE feriados (id INTEGER PRIMARY KEY, pais VARCHAR, fecha DATE, nombre VARCHAR, tipo VARCHAR, origen VARCHAR,
  activo BOOLEAN);
CREATE TABLE pp_workflow_regla (id VARCHAR PRIMARY KEY, objeto VARCHAR, nombre VARCHAR, descripcion VARCHAR, activo BOOLEAN);
CREATE TABLE pp_workflow_nivel (id VARCHAR PRIMARY KEY, regla_id VARCHAR, orden INTEGER, nombre VARCHAR, rol VARCHAR,
  cuatro_ojos BOOLEAN);
CREATE TABLE pp_workflow_nivel_usuario (id VARCHAR PRIMARY KEY, nivel_id VARCHAR, username VARCHAR, modo VARCHAR);
INSERT INTO impuestos VALUES (1, 'IVA21', 'IVA 21%', 'IVA', 21, 'INTERES', '2.1.07.01', '', '2026-01-01', NULL, 1);
INSERT INTO indices_referencia VALUES (1, 'BADLAR', 'BADLAR', 52.5, 'BCRA', NULL, 0);
INSERT INTO feriados VALUES (1, 'AR', '2026-06-17', 'Güemes', 'TRASLADABLE', 'MANUAL', 1);
INSERT INTO pp_workflow_regla VALUES ('r1', 'LINEA', 'Publicación', '', 1);
INSERT INTO pp_workflow_nivel VALUES ('n1', 'r1', 1, 'Analista', 'ADMG', 1);
INSERT INTO pp_workflow_nivel VALUES ('n2', 'r1', 2, 'Gerencia', 'SUPERVISAR', 0);
INSERT INTO pp_workflow_nivel_usuario VALUES ('u1', 'n1', 'pz.juan', 'EXCLUIR');
"""


def _crear_tablas_viejas():
    with engine.begin() as conn:
        for sql in TABLAS_VIEJAS.strip().split(";"):
            if sql.strip():
                conn.execute(text(sql))


def _borrar_tablas_viejas():
    with engine.begin() as conn:
        for t in ("impuestos", "indices_referencia", "feriados", "pp_workflow_regla", "pp_workflow_nivel",
                  "pp_workflow_nivel_usuario"):
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))


def test_arma_el_lote_desde_las_tablas_viejas():
    _crear_tablas_viejas()
    try:
        lote = mig.leer()
    finally:
        _borrar_tablas_viejas()
    assert lote["modulo"] == "creditos"
    assert lote["impuestos"][0] == {**lote["impuestos"][0], "codigo": "IVA21", "alicuota": 21.0,
                                    "vigente_desde": "2026-01-01", "activo": True}
    assert lote["indices"][0]["valor"] == 52.5 and lote["indices"][0]["activo"] is False
    assert lote["feriados"] == [{"pais": "AR", "fecha": "2026-06-17", "nombre": "Güemes", "tipo": "TRASLADABLE",
                                 "origen": "MANUAL", "activo": True}]
    regla = lote["workflow"][0]
    assert regla["objeto"] == "LINEA" and regla["activo"] is True
    # un perfil VFP que hubiera quedado como rol pasa a APROBAR; las excepciones viajan con su nivel
    assert [(n["orden"], n["rol"], n["cuatro_ojos"]) for n in regla["niveles"]] == [(1, "APROBAR", True), (2, "SUPERVISAR", False)]
    assert regla["niveles"][0]["usuarios"] == [{"username": "pz.juan", "modo": "EXCLUIR"}]


def test_sin_tablas_viejas_no_hay_nada_que_migrar():
    lote = mig.leer()
    assert (lote["impuestos"], lote["indices"], lote["feriados"], lote["workflow"]) == ([], [], [], [])


def test_envia_el_lote_con_la_clave_interna(monkeypatch):
    enviado = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"impuestos": 1, "indices": 1, "feriados": 1, "reglas": 1}

    def post(url, json, headers, timeout):
        enviado.update(url=url, lote=json, headers=headers)
        return Resp()

    monkeypatch.setattr(mig.httpx, "post", post)
    monkeypatch.setattr(mig.get_settings(), "configuraciones_internal_api_key", "clave-x")
    _crear_tablas_viejas()
    try:
        r = mig.migrar()
    finally:
        _borrar_tablas_viejas()
    assert enviado["url"].endswith("/internal/configuraciones/importar")
    assert enviado["headers"] == {"X-Api-Key": "clave-x"}
    assert r["importados"]["reglas"] == 1 and r["leidos"]["feriados"] == 1


def test_dry_run_no_envia(monkeypatch):
    monkeypatch.setattr(mig.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debía enviar")))
    assert mig.migrar(dry_run=True) == {"dry_run": True, "leidos": {"impuestos": 0, "indices": 0, "feriados": 0, "workflow": 0}}
