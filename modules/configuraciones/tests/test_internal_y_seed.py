"""API interna (la que consume Créditos) e importación / siembra inicial."""
from datetime import date

import pytest

from app import models
from app.seed import sembrar


@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "otra"}])
def test_sin_clave_valida_es_401(client, headers):
    assert client.get("/internal/configuraciones/impuestos", headers=headers).status_code == 401


def test_sin_clave_configurada_la_api_interna_queda_cerrada(client, monkeypatch):
    monkeypatch.setattr("app.dependencies.auth.settings.internal_api_key", "")
    assert client.get("/internal/configuraciones/impuestos", headers={"X-Api-Key": ""}).status_code == 401


def test_lectura_de_catalogos(client, interna, db):
    sembrar(db)
    imp = client.get("/internal/configuraciones/impuestos", headers=interna).json()["items"]
    assert {i["codigo"] for i in imp} == {"IVA21", "IVA105", "IIBB-CAT", "SELLOS"}
    assert client.get("/internal/configuraciones/indices/badlar", headers=interna).json()["valor"] == 45.0
    # dado de baja sigue respondiendo su valor (una línea publicada no pasa a cotizar sólo el margen)
    db.query(models.IndiceReferencia).filter_by(codigo="TPM").update({"activo": False}); db.commit()
    tpm = client.get("/internal/configuraciones/indices/TPM", headers=interna).json()
    assert tpm["valor"] == 40.0 and tpm["activo"] is False
    assert client.get("/internal/configuraciones/indices/NOEXISTE", headers=interna).status_code == 404


def test_feriados_por_rango_solo_activos(client, interna, db):
    db.add_all([models.Feriado(pais="AR", fecha=date(2026, 5, 25), nombre="Revolución"),
                models.Feriado(pais="AR", fecha=date(2026, 6, 20), nombre="Belgrano", activo=False),
                models.Feriado(pais="UY", fecha=date(2026, 5, 18), nombre="Batalla de Las Piedras")])
    db.commit()
    r = client.get("/internal/configuraciones/feriados?pais=ar&desde=2026-05-01&hasta=2026-06-30", headers=interna).json()
    assert r == {"pais": "AR", "fechas": ["2026-05-25"]}
    assert client.get("/internal/configuraciones/feriados?desde=2026-06-30&hasta=2026-05-01",
                      headers=interna).status_code == 422


def test_regla_de_workflow_por_modulo_y_objeto(client, interna):
    r = client.get("/internal/configuraciones/workflow/creditos/linea", headers=interna).json()
    assert r["objeto"] == "LINEA" and r["activo"] is False and r["niveles"][0]["rol"] == "APROBAR"
    assert client.get("/internal/configuraciones/workflow/creditos/OTRO", headers=interna).status_code == 404


IMPORTACION = {
    "modulo": "creditos",
    "impuestos": [{"codigo": "iva21", "nombre": "IVA general", "alicuota": 21, "cuenta_contable": "2.1.07.01"}],
    "indices": [{"codigo": "BADLAR", "nombre": "BADLAR", "valor": 52.5, "fuente": "BCRA"}],
    "feriados": [{"fecha": "2026-06-17", "nombre": "Güemes", "tipo": "TRASLADABLE", "origen": "MANUAL"}],
    "workflow": [{"objeto": "LINEA", "activo": True, "niveles": [
        {"orden": 1, "nombre": "Analista", "rol": "APROBAR", "usuarios": [{"username": "pz.x", "modo": "EXCLUIR"}]},
        {"orden": 2, "nombre": "Gerencia", "rol": "SUPERVISAR"}]}],
}


def test_importar_es_idempotente_y_pisa_por_clave_natural(client, interna, db):
    sembrar(db)   # la base nueva ya trae los valores por defecto
    for _ in range(2):
        r = client.post("/internal/configuraciones/importar", headers=interna, json=IMPORTACION)
        assert r.status_code == 200, r.text
    assert r.json() == {"impuestos": 1, "indices": 1, "feriados": 1, "reglas": 1}
    iva = db.query(models.Impuesto).filter_by(codigo="IVA21").one()
    assert iva.nombre == "IVA general"
    assert db.query(models.IndiceReferencia).filter_by(codigo="BADLAR").one().valor == 52.5
    assert db.query(models.Feriado).filter_by(fecha=date(2026, 6, 17)).count() == 1
    linea = client.get("/internal/configuraciones/workflow/creditos/LINEA", headers=interna).json()
    assert linea["activo"] is True
    assert [(n["orden"], n["rol"]) for n in linea["niveles"]] == [(1, "APROBAR"), (2, "SUPERVISAR")]
    assert linea["niveles"][0]["usuarios"][0]["modo"] == "EXCLUIR"


def test_siembra_idempotente_que_no_pisa_lo_cargado(db):
    db.add(models.Impuesto(codigo="PROPIO", nombre="Impuesto propio", alicuota=3))
    db.commit()
    sembrar(db)
    sembrar(db)
    assert [i.codigo for i in db.query(models.Impuesto).all()] == ["PROPIO"]   # no mezcla los de fábrica
    assert db.query(models.IndiceReferencia).count() == 3
    assert db.query(models.WorkflowRegla).count() == 4
    hoy = date.today()
    anios = {f.year for (f,) in db.query(models.Feriado.fecha).all()}
    assert anios == {hoy.year, hoy.year + 1, hoy.year + 2}
