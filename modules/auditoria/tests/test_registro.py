"""Alta de eventos (gateway y módulos), enmascarado y consulta."""
from datetime import datetime, timedelta, timezone

from app import models
from app.services import enmascarar, registro
from tests.conftest import gateway

INTERNA = "/internal/auditoria/eventos"
API = "/api/auditoria/eventos"


def evento(**kw):
    base = {"usuario": "ana", "usuario_id": 7, "modulo": "creditos", "entidad": "Contrato",
            "entidad_id": "CTO-1", "metodo": "PUT", "ruta": "/api/creditos/contratos/CTO-1",
            "estado_http": 200, "origen": "MODULO", "descripcion": "Cambio de tasa"}
    base.update(kw)
    return base


# ── Alta ─────────────────────────────────────────────────────────────────────────────────────────

def test_la_api_interna_exige_la_clave(client):
    assert client.post(INTERNA, json={"eventos": [evento()]}).status_code == 401
    assert client.post(INTERNA, headers={"X-Api-Key": "otra"}, json={"eventos": [evento()]}).status_code == 401


def test_registra_un_lote_de_eventos(client, interna, db):
    r = client.post(INTERNA, headers=interna, json={"eventos": [evento(), evento(entidad_id="CTO-2")]})
    assert r.status_code == 201 and r.json()["registrados"] == 2
    assert db.query(models.Evento).count() == 2


def test_la_operacion_se_deduce_del_metodo_y_de_la_ruta(client, interna, db):
    client.post(INTERNA, headers=interna, json={"eventos": [
        evento(metodo="POST", ruta="/api/creditos/contratos"),                      # alta
        evento(metodo="POST", ruta="/api/tesoreria/lotes/1/aprobar"),               # acción de negocio
        evento(metodo="DELETE", ruta="/api/security/users/3"),
        evento(metodo="PUT", ruta="/api/clientes/clients/3"),
        evento(metodo="POST", ruta="/api/auth/login", operacion="ACCESO"),          # declarada por quien registra
    ]})
    assert [e.operacion for e in db.query(models.Evento).order_by(models.Evento.id).all()] == [
        "ALTA", "ACCION", "BAJA", "MODIFICACION", "ACCESO"]


def test_el_error_queda_marcado_como_fallido(client, interna, db):
    client.post(INTERNA, headers=interna, json={"eventos": [evento(estado_http=403)]})
    e = db.query(models.Evento).one()
    assert e.exito is False


# ── Enmascarado ──────────────────────────────────────────────────────────────────────────────────

def test_no_se_guardan_claves_y_los_datos_sensibles_van_parciales(client, interna, db):
    client.post(INTERNA, headers=interna, json={"eventos": [evento(cambios={
        "password": ["vieja", "nueva"], "cbu": ["", "2850590940090418135201"],
        "email": ["a@x.com", "b@x.com"], "cuil": [None, "20301234569"], "monto": [100, 200]})]})
    c = db.query(models.Evento).one().cambios
    assert c["password"] == ["•••", "•••"]
    assert c["cbu"] == ["", "•••5201"]
    assert c["cuil"] == [None, "•••4569"]
    assert c["email"] == ["a@x.com", "b@x.com"] and c["monto"] == [100, 200]


def test_enmascara_tambien_adentro_de_estructuras_y_recorta_lo_enorme():
    c = enmascarar.cambios({"datos": [{"token": "abc", "nombre": "Ana"}, {"token": "xyz", "nombre": "Ana"}],
                            "obs": ["x" * 900, "y"]})
    assert c["datos"][0]["token"] == "•••" and c["datos"][1]["nombre"] == "Ana"
    assert c["obs"][0].endswith("…") and len(c["obs"][0]) == 501


# ── Consulta ─────────────────────────────────────────────────────────────────────────────────────

def test_la_consulta_pide_permiso(client, interna):
    assert client.get(API).status_code == 401
    assert client.get(API, headers=gateway("ana", "otra:cosa")).status_code == 403


