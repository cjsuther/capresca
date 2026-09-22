"""El circuito del módulo: la transacción manda, la definición decide y el asiento sale de ahí."""
from datetime import date, timedelta

from app import models
from tests.conftest import DEFINICION_DESEMBOLSO, gateway, transaccion

INTERNA = "/internal/contabilidad/transacciones"
API = "/api/contabilidad"


def _mandar(client, interna, **kw):
    return client.post(INTERNA, headers=interna, json=transaccion(**kw))


def _definir(client, contador, **cambios):
    return client.post(f"{API}/definiciones", headers=contador, json={**DEFINICION_DESEMBOLSO, **cambios})


# ── Sin definición: la transacción espera ────────────────────────────────────────────────────────

def test_la_api_interna_exige_la_clave(client):
    assert client.post(INTERNA, json=transaccion()).status_code == 401


def test_sin_definicion_la_transaccion_queda_pendiente_de_configuracion(client, interna, db):
    r = _mandar(client, interna)
    assert r.status_code == 201
    assert r.json()["estado"] == "PENDIENTE_CONFIGURACION" and r.json()["asientoId"] is None
    assert "Falta definir" in r.json()["motivo"]
    assert db.query(models.Asiento).count() == 0          # no se inventa ningún asiento


def test_el_alta_de_transacciones_es_idempotente(client, interna, db):
    _mandar(client, interna)
    r = _mandar(client, interna)
    assert r.json()["ya_existia"] is True
    assert db.query(models.Transaccion).count() == 1


def test_los_pendientes_se_agrupan_con_sus_campos_para_definirlos(client, interna, contador):
    _mandar(client, interna, referencia="CTO-1")
    _mandar(client, interna, referencia="CTO-2")
    _mandar(client, interna, tipo="COBRANZA", referencia="REC-1", datos={"capital": 5000, "interes": 900})
    d = client.get(f"{API}/transacciones/sin-definir", headers=contador).json()
    assert [(i["modulo"], i["tipo"], i["cantidad"]) for i in d["items"]] == [
        ("creditos", "DESEMBOLSO", 2), ("creditos", "COBRANZA", 1)]
    assert d["items"][0]["campos"] == ["capital", "gastos", "iva"]    # qué se puede usar en la definición


# ── Con definición: sale el asiento ──────────────────────────────────────────────────────────────

def test_al_definir_la_regla_se_contabiliza_lo_que_estaba_esperando(client, interna, contador, db):
    _mandar(client, interna, referencia="CTO-1")
    _mandar(client, interna, referencia="CTO-2")

    r = _definir(client, contador)

    assert r.status_code == 201 and r.json()["reproceso"] == {"contabilizadas": 2, "pendientes": 0, "errores": 0}
    ts = db.query(models.Transaccion).all()
    assert {t.estado for t in ts} == {"CONTABILIZADA"} and all(t.asiento_id for t in ts)
    a = db.query(models.Asiento).order_by(models.Asiento.numero).first()
    assert a.numero == 1 and a.diario_codigo == "BANCO" and a.concepto == "Desembolso CTO-1"
    assert [(l.cuenta_codigo, float(l.debe), float(l.haber)) for l in a.lineas] == [
        ("1.1.04", 102000.0, 0.0), ("1.1.02", 0.0, 100000.0), ("4.1.03", 0.0, 2000.0)]


def test_una_transaccion_nueva_se_contabiliza_al_llegar(client, interna, contador):
    _definir(client, contador)
    r = _mandar(client, interna, referencia="CTO-9")
    assert r.json()["estado"] == "CONTABILIZADA" and r.json()["asientoId"]


def test_el_asiento_conserva_la_trazabilidad_en_los_dos_sentidos(client, interna, contador):
    _definir(client, contador)
    tid = _mandar(client, interna, referencia="CTO-7").json()["id"]
    t = client.get(f"{API}/transacciones/{tid}", headers=contador).json()
    assert t["asiento"]["numero"] and t["asiento"]["origen"] == "TRANSACCION"
    a = client.get(f"{API}/asientos/{t['asiento']['id']}", headers=contador).json()
    assert a["transaccion"]["referencia"] == "CTO-7" and a["transaccion"]["modulo"] == "creditos"
    assert a["transaccion"]["datos"]["capital"] == 100000


