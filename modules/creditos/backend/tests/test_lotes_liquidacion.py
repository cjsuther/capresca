"""Lotes: solicitudes aprobadas y liquidables, por tipo de crédito y fecha, numerados por año, con
tope configurable; alguien los verifica y los cierra, Despacho les asigna la resolución y recién ahí
se liquidan completos."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import models, models_productos as m
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import lotes_liquidacion as lotes

CLAVE = "clave-despacho-test"
ANIO = date.today().year


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "despacho_internal_api_key", CLAVE)
    from app.main import app
    with TestClient(app) as c:
        yield c


HD = {"X-Api-Key": CLAVE}


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _producto(codigo="LP-PERS-01"):
    with SessionLocal() as db:
        return db.query(m.PPProducto).filter_by(codigo=codigo).one().id


_n = {"i": 0}


def _aprobada(producto_id, monto=300_000, cliente_id=1, cbu="", aprobada_en=None, estado="APROBADA"):
    """Una solicitud aprobada (como la deja el circuito de evaluación) y su ubicación en el lote."""
    _n["i"] += 1
    with SessionLocal() as db:
        s = m.PPSolicitud(numero=f"SOL-T-{_n['i']:04d}", estado=estado, producto_id=producto_id,
                          solicitante_tipo="REGISTRADO", cliente_id=cliente_id,
                          monto_solicitado=Decimal(monto), plazo_solicitado=12,
                          datos_adicionales={"cbu": cbu} if cbu else {},
                          aprobada_en=aprobada_en or date.today())
        db.add(s); db.flush()
        if estado == "APROBADA":
            lotes.asignar(db, s)
        db.commit()
        return s.id


def _sin_cbu_cliente():
    with SessionLocal() as db:
        db.add(models.Cliente(id=90, id_cliente="C90", cuil="20999999990", dni="99999999",
                              apellido_nombre="SIN CBU, ANA", cbu=""))
        db.commit()
    return 90


def _sol(sid):
    with SessionLocal() as db:
        return db.get(m.PPSolicitud, sid)


def _lote(lote_id):
    with SessionLocal() as db:
        return db.get(m.PPLoteLiquidacion, lote_id)


def _listar(client, h):
    return client.get("/api/creditos/contratos/lotes-liquidacion", headers=h).json()


def _res(id=7, numero=45, importe=10_000_000, oficial=None):
    return {"id": id, "numero": numero, "anio": ANIO, "numero_oficial": oficial,
            "fecha": date.today().isoformat(), "importe": importe}


def _cerrar(lote_id):
    with SessionLocal() as db:
        if db.get(m.PPLoteLiquidacion, lote_id).estado == lotes.ABIERTO:
            lotes.cerrar(db, lote_id, "verificador")


def _asignar(client, lote_ids, cerrar=True, **kw):
    if cerrar:
        for lid in lote_ids:
            _cerrar(lid)
    return client.post("/internal/creditos/lotes/asignar-resolucion", headers=HD,
                       json={"lote_ids": lote_ids, "resolucion": _res(**kw)})


def _tope(n):
    with SessionLocal() as db:
        db.query(models.Parametro).filter_by(clave=lotes.PARAMETRO).one().valor = str(n)
        db.commit()


# ---------------------------------------------------------------------------------- armado
def test_al_aprobarse_entra_al_lote_de_su_tipo_y_fecha(client):
    hcred, hadmin = _auth(client, "creditos", "cred123"), _auth(client)
    pid = _producto()
    sol = client.post("/api/creditos/solicitudes", headers=hcred, json={
        "producto_id": pid, "monto_solicitado": 300_000, "plazo_solicitado": 12,
        "solicitante_tipo": "REGISTRADO", "cliente_id": 1}).json()
    client.post(f"/api/creditos/solicitudes/{sol['id']}/estado", headers=hcred, json={"accion": "enviar"})
    ap = client.post(f"/api/creditos/solicitudes/{sol['id']}/estado", headers=hadmin, json={"accion": "aprobar"}).json()
    assert ap["estado"] == "APROBADA"
    assert ap["lote"]["codigo"] == f"{ANIO}-0001" and ap["lote"]["estado"] == "ABIERTO"
    assert ap["lote"]["resolucion"] is None
    with SessionLocal() as db:
        s = db.get(m.PPSolicitud, sol["id"])
        assert s.aprobada_en == date.today() and s.lote_liquidacion_id == ap["lote"]["id"]


def test_tipos_y_fechas_distintos_van_a_lotes_distintos(client):
    pers, jub = _producto(), _producto("LP-JUB-01")
    a1, a2 = _aprobada(pers), _aprobada(pers)
    b = _aprobada(jub)
    c = _aprobada(pers, aprobada_en=date(ANIO, 1, 2))
    l1, l2, lb, lc = (_sol(x).lote_liquidacion_id for x in (a1, a2, b, c))
    assert l1 == l2 and len({l1, lb, lc}) == 3
    assert [_lote(x).codigo for x in (l1, lb, lc)] == [f"{ANIO}-0001", f"{ANIO}-0002", f"{ANIO}-0003"]


def test_lo_que_no_es_liquidable_queda_fuera_de_lote_hasta_completarse(client):
    h = _auth(client)
    pid = _producto()
    sid = _aprobada(pid, cliente_id=_sin_cbu_cliente())
    assert _sol(sid).lote_liquidacion_id is None
    fuera = _listar(client, h)["fueraDeLote"]
    assert fuera[0]["id"] == sid and fuera[0]["faltantes"] == ["CBU de acreditación (22 dígitos)"]
    det = client.get(f"/api/creditos/solicitudes/{sid}", headers=h).json()
    assert det["lote"] is None and det["faltaParaLote"] == ["CBU de acreditación (22 dígitos)"]

    with SessionLocal() as db:            # se completa el CBU (p. ej. en el padrón)
        db.get(models.Cliente, 90).cbu = "0110466420046600526713"
        db.commit()
    d = _listar(client, h)
    assert d["fueraDeLote"] == [] and _sol(sid).lote_liquidacion_id is not None


def test_lleno_el_lote_se_abre_el_siguiente(client):
    _tope(2)
    pid = _producto()
    ids = [_aprobada(pid) for _ in range(5)]
    codigos = [_lote(_sol(i).lote_liquidacion_id).codigo for i in ids]
    assert codigos == [f"{ANIO}-0001"] * 2 + [f"{ANIO}-0002"] * 2 + [f"{ANIO}-0003"]


def _tope_monto(producto_id, monto):
    with SessionLocal() as db:
        db.get(m.PPProducto, producto_id).lote_monto_max = monto
        db.commit()


def test_el_tope_de_monto_del_tipo_de_credito_abre_otro_lote(client):
    pid, jub = _producto(), _producto("LP-JUB-01")
    _tope_monto(pid, 500_000)
    a = _sol(_aprobada(pid, 300_000)).lote_liquidacion_id
    b = _sol(_aprobada(pid, 200_000)).lote_liquidacion_id          # 500: justo el tope, entra
    c = _sol(_aprobada(pid, 100_000)).lote_liquidacion_id          # 600: no entra
    assert a == b and c != a
    assert lotes.importe(SessionLocal(), a) == 500_000
    otro = _sol(_aprobada(jub, 900_000)).lote_liquidacion_id       # el otro tipo no tiene tope de monto
    assert _sol(_aprobada(jub, 900_000)).lote_liquidacion_id == otro


def test_lo_que_pase_primero_cantidad_o_monto(client):
    _tope(2)
    pid = _producto()
    _tope_monto(pid, 10_000_000)
    a, b, c = (_sol(_aprobada(pid, 100_000)).lote_liquidacion_id for _ in range(3))
    assert a == b != c                                                # pasó primero la cantidad


def test_una_sola_solicitud_mayor_al_tope_va_sola_a_su_lote(client):
    pid = _producto()
    _tope_monto(pid, 100_000)
    a = _sol(_aprobada(pid, 300_000)).lote_liquidacion_id
    b = _sol(_aprobada(pid, 50_000)).lote_liquidacion_id
    assert a != b


def test_no_se_mueve_a_un_lote_que_pasaria_el_tope_de_monto(client):
    h = _auth(client)
    pid = _producto()
    _tope_monto(pid, 400_000)
    a = _aprobada(pid, 300_000)
    b = _aprobada(pid, 300_000)
    la, lb = _sol(a).lote_liquidacion_id, _sol(b).lote_liquidacion_id
    assert la != lb
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": b, "destino_id": la})
    assert r.status_code == 409 and "tope de monto" in r.json()["detail"]


def test_los_topes_de_monto_se_configuran_por_tipo_de_credito(client):
    h = _auth(client)
    pid = _producto()
    r = client.put("/api/creditos/contratos/lotes-liquidacion/topes", headers=h,
                   json=[{"producto_id": pid, "tope_monto": 2_500_000}])
    assert r.status_code == 200, r.text
    fila = next(x for x in r.json()["items"] if x["productoId"] == pid)
    assert fila["topeMonto"] == 2_500_000 and r.json()["maximo"] == 50
    r = client.put("/api/creditos/contratos/lotes-liquidacion/topes", headers=h,
                   json=[{"producto_id": pid, "tope_monto": None}])
    assert next(x for x in r.json()["items"] if x["productoId"] == pid)["topeMonto"] is None
    assert client.put("/api/creditos/contratos/lotes-liquidacion/topes", headers=h,
                      json=[{"producto_id": pid, "tope_monto": -1}]).status_code == 422


def test_el_numero_arranca_en_uno_cada_anio(client):
    pid = _producto()
    with SessionLocal() as db:
        db.add(m.PPLoteLiquidacion(anio=ANIO - 1, numero=37, producto_id=pid, fecha=date(ANIO - 1, 12, 30)))
        db.commit()
    assert _lote(_sol(_aprobada(pid)).lote_liquidacion_id).codigo == f"{ANIO}-0001"


def test_un_lote_cerrado_no_recibe_mas_solicitudes(client):
    pid = _producto()
    lid = _sol(_aprobada(pid)).lote_liquidacion_id
    _cerrar(lid)
    otra = _sol(_aprobada(pid)).lote_liquidacion_id
    assert otra != lid and _lote(otra).estado == "ABIERTO"


# ---------------------------------------------------------------------------------- cierre
def test_quien_verifica_cierra_el_lote_y_queda_registrado(client):
    h = _auth(client)
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/cerrar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "CERRADO" and r.json()["cerradoPor"] == "admin" and r.json()["cerradoEn"]
    lt = _lote(lid)
    assert lt.estado == "CERRADO" and lt.cerrado_por == "admin" and lt.cerrado_en is not None
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/cerrar", headers=h)
    assert r.status_code == 409 and "ya está cerrado" in r.json()["detail"]


def test_no_se_cierra_un_lote_con_algo_que_no_se_puede_liquidar(client):
    h = _auth(client)
    sid = _aprobada(_producto())
    lid = _sol(sid).lote_liquidacion_id
    with SessionLocal() as db:
        db.get(models.Cliente, 1).cbu = "123"          # le cambiaron el CBU después de entrar al lote
        db.commit()
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/cerrar", headers=h)
    assert r.status_code == 409 and "no se pueden liquidar" in r.json()["detail"]
    assert _lote(lid).estado == "ABIERTO"


def test_un_lote_cerrado_se_reabre_mientras_no_tenga_resolucion(client):
    h = _auth(client)
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    _cerrar(lid)
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/reabrir", headers=h)
    assert r.status_code == 200 and _lote(lid).estado == "ABIERTO" and _lote(lid).cerrado_por is None
    _asignar(client, [lid])
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/reabrir", headers=h)
    assert r.status_code == 409 and "ya tiene resolución" in r.json()["detail"]


def test_sin_permiso_de_escritura_no_se_cierra(client, monkeypatch):
    from app.api import solicitudes
    from fastapi import HTTPException

    def _no(db, user):
        raise HTTPException(403, "Sin permiso")
    monkeypatch.setattr(solicitudes, "_req_edita", _no)
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    r = client.post(f"/api/creditos/contratos/lotes-liquidacion/{lid}/cerrar", headers=_auth(client))
    assert r.status_code == 403 and _lote(lid).estado == "ABIERTO"


# ---------------------------------------------------------------------------------- resolución
def test_despacho_sólo_asigna_resolucion_a_lotes_cerrados(client):
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    r = _asignar(client, [lid], cerrar=False)
    assert r.status_code == 409 and "todavía no se cerraron" in r.json()["detail"]
    assert _lote(lid).estado == "ABIERTO"


def test_despacho_asigna_una_resolucion_a_varios_lotes(client):
    h = _auth(client)
    pers, jub = _producto(), _producto("LP-JUB-01")
    a, b = _aprobada(pers, 300_000), _aprobada(jub, 200_000)
    la, lb = _sol(a).lote_liquidacion_id, _sol(b).lote_liquidacion_id
    r = _asignar(client, [la, lb], importe=500_000, oficial=120)
    assert r.status_code == 200, r.text
    assert float(r.json()["totalResolucion"]) == 500_000
    assert _lote(la).estado == _lote(lb).estado == "CON_RESOLUCION"
    det = client.get(f"/api/creditos/solicitudes/{a}", headers=h).json()
    assert det["lote"]["estado"] == "CON_RESOLUCION"
    assert det["lote"]["resolucion"]["numeroOficial"] == 120 and det["resolucion"]["numero"] == 45


def test_la_suma_de_los_lotes_no_supera_el_importe_de_la_resolucion(client):
    pid, jub = _producto(), _producto("LP-JUB-01")
    la = _sol(_aprobada(pid, 300_000)).lote_liquidacion_id
    lb = _sol(_aprobada(jub, 300_000)).lote_liquidacion_id
    assert _asignar(client, [la], importe=500_000).status_code == 200
    r = _asignar(client, [lb], importe=500_000)            # 300 + 300 > 500
    assert r.status_code == 409 and "supera el importe" in r.json()["detail"]
    assert _lote(lb).estado == "CERRADO"


def test_un_lote_no_recibe_dos_resoluciones(client):
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    assert _asignar(client, [lid]).status_code == 200
    r = _asignar(client, [lid], id=8, numero=46)
    assert r.status_code == 409 and "ya tienen resolución" in r.json()["detail"]


def test_bajar_el_importe_de_la_resolucion_se_controla(client):
    lid = _sol(_aprobada(_producto(), 300_000)).lote_liquidacion_id
    _asignar(client, [lid], importe=500_000)
    r = client.post("/internal/creditos/lotes/resolucion", headers=HD, json=_res(importe=200_000))
    assert r.status_code == 409
    r = client.post("/internal/creditos/lotes/resolucion", headers=HD, json=_res(importe=400_000, oficial=777))
    assert r.status_code == 200 and r.json()["lotes"] == 1
    assert _lote(lid).resolucion_numero_oficial == 777 and float(_lote(lid).resolucion_importe) == 400_000


def test_quitar_la_resolucion_deja_el_lote_cerrado(client):
    sid = _aprobada(_producto())
    lid = _sol(sid).lote_liquidacion_id
    _asignar(client, [lid])
    r = client.post(f"/internal/creditos/lotes/{lid}/quitar-resolucion", headers=HD)
    assert r.status_code == 200 and r.json()["estado"] == "CERRADO" and _lote(lid).estado == "CERRADO"
    assert _lote(lid).cerrado_por == "verificador"
    assert _sol(sid).en_resolucion is False and _lote(lid).resolucion_id is None


def test_las_solicitudes_de_un_lote_con_resolucion_no_se_anulan(client):
    h = _auth(client)
    sid = _aprobada(_producto())
    _asignar(client, [_sol(sid).lote_liquidacion_id])
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=h, json={"accion": "anular", "motivo": "x"})
    assert r.status_code == 409 and "con resolución" in r.json()["detail"]
    assert _sol(sid).estado == "APROBADA"


def test_las_solicitudes_de_un_lote_cerrado_no_se_anulan(client):
    h = _auth(client)
    sid = _aprobada(_producto())
    _cerrar(_sol(sid).lote_liquidacion_id)
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=h, json={"accion": "anular", "motivo": "x"})
    assert r.status_code == 409 and "cerrado" in r.json()["detail"]


def test_anular_una_de_un_lote_abierto_la_saca_del_lote(client):
    h = _auth(client)
    sid = _aprobada(_producto())
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=h, json={"accion": "anular", "motivo": "x"})
    assert r.status_code == 200 and _sol(sid).lote_liquidacion_id is None


def test_sin_la_clave_interna_no_se_entra(client):
    assert client.get("/internal/creditos/lotes").status_code == 401
    assert client.get("/internal/creditos/lotes", headers={"X-Api-Key": "otra"}).status_code == 401


def test_despacho_lista_los_lotes_y_las_solicitudes_de_una_resolucion(client):
    pid = _producto()
    a, b = _aprobada(pid, 100_000), _aprobada(pid, 200_000)
    lid = _sol(a).lote_liquidacion_id
    _asignar(client, [lid])
    d = client.get("/internal/creditos/lotes", headers=HD, params={"estado": "CON_RESOLUCION"}).json()
    assert [x["id"] for x in d["items"]] == [lid] and d["items"][0]["montoTotal"] == 300_000
    anexo = client.get("/internal/creditos/lotes/resolucion/solicitudes", headers=HD,
                       params={"resolucion_id": 7}).json()
    assert {f["id"] for f in anexo["items"]} == {a, b} and float(anexo["total"]) == 300_000
    assert anexo["items"][0]["cuil"] == "20123456786"


def test_despacho_ve_el_detalle_del_lote_con_cada_solicitante(client):
    pid = _producto()
    a, b = _aprobada(pid, 100_000), _aprobada(pid, 200_000)
    lid = _sol(a).lote_liquidacion_id
    d = client.get(f"/internal/creditos/lotes/{lid}", headers=HD).json()
    assert d["codigo"] and d["cantidad"] == 2 and d["montoTotal"] == 300_000
    filas = {f["solicitudId"]: f for f in d["contratos"]}
    assert set(filas) == {a, b}
    assert filas[a]["monto"] == 100_000 and filas[a]["cuil"] == "20123456786" and filas[a]["dni"]
    assert filas[a]["cliente"] and filas[a]["estadoSolicitud"] == "APROBADA"
    assert client.get("/internal/creditos/lotes/999999", headers=HD).status_code == 404


# ---------------------------------------------------------------------------------- mover
def test_mover_a_un_lote_del_mismo_tipo_y_fecha_o_a_uno_nuevo(client):
    h = _auth(client)
    _tope(2)
    pid = _producto()
    a, b, c = _aprobada(pid), _aprobada(pid), _aprobada(pid)
    l1, l2 = _sol(a).lote_liquidacion_id, _sol(c).lote_liquidacion_id
    _asignar(client, [l1])
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": a, "destino_id": l2})
    assert r.status_code == 200, r.text
    assert _sol(a).lote_liquidacion_id == l2 and _sol(a).en_resolucion is False
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": b, "nuevo": True})
    assert r.status_code == 200 and r.json()["codigo"] == f"{ANIO}-0003"
    assert _lote(r.json()["id"]).fecha == _lote(l1).fecha


def test_no_se_mueve_a_otro_tipo_ni_a_un_lote_completo(client):
    h = _auth(client)
    _tope(1)
    pid, jub = _producto(), _producto("LP-JUB-01")
    a, b, c = _aprobada(pid), _aprobada(pid), _aprobada(jub)
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": a, "destino_id": _sol(c).lote_liquidacion_id})
    assert r.status_code == 409 and "mismo tipo" in r.json()["detail"]
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": a, "destino_id": _sol(b).lote_liquidacion_id})
    assert r.status_code == 409 and "completo" in r.json()["detail"]


def test_al_verificar_se_mueve_entre_lotes_abiertos(client):
    h = _auth(client)
    _tope(1)
    pid = _producto()
    a, b = _aprobada(pid), _aprobada(pid)
    la, lb = _sol(a).lote_liquidacion_id, _sol(b).lote_liquidacion_id
    _tope(5)
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": b, "destino_id": la})
    assert r.status_code == 200 and _sol(b).lote_liquidacion_id == la


def test_no_se_mueve_a_un_lote_cerrado_ni_con_resolucion(client):
    h = _auth(client)
    _tope(1)
    pid = _producto()
    a, b, c = _aprobada(pid), _aprobada(pid), _aprobada(pid)
    la, lb, lc = (_sol(x).lote_liquidacion_id for x in (a, b, c))
    _tope(5)
    _cerrar(la)
    _asignar(client, [lb])
    for destino in (la, lb):
        r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                        json={"solicitud_id": c, "destino_id": destino})
        assert r.status_code == 409 and "sólo se mueve a un lote abierto" in r.json()["detail"]
    assert _sol(c).lote_liquidacion_id == lc


# ---------------------------------------------------------------------------------- liquidación
def test_sin_resolucion_el_lote_no_se_liquida(client):
    h = _auth(client)
    lid = _sol(_aprobada(_producto())).lote_liquidacion_id
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lid})
    assert r.status_code == 409 and "no tiene resolución" in r.json()["detail"]


def test_liquidar_origina_y_desembolsa_el_lote_completo(client):
    h = _auth(client)
    pid = _producto()
    a, b = _aprobada(pid), _aprobada(pid)
    lid = _sol(a).lote_liquidacion_id
    _asignar(client, [lid])
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lid})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["errores"] == [] and len(d["desembolsados"]) == 2 and d["estado"] == "LIQUIDADO"
    with SessionLocal() as db:
        for sid in (a, b):
            s = db.get(m.PPSolicitud, sid)
            c = db.get(m.PPContrato, s.contrato_id)
            assert s.estado == "ORIGINADA" and c.estado == "ACTIVO" and c.lote_liquidacion_id == lid
        assert db.get(m.PPLoteLiquidacion, lid).liquidado_en is not None
    assert all(x["id"] != lid for x in _listar(client, h)["items"])        # ya no está pendiente


def test_si_algo_no_es_liquidable_no_se_liquida_nada(client):
    h = _auth(client)
    pid = _producto()
    a, b = _aprobada(pid), _aprobada(pid)
    lid = _sol(a).lote_liquidacion_id
    _asignar(client, [lid])
    with SessionLocal() as db:            # el cliente de b perdió el CBU después de entrar al lote
        s = db.get(m.PPSolicitud, b)
        s.cliente_id = _sin_cbu_cliente()
        db.commit()
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lid})
    assert r.status_code == 409 and "no se puede liquidar completo" in r.json()["detail"]
    assert _sol(a).estado == "APROBADA" and _sol(a).contrato_id is None


def test_originar_suelta_sin_lote_con_resolucion_no_se_puede(client):
    h = _auth(client)
    pid = _producto()
    sid = _aprobada(pid)
    r = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pid, "cliente_nombre": "X", "monto": 300_000, "plazo": 12,
        "solicitud_pp_id": sid, "desembolsar": False})
    assert r.status_code == 409 and "liquidar su lote" in r.json()["detail"]


# ---------------------------------------------------------------------------------- migración
def test_los_lotes_de_contratos_pasan_a_solicitudes_y_se_parten_por_resolucion(client):
    pid = _producto()
    with SessionLocal() as db:
        lote = m.PPLoteLiquidacion(anio=ANIO, numero=1, producto_id=pid, fecha=date(ANIO, 9, 24))
        db.add(lote); db.flush()
        for i, res in enumerate((4, 4, 0)):
            c = m.PPContrato(producto_id=pid, producto_version_numero=1, numero_contrato=f"CTO-M-{i}",
                             cliente_nombre="M", sistema="FRANCES", monto_original=Decimal(100), saldo_capital=Decimal(100),
                             plazo=12, tasa_contratada=Decimal(50), fecha_valor=lote.fecha,
                             fecha_vencimiento=lote.fecha, estado="A_LIQUIDAR", lote_liquidacion_id=lote.id)
            db.add(c); db.flush()
            db.add(m.PPSolicitud(numero=f"SOL-M-{i}", estado="ORIGINADA", producto_id=pid, contrato_id=c.id,
                                 numero_resolucion=res, en_resolucion=bool(res),
                                 fecha_resolucion=date(ANIO, 9, 25) if res else None))
        db.commit()
        lid = lote.id
        assert lotes.migrar_a_solicitudes(db) > 0
        assert lotes.migrar_a_solicitudes(db) == 0                       # idempotente
        lt = db.get(m.PPLoteLiquidacion, lid)
        assert lt.estado == "CON_RESOLUCION" and lt.resolucion_numero == 4 and lt.resolucion_id is None
        assert db.query(m.PPSolicitud).filter_by(lote_liquidacion_id=lid).count() == 2
        sin = db.query(m.PPSolicitud).filter_by(numero="SOL-M-2").one()
        otro = db.get(m.PPLoteLiquidacion, sin.lote_liquidacion_id)
        assert otro.id != lid and otro.estado == "ABIERTO" and otro.fecha == lt.fecha
        assert db.get(m.PPContrato, sin.contrato_id).lote_liquidacion_id == otro.id

    # Despacho vincula el lote migrado (sin id) por número y año al actualizar la resolución.
    r = client.post("/internal/creditos/lotes/resolucion", headers=HD,
                    json={"id": 31, "numero": 4, "anio": ANIO, "numero_oficial": 9, "importe": 1000})
    assert r.json()["lotes"] == 1 and _lote(lid).resolucion_id == 31


def test_el_tope_se_siembra_en_los_parametros_de_creditos(client):
    with SessionLocal() as db:
        p = db.query(models.Parametro).filter_by(clave="LOTE_LIQUIDACION_MAX").one()
        assert (p.valor, p.ambito) == ("50", "creditos")