def test_filtra_por_usuario_modulo_operacion_y_texto(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [
        evento(usuario="ana", modulo="creditos", entidad_id="CTO-1"),
        evento(usuario="beto", modulo="tesoreria", entidad="Lote", entidad_id="LOT-9", metodo="POST",
               ruta="/api/tesoreria/lotes/9/enviar", descripcion="Envío del lote"),
        evento(usuario="beto", modulo="tesoreria", entidad="Lote", entidad_id="LOT-9", estado_http=409),
    ]})
    assert client.get(f"{API}?usuario=beto", headers=auditor).json()["total"] == 2
    assert client.get(f"{API}?modulo=creditos", headers=auditor).json()["total"] == 1
    assert client.get(f"{API}?operacion=ACCION", headers=auditor).json()["total"] == 1
    assert client.get(f"{API}?texto=LOT-9", headers=auditor).json()["total"] == 2
    assert client.get(f"{API}?solo_errores=true", headers=auditor).json()["total"] == 1
    assert client.get(f"{API}?entidad=Lote&entidad_id=LOT-9", headers=auditor).json()["total"] == 2


def test_lista_lo_mas_nuevo_primero_y_pagina(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [evento(entidad_id=f"CTO-{i}") for i in range(1, 6)]})
    d = client.get(f"{API}?limit=2", headers=auditor).json()
    assert d["total"] == 5 and len(d["items"]) == 2
    assert d["items"][0]["entidadId"] == "CTO-5"
    assert client.get(f"{API}?limit=2&offset=4", headers=auditor).json()["items"][0]["entidadId"] == "CTO-1"


def test_filtra_por_fechas(client, interna, auditor, db):
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    client.post(INTERNA, headers=interna, json={"eventos": [
        evento(entidad_id="VIEJO", fecha=(ayer - timedelta(days=40)).isoformat()),
        evento(entidad_id="HOY")]})
    hoy = datetime.now(timezone.utc).date().isoformat()
    d = client.get(f"{API}?desde={hoy}", headers=auditor).json()
    assert [i["entidadId"] for i in d["items"]] == ["HOY"]


def test_el_detalle_cruza_lo_del_gateway_con_lo_del_modulo(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [
        evento(origen="GATEWAY", request_id="req-1", entidad="", entidad_id=""),
        evento(origen="MODULO", request_id="req-1", cambios={"tasa": [50, 52]})]})
    lista = client.get(API, headers=auditor).json()["items"]
    detalle = client.get(f"{API}/{lista[0]['id']}", headers=auditor).json()
    assert detalle["requestId"] == "req-1"
    assert [r["origen"] for r in detalle["relacionados"]] == ["GATEWAY"]
    assert client.get(f"{API}/99999", headers=auditor).status_code == 404


def test_historia_de_un_registro(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [
        evento(entidad_id="CTO-1", descripcion="alta"), evento(entidad_id="CTO-1", descripcion="cambio"),
        evento(entidad_id="CTO-2")]})
    d = client.get("/api/auditoria/registros/creditos/Contrato/CTO-1", headers=auditor).json()
    assert d["total"] == 2 and {i["descripcion"] for i in d["items"]} == {"alta", "cambio"}


def test_resumen_para_los_filtros(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [evento(), evento(modulo="tesoreria")]})
    r = client.get(f"{API}/resumen", headers=auditor).json()
    assert r["total"] == 2 and r["retencionDias"] == 1825
    assert {m["valor"] for m in r["modulos"]} == {"creditos", "tesoreria"}


def test_el_registro_no_se_puede_editar_ni_borrar(client, interna, auditor):
    client.post(INTERNA, headers=interna, json={"eventos": [evento()]})
    assert client.delete(f"{API}/1", headers=auditor).status_code == 405
    assert client.put(f"{API}/1", headers=auditor, json={}).status_code == 405


# ── Retención ────────────────────────────────────────────────────────────────────────────────────

def test_la_purga_se_lleva_lo_que_supera_la_retencion(client, interna, db):
    viejo = (datetime.now(timezone.utc) - timedelta(days=2000)).isoformat()
    client.post(INTERNA, headers=interna, json={"eventos": [evento(fecha=viejo), evento()]})
    assert registro.purgar(db) == 1
    assert [e.entidad_id for e in db.query(models.Evento).all()] == ["CTO-1"]