def test_las_lineas_en_cero_no_ensucian_el_asiento(client, interna, contador, db):
    _definir(client, contador)
    _mandar(client, interna, referencia="CTO-3", datos={"capital": 50000, "gastos": 0, "iva": 0})
    a = db.query(models.Asiento).order_by(models.Asiento.id.desc()).first()
    assert [l.cuenta_codigo for l in a.lineas] == ["1.1.04", "1.1.02"]


def test_la_numeracion_es_correlativa_por_ejercicio(client, interna, contador, db):
    _definir(client, contador)
    for i in range(3):
        _mandar(client, interna, referencia=f"CTO-{i}")
    assert [a.numero for a in db.query(models.Asiento).order_by(models.Asiento.numero).all()] == [1, 2, 3]


# ── Definiciones: validación y prueba ────────────────────────────────────────────────────────────

def test_una_definicion_sin_debe_y_haber_no_se_guarda(client, contador):
    r = _definir(client, contador, lineas=[{"cuenta": "1.1.04", "dc": "DEBE", "importe": "capital"},
                                           {"cuenta": "1.1.02", "dc": "DEBE", "importe": "capital"}])
    assert r.status_code == 422 and "DEBE" in r.json()["detail"]


def test_una_definicion_con_cuenta_de_agrupacion_no_se_guarda(client, contador):
    r = _definir(client, contador, lineas=[{"cuenta": "1", "dc": "DEBE", "importe": "capital"},
                                           {"cuenta": "1.1.02", "dc": "HABER", "importe": "capital"}])
    assert r.status_code == 422 and "agrupación" in r.json()["detail"]


def test_la_expresion_del_importe_no_ejecuta_codigo(client, contador):
    r = _definir(client, contador, lineas=[
        {"cuenta": "1.1.04", "dc": "DEBE", "importe": "__import__('os').system('ls')"},
        {"cuenta": "1.1.02", "dc": "HABER", "importe": "capital"}])
    assert r.status_code == 422


def test_la_definicion_se_prueba_antes_de_usarla(client, contador):
    d = _definir(client, contador).json()
    r = client.post(f"{API}/definiciones/{d['id']}/probar", headers=contador,
                    json={"datos": {"capital": 1000, "gastos": 100}}).json()
    assert r["debe"] == r["haber"] == 1100.0
    assert [l["cuenta"] for l in r["lineas"]] == ["1.1.04", "1.1.02", "4.1.03"]


def test_si_la_definicion_no_balancea_la_transaccion_queda_en_error(client, interna, contador, db):
    _definir(client, contador, lineas=[{"cuenta": "1.1.04", "dc": "DEBE", "importe": "capital"},
                                       {"cuenta": "1.1.02", "dc": "HABER", "importe": "capital + gastos"}])
    r = _mandar(client, interna)
    assert r.json()["estado"] == "ERROR" and "no balancea" in r.json()["motivo"]
    assert db.query(models.Asiento).count() == 0


def test_la_definicion_corregida_reprocesa_lo_que_habia_quedado_en_error(client, interna, contador):
    d = _definir(client, contador, lineas=[{"cuenta": "1.1.04", "dc": "DEBE", "importe": "capital"},
                                           {"cuenta": "1.1.02", "dc": "HABER", "importe": "capital + gastos"}])
    _mandar(client, interna)
    r = client.put(f"{API}/definiciones/{d.json()['id']}", headers=contador, json=DEFINICION_DESEMBOLSO)
    assert r.json()["reproceso"]["contabilizadas"] == 1


def test_la_definicion_respeta_su_vigencia(client, interna, contador, db):
    manana = (date.today() + timedelta(days=1)).isoformat()
    _definir(client, contador, vigente_desde=manana)
    assert _mandar(client, interna).json()["estado"] == "PENDIENTE_CONFIGURACION"


# ── Permisos ─────────────────────────────────────────────────────────────────────────────────────

def test_sin_permiso_no_se_configura_ni_se_registra(client, solo_lectura):
    assert client.post(f"{API}/definiciones", headers=solo_lectura, json=DEFINICION_DESEMBOLSO).status_code == 403
    assert client.post(f"{API}/asientos", headers=solo_lectura, json={
        "fecha": date.today().isoformat(), "concepto": "x",
        "lineas": [{"cuenta": "1.1.01", "debe": 10}, {"cuenta": "1.1.02", "haber": 10}]}).status_code == 403
    assert client.get(f"{API}/asientos", headers=solo_lectura).status_code == 200
    assert client.get(f"{API}/asientos", headers=gateway("x")).status_code == 403
