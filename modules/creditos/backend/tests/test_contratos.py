"""Configurar Créditos — originación (Fase 5) y servicing (Fase 6)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pers(client, h):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    return next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")


def test_oferta_solo_publicados(client):
    h = _auth(client)
    codigos = {p["codigo"] for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"]}
    assert "LP-PERS-01" in codigos and "LP-JUB-01" in codigos
    assert "LP-ADEL-01" not in codigos  # EN_REVISION
    assert "LP-VIV-01" not in codigos   # RETIRADO


def test_originar_congela_snapshot_y_cronograma(client):
    h = _auth(client)
    p = _pers(client, h)
    r = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "PEREZ", "monto": 1200000, "plazo": 24})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["estado"] == "ACTIVO"
    assert len(c["cuotas"]) == 24
    assert c["saldo_capital"] == 1200000
    assert c["snapshot"]["codigo"] == "LP-PERS-01" and c["snapshot"]["version"] == p["version"]
    # Σ capital == monto (dentro de la tolerancia de redondeo del modelo)
    assert abs(sum(q["capital"] for q in c["cuotas"]) - 1200000) < 0.5
    # la última cuota salda exacto: saldo final 0
    assert c["cuotas"][-1]["saldo_final"] == 0
    assert c["actividades"][0]["tipo"] == "DISBURSEMENT"


def test_cargo_desembolso_no_se_cobra_doble(client):
    """H-085: el cargo al desembolso va en la 1ª cuota; no se resta además del neto acreditado."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "DOBLE", "monto": 1_000_000, "plazo": 12}).json()
    liq = c["liquidacion"]
    # El cliente recibe el monto completo (no se deduce el cargo del neto).
    assert liq["neto"] == liq["monto"] == 1_000_000
    # Y ese cargo ya está cobrado dentro del cronograma (1ª cuota con cargo > resto).
    cuotas = c["cuotas"]
    if float(cuotas[0]["cargos"]) > 0:
        assert float(cuotas[0]["cargos"]) >= float(cuotas[1]["cargos"])  # el cargo desembolso pesa en la 1ª
    # invariante: Σcapital = monto (el cargo no infló el capital salvo que sea financiable)
    assert abs(sum(q["capital"] for q in cuotas) - 1_000_000) < 0.5


def test_originar_valida_rango_y_publicado(client):
    h = _auth(client)
    p = _pers(client, h)
    # monto fuera de rango
    bad = client.post("/api/creditos/contratos/originar", headers=h,
                      json={"producto_id": p["id"], "cliente_nombre": "X", "monto": 99, "plazo": 24})
    assert bad.status_code == 422
    # producto no publicado (ADEL en revisión)
    cat = client.get("/api/creditos/productos", headers=h).json()["items"]
    adel = next(x for x in cat if x["codigo"] == "LP-ADEL-01")
    r = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": adel["id"], "cliente_nombre": "X", "monto": 500000, "plazo": 12})
    assert r.status_code == 409


def _publicar_negociable(client):
    """Crea (créditos), configura banda negociable 40–60, aprueba y publica (admin)."""
    hc = {"Authorization": f"Bearer {client.post('/api/creditos/auth/login', data={'username': 'creditos', 'password': 'cred123'}).json()['access_token']}"}
    ha = _auth(client)
    p = client.post("/api/creditos/productos", headers=hc, json={"nombre": "Negociable"}).json()
    pid = p["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hc, json={**p["cfg"], "tna": 50, "tnaNegociable": True, "tnaMin": 40, "tnaMax": 60})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hc, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=ha, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=ha, json={"accion": "publicar"})
    return ha, pid


def test_banda_negociacion_persiste(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Band"}).json()
    r = client.put(f"/api/creditos/productos/{p['id']}/config", headers=h, json={**p["cfg"], "tnaNegociable": True, "tnaMin": 30, "tnaMax": 70})
    assert r.json()["cfg"]["tnaNegociable"] is True and r.json()["cfg"]["tnaMin"] == 30 and r.json()["cfg"]["tnaMax"] == 70


def test_originar_tasa_dentro_y_fuera_de_banda(client):
    h, pid = _publicar_negociable(client)
    # dentro de la banda -> usa la tasa negociada
    ok = client.post("/api/creditos/contratos/originar", headers=h, json={"producto_id": pid, "cliente_nombre": "X", "monto": 1000000, "plazo": 24, "tasa": 55})
    assert ok.status_code == 201 and ok.json()["tasa"] == 55
    # fuera de la banda -> 422
    bad = client.post("/api/creditos/contratos/originar", headers=h, json={"producto_id": pid, "cliente_nombre": "X", "monto": 1000000, "plazo": 24, "tasa": 70})
    assert bad.status_code == 422
    # sin tasa -> usa la del producto (50)
    d = client.post("/api/creditos/contratos/originar", headers=h, json={"producto_id": pid, "cliente_nombre": "X", "monto": 1000000, "plazo": 24}).json()
    assert d["tasa"] == 50


def test_originar_tasa_en_linea_no_negociable(client):
    h = _auth(client)
    pers = next(x for x in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if x["codigo"] == "LP-PERS-01")
    r = client.post("/api/creditos/contratos/originar", headers=h, json={"producto_id": pers["id"], "cliente_nombre": "X", "monto": 1000000, "plazo": 24, "tasa": 30})
    assert r.status_code == 422  # la línea no permite negociar la tasa


def test_servicing_pago_y_payoff(client):
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "PEREZ", "monto": 1200000, "plazo": 24}).json()
    cid = c["id"]
    # pago de una cuota
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    assert r["cuotas"][0]["estado"] == "PAGADA"
    assert r["saldo_capital"] < 1200000
    # cancelación total
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYOFF"}).json()
    assert r["estado"] == "CERRADO" and r["saldo_capital"] == 0
    assert all(q["estado"] == "PAGADA" for q in r["cuotas"])
    # un contrato cerrado no admite más actividades
    assert client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).status_code == 409


def _jub(client, h):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    return next(p for p in of["items"] if p["codigo"] == "LP-JUB-01")


def test_disponibilidad_catalogo_y_filtro_oferta(client):
    """Fase E: la oferta se anota con elegibilidad y filtra por segmento del solicitante."""
    h = _auth(client)
    cat = client.get("/api/creditos/contratos/segmentos", headers=h).json()
    assert "JUBILADO" in cat["segmentos"] and "SUCURSAL" in cat["canales"]
    # Sin perfil: todo elegible
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()["items"]
    assert all(p["elegibilidad"]["elegible"] for p in of)
    # Segmento JUBILADO: Jubilados elegible, Personal (AGENTE_PUBLICO/DOCENTE/MUNICIPAL) no
    of = {p["codigo"]: p for p in client.get("/api/creditos/contratos/oferta?segmento=JUBILADO", headers=h).json()["items"]}
    assert of["LP-JUB-01"]["elegibilidad"]["elegible"] is True
    assert of["LP-PERS-01"]["elegibilidad"]["elegible"] is False
    # solo_elegibles excluye el no elegible
    cods = {p["codigo"] for p in client.get("/api/creditos/contratos/oferta?segmento=JUBILADO&solo_elegibles=true", headers=h).json()["items"]}
    assert "LP-JUB-01" in cods and "LP-PERS-01" not in cods


def test_originar_respeta_disponibilidad(client):
    h = _auth(client)
    jub = _jub(client, h)
    base = {"producto_id": jub["id"], "cliente_nombre": "GOMEZ", "monto": 1000000, "plazo": 24}
    # Sin perfil: se puede originar (compatibilidad hacia atrás)
    assert client.post("/api/creditos/contratos/originar", headers=h, json=base).status_code == 201
    # Segmento no habilitado → 422
    bad = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "segmento": "AGENTE_PUBLICO"})
    assert bad.status_code == 422 and "disponibilidad" in bad.text.lower()
    # Edad por debajo del mínimo (60) → 422
    joven = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "segmento": "JUBILADO", "edad": 50})
    assert joven.status_code == 422
    # Perfil válido → 201
    ok = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "segmento": "JUBILADO", "canal": "SUCURSAL", "edad": 70})
    assert ok.status_code == 201, ok.text


def _web_only(client, h):
    """Crea y publica un producto cuyo único canal habilitado es WEB (solo portal)."""
    pid = client.post("/api/creditos/productos", headers=h, json={"nombre": "Prestamo Web QA"}).json()["id"]
    det = client.get(f"/api/creditos/productos/{pid}", headers=h).json()
    comps = [{"codigo": c["codigo"], "config": c["config"], "activo": c["activo"], "heredado": c.get("heredado", False)}
             for c in det["componentes"]]
    av = next((c for c in comps if c["codigo"] == "AVAILABILITY"), None)
    if av is None:
        av = {"codigo": "AVAILABILITY", "config": {}, "activo": True, "heredado": False}; comps.append(av)
    av["activo"] = True
    av["config"] = {**(av["config"] or {}), "canales": ["WEB"]}
    r = client.put(f"/api/creditos/productos/{pid}/config", headers=h, json={**det["cfg"], "componentes": comps})
    assert r.status_code == 200, r.text
    for acc in ("revisar", "aprobar", "publicar"):
        rr = client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": acc})
        assert rr.status_code == 200, (acc, rr.text)
    return pid


def test_web_only_no_se_origina_desde_backoffice(client):
    """H-184: un producto 'solo WEB' no debe poder originarse desde el backoffice como venta de sucursal,
    ni siquiera dejando el canal vacío (antes, canal vacío salteaba el chequeo de disponibilidad)."""
    h = _auth(client)
    pid = _web_only(client, h)
    # confirmar que el producto quedó solo-WEB
    det = client.get(f"/api/creditos/productos/{pid}", headers=h).json()
    assert det["disponibilidad"]["canales"] == ["WEB"]
    base = {"producto_id": pid, "cliente_nombre": "GOMEZ", "monto": 1000000, "plazo": 24}
    # canal SUCURSAL → 422 (control explícito)
    assert client.post("/api/creditos/contratos/originar", headers=h, json={**base, "canal": "SUCURSAL"}).status_code == 422
    # canal VACÍO/omitido → 422 (loophole cerrado: default backoffice = SUCURSAL)
    r_vacio = client.post("/api/creditos/contratos/originar", headers=h, json=base)
    assert r_vacio.status_code == 422, r_vacio.text
    # canal WEB explícito → 201 (procesar el canal legítimo sí se permite)
    r_web = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "canal": "WEB", "desembolsar": False})
    assert r_web.status_code == 201, r_web.text


def test_oferta_backoffice_filtra_por_canal(client):
    """H-185: la oferta del backoffice esconde (filtro duro) un producto solo-WEB cuando el operador
    origina por un canal donde no está habilitado; con canal WEB o sin canal, aparece."""
    h = _auth(client)
    pid = _web_only(client, h)
    def cods(qs=""):
        return {p["id"] for p in client.get(f"/api/creditos/contratos/oferta{qs}", headers=h).json()["items"]}
    assert pid not in cods("?canal=SUCURSAL")   # solo-WEB no se lista en canal sucursal
    assert pid in cods("?canal=WEB")            # sí en canal web
    assert pid in cods()                         # sin canal: catálogo completo


def test_backdating_y_reversa(client):
    """Fase F: pago con fecha valor pasada y reversa que deshace el efecto (recompute)."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "LOPEZ", "monto": 1200000, "plazo": 24}).json()
    cid = c["id"]
    fv = c["fecha_valor"]
    # Backdating: pago con fecha valor = fecha de desembolso (no futura, no anterior al desembolso)
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "fecha": fv})
    assert r.status_code == 200, r.text
    c1 = r.json()
    assert c1["cuotas"][0]["estado"] == "PAGADA"
    pay = next(a for a in c1["actividades"] if a["tipo"] == "PAYMENT")
    assert pay["fecha"] == fv
    saldo_tras_pago = c1["saldo_capital"]
    assert saldo_tras_pago < 1200000
    # Fecha futura → 422
    fut = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "fecha": "2999-01-01"})
    assert fut.status_code == 422
    # Reversar el pago → cuota vuelve a PENDIENTE y saldo se restaura
    rv = client.post(f"/api/creditos/contratos/{cid}/actividad/{pay['id']}/reversar", headers=h)
    assert rv.status_code == 200, rv.text
    c2 = rv.json()
    assert c2["cuotas"][0]["estado"] == "PENDIENTE"
    assert c2["saldo_capital"] == 1200000
    assert c2["estado"] == "ACTIVO"
    assert any(a["tipo"] == "REVERSAL" and a["reversaDe"] == pay["id"] for a in c2["actividades"])
    assert any(a["id"] == pay["id"] and a["estado"] == "REVERSADA" for a in c2["actividades"])
    # No se puede reversar dos veces
    again = client.post(f"/api/creditos/contratos/{cid}/actividad/{pay['id']}/reversar", headers=h)
    assert again.status_code == 409


def test_reversa_de_payoff_reabre_contrato(client):
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "DIAZ", "monto": 1000000, "plazo": 12}).json()
    cid = c["id"]
    po = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYOFF"}).json()
    assert po["estado"] == "CERRADO" and po["saldo_capital"] == 0
    payoff_act = next(a for a in po["actividades"] if a["tipo"] == "PAYOFF")
    # Contrato cerrado: no admite nuevas actividades
    assert client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).status_code == 409
    # Reversar el payoff reabre el contrato
    re = client.post(f"/api/creditos/contratos/{cid}/actividad/{payoff_act['id']}/reversar", headers=h).json()
    assert re["estado"] == "ACTIVO" and re["saldo_capital"] == 1000000
    assert all(q["estado"] == "PENDIENTE" for q in re["cuotas"])


def _var(client, h):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    return next(p for p in of["items"] if p["codigo"] == "LP-VAR-01")


def test_relationship_pricing_descuenta_tna(client):
    """Fase G: la relación PREMIUM baja la TNA en puntos al originar (relationship pricing)."""
    h = _auth(client)
    cat = client.get("/api/creditos/contratos/segmentos", headers=h).json()
    assert any(r["codigo"] == "PREMIUM" and r["bonusTna"] == -4.0 for r in cat["relaciones"])
    p = _pers(client, h)
    base = {"producto_id": p["id"], "cliente_nombre": "REL", "monto": 1000000, "plazo": 12}
    estd = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "relacion": "ESTANDAR"}).json()
    prem = client.post("/api/creditos/contratos/originar", headers=h, json={**base, "relacion": "PREMIUM"}).json()
    assert prem["tasa"] == estd["tasa"] - 4  # 4 puntos de descuento
    assert prem["snapshot"]["relacion"] == "PREMIUM" and prem["snapshot"]["bonus_relacion"] == -4.0


def test_relationship_pricing_no_perfora_piso_de_banda(client):
    """La banda de negociación es un piso duro: el descuento por relación no la puede perforar."""
    ha, pid = _publicar_negociable(client)  # banda 40–60
    base = {"producto_id": pid, "cliente_nombre": "PISO", "monto": 1000000, "plazo": 12}
    # Negociada al piso (40) + PREMIUM (−4): sin clamp daría 36; con clamp queda en 40.
    prem = client.post("/api/creditos/contratos/originar", headers=ha, json={**base, "tasa": 40, "relacion": "PREMIUM"}).json()
    assert prem["tasa"] == 40, f"el piso 40 no debe perforarse; got {prem['tasa']}"
    assert prem["snapshot"]["piso_relacion"] == 40
    # Con margen sobre el piso el descuento sí se aplica: 50 − 4 = 46 (dentro de banda).
    prem2 = client.post("/api/creditos/contratos/originar", headers=ha, json={**base, "tasa": 50, "relacion": "PREMIUM"}).json()
    assert prem2["tasa"] == 46


def test_bundles_listado(client):
    h = _auth(client)
    b = client.get("/api/creditos/contratos/bundles", headers=h).json()
    assert b["total"] >= 1
    bnd = next(x for x in b["items"] if x["codigo"] == "BND-CAP-01")
    roles = {mi["producto"]["codigo"]: mi["rol"] for mi in bnd["miembros"]}
    assert roles["LP-PERS-01"] == "PRINCIPAL" and roles["LP-JUB-01"] == "COMPLEMENTO"


def test_repricing_periodico_actualiza_tna_variable(client):
    """Fase G: regla periódica REPRICING recalcula la TNA desde el índice; la reversa la restaura."""
    h = _auth(client)
    var = _var(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": var["id"], "cliente_nombre": "VARCLI", "monto": 1000000, "plazo": 12}).json()
    cid = c["id"]
    tna0 = c["tasa"]  # BADLAR(45) + margen(10) = 55
    assert tna0 == 55
    # Cambia el índice BADLAR y aplica repricing
    badlar = next(i for i in client.get("/api/creditos/indices", headers=h).json()["items"] if i["codigo"] == "BADLAR")
    client.put(f"/api/creditos/indices/{badlar['id']}", headers=h, json={**badlar, "valor": 60})
    rp = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "REPRICING"}).json()
    assert rp["tasa"] == 70  # 60 + 10
    rep = next(a for a in rp["actividades"] if a["tipo"] == "REPRICING")
    # Reversar el repricing restaura la TNA anterior
    re = client.post(f"/api/creditos/contratos/{cid}/actividad/{rep['id']}/reversar", headers=h).json()
    assert re["tasa"] == 55
    # Una línea FIJA no admite repricing
    pers = client.post("/api/creditos/contratos/originar", headers=h,
                       json={"producto_id": _pers(client, h)["id"], "cliente_nombre": "F", "monto": 1000000, "plazo": 12}).json()
    bad = client.post(f"/api/creditos/contratos/{pers['id']}/actividad", headers=h, json={"tipo": "REPRICING"})
    assert bad.status_code == 422


def _sum(lineas, k):
    return round(sum(l[k] for l in lineas), 2)


def test_asientos_contables_de_originacion_y_pago(client):
    """Integración con Contabilidad: originar y pagar generan asientos balanceados en el Libro Diario."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "CONTAB", "monto": 1200000, "plazo": 12}).json()
    cid = c["id"]
    # Asiento de otorgamiento: Debe capital / Haber Caja = monto, balanceado
    otorg = next(a for a in c["asientos"] if a["origen"] == "pp_otorgamiento")
    assert _sum(otorg["lineas"], "debe") == _sum(otorg["lineas"], "haber") == 1200000
    assert any(l["cuenta"] == "1.1.01" and l["haber"] == 1200000 for l in otorg["lineas"])
    # Aparece en el Libro Diario de Contabilidad
    ld = client.get("/api/creditos/contabilidad/libro-diario", headers=h).json()
    assert any("CONTAB" in a["concepto"] or c["numero_contrato"] in a["concepto"] for a in ld)
    # Pago genera asiento de cobranza balanceado
    c2 = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    cob = next(a for a in c2["asientos"] if a["origen"] == "pp_cobranza")
    assert _sum(cob["lineas"], "debe") == _sum(cob["lineas"], "haber")
    assert any(l["cuenta"] == "1.1.01" and l["debe"] > 0 for l in cob["lineas"])  # Debe Caja


def test_reversa_de_pago_genera_contra_asiento(client):
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "CONTAB2", "monto": 1000000, "plazo": 12}).json()
    cid = c["id"]
    pay = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    act = next(a for a in pay["actividades"] if a["tipo"] == "PAYMENT")
    n_antes = len(pay["asientos"])
    rev = client.post(f"/api/creditos/contratos/{cid}/actividad/{act['id']}/reversar", headers=h).json()
    # Se agregó un contra-asiento (no se borró el original)
    assert len(rev["asientos"]) == n_antes + 1
    contra = next(a for a in rev["asientos"] if a["origen"] == "pp_reversa")
    # El contra-asiento invierte debe/haber respecto del de cobranza
    assert _sum(contra["lineas"], "debe") == _sum(contra["lineas"], "haber")
    assert any(l["cuenta"] == "1.1.01" and l["haber"] > 0 for l in contra["lineas"])  # ahora Caja al Haber


def test_originar_desde_solicitud_legacy(client):
    """Integración con Solicitudes: originar un contrato pp desde una solicitud legacy aprobada."""
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.SolicitudCredito(id=990001, fecha_soli=datetime.date(2026, 1, 10),
        cuil="20111222333", apellido_nombre="PEREZ JUAN", montosol=Decimal("1500000"),
        linea=6097, estado="A", cubica="C", no_resol=0, en_reso=False, lote=0))
    db.commit(); db.close()

    h = _auth(client)
    # Aparece en el listado de solicitudes aprobadas originables
    sols = client.get("/api/creditos/contratos/solicitudes?q=PEREZ", headers=h).json()
    assert any(s["id"] == 990001 and s["monto"] == 1500000 for s in sols["items"])

    p = _pers(client, h)
    r = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": p["id"], "cliente_nombre": "PEREZ JUAN", "monto": 1500000,
        "plazo": 24, "solicitud_id": 990001})
    assert r.status_code == 201, r.text
    assert r.json()["solicitud_origen"] == 990001

    # Ya no aparece como originable (excluida)
    sols2 = client.get("/api/creditos/contratos/solicitudes?q=PEREZ", headers=h).json()
    assert not any(s["id"] == 990001 for s in sols2["items"])
    # No se puede originar dos veces la misma solicitud
    dup = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": p["id"], "cliente_nombre": "PEREZ JUAN", "monto": 1500000,
        "plazo": 24, "solicitud_id": 990001})
    assert dup.status_code == 409


def test_tablero_cartera(client):
    """Tablero de cartera: KPIs, desglose por estado/producto y detalle para drill-down tras originar y pagar."""
    h = _auth(client)
    p = _pers(client, h)
    base_n = client.get("/api/creditos/contratos/tablero", headers=h).json()["kpis"]["contratos"]
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "TAB", "monto": 1000000, "plazo": 12}).json()
    client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h, json={"tipo": "PAYMENT"})
    t = client.get("/api/creditos/contratos/tablero", headers=h).json()
    k = t["kpis"]
    assert k["contratos"] == base_n + 1
    assert k["capitalColocado"] >= 1000000
    assert 0 < k["saldoVigente"] < 1000000  # bajó tras el pago
    assert k["cuotasPagadas"] >= 1 and k["cobrado"] > 0
    # nuevos agregados: por estado/producto son listas; aging y evolución están presentes.
    assert any(e["estado"] == "ACTIVO" and e["contratos"] >= 1 for e in t["porEstado"])
    assert any(pp["codigo"] == "LP-PERS-01" and pp["contratos"] >= 1 for pp in t["porProducto"])
    assert len(t["aging"]) == 5 and len(t["evolucion"]) == 6
    # el detalle para el drill-down trae el contrato con su bucket de mora y días de atraso.
    row = next(r for r in t["contratos"] if r["numero"] == c["numero_contrato"])
    assert "moraBucket" in row and "diasAtraso" in row and row["estado"] == "ACTIVO"


def test_preview_coincide_con_contrato_originado(client):
    """Única fuente de verdad: el cronograma del preview == el del contrato originado."""
    h = _auth(client)
    p = _pers(client, h)
    cfg = p["cfg"]
    charge = next((c for c in p["componentes"] if c["codigo"] == "CHARGE" and c["activo"]), None)
    tax = next((c for c in p["componentes"] if c["codigo"] == "TAX" and c["activo"]), None)
    rs = next((c for c in p["componentes"] if c["codigo"] == "REPAYMENT_SCHEDULE" and c["activo"]), None)
    payload = {
        "sistema": cfg["sistema"], "monto": 1000000, "plazo": 12, "tna": cfg["tna"],
        "cargoOtorg": cfg["cargoOtorg"], "gracia": cfg.get("graciaCapital", 0), "frecuencia": cfg["frecuencia"],
        "cargos": [{"porcentaje": it.get("porcentaje"), "momento": it.get("momento")} for it in (charge["config"].get("items") or [])] if charge else [],
        "impuestos": [{"base": it.get("base"), "porcentaje": it.get("porcentaje")} for it in (tax["config"].get("items") or [])] if tax else [],
        "diaPago": (rs["config"].get("diaPago", 5) if rs else 5),
        "primerVencimientoDias": (rs["config"].get("primerVencimientoDias", 30) if rs else 30),
        "ajusteFinDeSemana": (rs["config"].get("ajusteFinDeSemana", "SIN_AJUSTE") if rs else "SIN_AJUSTE"),
        "tipoCuota": (rs["config"].get("tipoCuota", "VENCIDA") if rs else "VENCIDA"),
        "financiable": bool(charge["config"].get("financiable", False)) if charge else False,
        "cargoMomento": (charge["config"].get("momento", "PRORRATEADO") if charge else "PRORRATEADO"),
    }
    prev = client.post(f"/api/creditos/productos/preview", headers=h, json=payload).json()
    cto = client.post("/api/creditos/contratos/originar", headers=h,
                      json={"producto_id": p["id"], "cliente_nombre": "COH", "monto": 1000000, "plazo": 12}).json()
    assert len(prev["rows"]) == len(cto["cuotas"]) == 12
    for a, b in zip(prev["rows"], cto["cuotas"]):
        assert a["total"] == b["total"] and a["capital"] == b["capital"]
        assert a["interes"] == b["interes"] and a["cargos"] == b["cargos"]
        assert a["fecha_vencimiento"] == b["fecha_vencimiento"]


def test_otorgar_y_desembolsar_por_pasos(client):
    """Proceso de originación: otorgar (A_LIQUIDAR) y desembolsar como pasos separados."""
    h = _auth(client)
    p = _pers(client, h)
    r = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": p["id"], "cliente_nombre": "WIZARD", "monto": 1000000, "plazo": 12,
        "desembolsar": False, "datos_adicionales": {"destino": "CONSUMO", "cbu": "2850", "observaciones": "ok"}})
    assert r.status_code == 201
    c = r.json()
    cid = c["id"]
    assert c["estado"] == "A_LIQUIDAR"
    assert c["datos_adicionales"]["destino"] == "CONSUMO"
    # El cliente recibe el monto completo: los cargos están dentro del cronograma, no se deducen (H-085).
    assert c["liquidacion"]["neto"] == c["liquidacion"]["monto"]
    assert not c["asientos"] and not c["actividades"]
    # No admite pagos ni reversa antes de desembolsar
    assert client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).status_code == 409
    # Desembolsar → ACTIVO + asiento + DISBURSEMENT
    d = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=h).json()
    assert d["estado"] == "ACTIVO"
    assert any(a["origen"] == "pp_otorgamiento" for a in d["asientos"])
    assert any(a["tipo"] == "DISBURSEMENT" for a in d["actividades"])
    # No se puede desembolsar dos veces
    assert client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=h).status_code == 409


def test_export_pdf_y_excel(client):
    """Exportación: PDF de un contrato y Excel de la cartera."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "EXP", "monto": 1000000, "plazo": 12}).json()
    pdf = client.get(f"/api/creditos/contratos/{c['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    xls = client.get("/api/creditos/contratos/export.xlsx", headers=h)
    assert xls.status_code == 200 and xls.content[:2] == b"PK" and len(xls.content) > 1000


def test_devengamiento_no_duplica_ingreso(client):
    """Devengar reconoce el interés (Debe a devengar / Haber ganados); el cobro salda la cuenta
    a cobrar sin volver a reconocer el ingreso."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "DEV", "monto": 1000000, "plazo": 12}).json()
    cid = c["id"]
    d = client.post(f"/api/creditos/contratos/{cid}/devengar", headers=h).json()
    dev = next(a for a in d["asientos"] if a["origen"] == "pp_devengo")
    interes = d["cuotas"][0]["interes"]
    assert _sum(dev["lineas"], "debe") == _sum(dev["lineas"], "haber") == interes
    assert any(l["cuenta"] == "1.2.02" and l["debe"] == interes for l in dev["lineas"])   # Debe a devengar
    assert any(l["cuenta"] == "4.1.01" and l["haber"] == interes for l in dev["lineas"])  # Haber ganados
    assert d["cuotas"][0]["devengada"] is True
    # Cobro de la cuota devengada: el interés acredita a 1.2.02 (no a 4.1.01)
    pay = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    cob = next(a for a in pay["asientos"] if a["origen"] == "pp_cobranza")
    assert any(l["cuenta"] == "1.2.02" and l["haber"] == interes for l in cob["lineas"])
    assert not any(l["cuenta"] == "4.1.01" for l in cob["lineas"])
    # No se puede devengar dos veces la misma cuota: la 2ª devenga la cuota siguiente
    d2 = client.post(f"/api/creditos/contratos/{cid}/devengar", headers=h).json()
    assert d2["cuotas"][1]["devengada"] is True


def test_asiento_separa_comisiones_de_impuestos(client):
    """El pago imputa comisiones (4.1.04) e impuestos (IVA) a cuentas SEPARADAS, no todo a IVA."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "SEP", "monto": 1000000, "plazo": 12}).json()
    q1 = c["cuotas"][0]
    assert q1["impuestos"] > 0 and q1["cargos"] > q1["impuestos"]  # hay comisiones además del IVA
    pay = client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    cob = next(a for a in pay["asientos"] if a["origen"] == "pp_cobranza")
    comis = next((l for l in cob["lineas"] if l["cuenta"] == "4.1.04"), None)
    iva = next((l for l in cob["lineas"] if l["cuenta"] in ("2.1.07", "2.1.01")), None)
    assert comis and iva and comis["haber"] > 0 and iva["haber"] > 0
    assert abs(iva["haber"] - q1["impuestos"]) < 0.01                    # IVA = sólo impuestos
    assert abs(comis["haber"] - (q1["cargos"] - q1["impuestos"])) < 0.01  # comisiones = cargos − impuestos
    assert _sum(cob["lineas"], "debe") == _sum(cob["lineas"], "haber")


def test_mora_punitorio_en_cuota_vencida(client):
    """H-086: al pagar una cuota vencida se cobra punitorio (moraTNA) y el asiento balancea."""
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models_productos as mp
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "MORA", "monto": 1_000_000, "plazo": 12}).json()
    cid = c["id"]
    assert c["snapshot"]["mora_tna"] == 120.0  # LP-PERS-01 tiene MORA 120%
    total1 = c["cuotas"][0]["total"]
    # Forzamos el vencimiento de la 1ª cuota a 40 días atrás para simular mora.
    hoy = datetime.date.today()
    with SessionLocal() as db:
        cto = db.get(mp.PPContrato, cid)
        q1 = min(cto.cuotas, key=lambda x: x.numero_cuota)
        q1.fecha_vencimiento = hoy - datetime.timedelta(days=40)
        db.commit()
    # Pagamos hoy (no futura): 40 − 5 gracia = 35 días de mora.
    rp = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    assert rp.status_code == 200, rp.text
    pago = rp.json()
    act = next(a for a in pago["actividades"] if a["tipo"] == "PAYMENT")
    assert act["importe"] > total1, "el importe debe incluir el punitorio"
    assert act["dato"]["mora_dias"] == 35 and act["dato"]["interes_punitorio"] > 0
    # punitorio esperado = cuota · (120/365)/100 · 35
    esperado_pun = round(total1 * (120 / 365 / 100) * 35, 2)
    assert abs(act["dato"]["interes_punitorio"] - esperado_pun) < 1
    # el asiento del pago balancea (debe == haber)
    asi = pago["asientos"][-1]
    debe = sum(l.get("debe", 0) for l in asi["lineas"])
    haber = sum(l.get("haber", 0) for l in asi["lineas"])
    assert abs(debe - haber) < 0.01


def test_sin_mora_si_cuota_al_dia(client):
    """Si la cuota no está vencida (o dentro de los días de gracia), no hay punitorio."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "ALDIA", "monto": 1_000_000, "plazo": 12}).json()
    total1 = c["cuotas"][0]["total"]
    rp = client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    act = next(a for a in rp["actividades"] if a["tipo"] == "PAYMENT")
    assert abs(act["importe"] - total1) < 0.01  # sin punitorio
    assert "interes_punitorio" not in (act.get("dato") or {})


def test_todos_los_asientos_balancean_en_el_ciclo(client):
    """Invariante contable: todo asiento pp_ (otorgamiento, devengo, pago, mora, payoff) balancea."""
    import datetime
    from app.core.database import SessionLocal
    from app import models_productos as mp
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "ASI", "monto": 1_000_000, "plazo": 12}).json()
    cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/devengar", headers=h)
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    # forzar mora en la próxima cuota
    with SessionLocal() as db:
        cto = db.get(mp.PPContrato, cid)
        q = min([x for x in cto.cuotas if x.estado == "PENDIENTE"], key=lambda x: x.numero_cuota)
        q.fecha_vencimiento = datetime.date.today() - datetime.timedelta(days=30)
        db.commit()
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})  # con mora
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    assert len(det["asientos"]) >= 4
    for a in det["asientos"]:
        debe = sum(l.get("debe", 0) for l in a["lineas"])
        haber = sum(l.get("haber", 0) for l in a["lineas"])
        assert abs(debe - haber) < 0.01, f"asiento desbalanceado: {a['concepto']} ({debe} vs {haber})"


def test_relacion_invalida_rechaza(client):
    """Una relación inexistente no se acepta silenciosamente (evita basura en el snapshot)."""
    h = _auth(client)
    p = _pers(client, h)
    base = {"producto_id": p["id"], "cliente_nombre": "X", "monto": 1_000_000, "plazo": 12}
    assert client.post("/api/creditos/contratos/originar", headers=h, json={**base, "relacion": "INEXISTENTE"}).status_code == 422
    # las válidas siguen funcionando
    assert client.post("/api/creditos/contratos/originar", headers=h, json={**base, "relacion": "PREMIUM"}).status_code == 201
    assert client.post("/api/creditos/contratos/originar", headers=h, json={**base, "relacion": "ESTANDAR"}).status_code == 201


def test_bundle_muestra_version_vigente_no_borrador(client):
    """El bundle serializa la versión VIGENTE del miembro, no una v2 con vigencia futura."""
    import datetime
    h = _auth(client)
    hcred = {"Authorization": f"Bearer {client.post('/api/creditos/auth/login', data={'username': 'creditos', 'password': 'cred123'}).json()['access_token']}"}
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    pid = pers["id"]
    tna_vigente = pers["cfg"]["tna"]
    # v2 con TNA distinta y vigencia a futuro
    futuro = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    nv = client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=h).json()
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**nv["cfg"], "tna": tna_vigente + 40, "vigenciaDesde": futuro})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "publicar"})
    # El bundle debe mostrar la TNA vigente (no la futura)
    bnd = next(x for x in client.get("/api/creditos/contratos/bundles", headers=h).json()["items"] if x["codigo"] == "BND-CAP-01")
    princ = next(mi for mi in bnd["miembros"] if mi["producto"]["codigo"] == "LP-PERS-01")
    assert princ["producto"]["cfg"]["tna"] == tna_vigente, \
        f"el bundle debe mostrar la versión vigente ({tna_vigente}), no la futura; got {princ['producto']['cfg']['tna']}"


def test_pago_parcial_de_cuota(client):
    """Situación 5: un abono parcial no completa la cuota; se acumula en `pagado` y el saldo no baja."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "PARCIAL", "monto": 1_000_000, "plazo": 12}).json()
    cid = c["id"]
    total1, cap1, saldo0 = c["cuotas"][0]["total"], c["cuotas"][0]["capital"], c["saldo_capital"]
    mitad = round(total1 / 2, 2)
    # abono parcial (la mitad)
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "importe": mitad}).json()
    q1 = r["cuotas"][0]
    assert q1["estado"] == "PENDIENTE" and abs(q1["pagado"] - mitad) < 0.01
    assert r["saldo_capital"] == saldo0    # no baja hasta completar la cuota
    # asiento del parcial balancea
    asi = r["asientos"][-1]
    assert abs(sum(l.get("debe", 0) for l in asi["lineas"]) - sum(l.get("haber", 0) for l in asi["lineas"])) < 0.01
    # completar la cuota → PAGADA y el saldo baja por el capital
    r2 = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    assert r2["cuotas"][0]["estado"] == "PAGADA"
    assert abs(r2["saldo_capital"] - (saldo0 - cap1)) < 0.5


def test_reversa_de_pago_parcial(client):
    """Reversar un abono parcial restaura `pagado` a lo anterior (event-sourcing)."""
    h = _auth(client)
    p = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": p["id"], "cliente_nombre": "REVPARC", "monto": 1_000_000, "plazo": 12}).json()
    cid = c["id"]
    total1 = c["cuotas"][0]["total"]
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "importe": round(total1 / 3, 2)}).json()
    act = next(a for a in r["actividades"] if a["tipo"] == "PAYMENT")
    assert r["cuotas"][0]["pagado"] > 0
    rr = client.post(f"/api/creditos/contratos/{cid}/actividad/{act['id']}/reversar", headers=h).json()
    assert rr["cuotas"][0]["pagado"] == 0 and rr["cuotas"][0]["estado"] == "PENDIENTE"


def _prep(client, h):
    p = _pers(client, h)
    return client.post("/api/creditos/contratos/originar", headers=h,
                       json={"producto_id": p["id"], "cliente_nombre": "PREP", "monto": 1_000_000, "plazo": 12}).json()


def test_prepago_baja_cuota(client):
    """Prepago BAJA_CUOTA: mismo número de cuotas pendientes, cuota menor; saldo baja por el importe."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    saldo_pre = det["saldo_capital"]; cuota_pre = next(q for q in det["cuotas"] if q["estado"] == "PENDIENTE")["total"]
    n_pre = len([q for q in det["cuotas"] if q["estado"] == "PENDIENTE"])
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PARTIAL_PREPAYMENT", "importe": 300000, "modo": "BAJA_CUOTA"}).json()
    pend = [q for q in r["cuotas"] if q["estado"] == "PENDIENTE"]
    assert len(pend) == n_pre                                   # mismo plazo
    assert pend[0]["total"] < cuota_pre                         # cuota menor
    assert abs(r["saldo_capital"] - (saldo_pre - 300000)) < 1   # saldo bajó por el prepago
    assert abs(sum(q["capital"] for q in pend) - r["saldo_capital"]) < 1
    assert pend[-1]["saldo_final"] == 0
    asi = r["asientos"][-1]
    assert abs(sum(l.get("debe", 0) for l in asi["lineas"]) - sum(l.get("haber", 0) for l in asi["lineas"])) < 0.01


def test_prepago_baja_plazo(client):
    """Prepago BAJA_PLAZO: menos cuotas pendientes; saldo baja por el importe."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    n_pre = len([q for q in det["cuotas"] if q["estado"] == "PENDIENTE"])
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PARTIAL_PREPAYMENT", "importe": 300000, "modo": "BAJA_PLAZO"}).json()
    pend = [q for q in r["cuotas"] if q["estado"] == "PENDIENTE"]
    assert len(pend) < n_pre                                    # menos plazo
    assert abs(r["saldo_capital"] - (det["saldo_capital"] - 300000)) < 1
    assert pend[-1]["saldo_final"] == 0


def test_reversa_de_prepago_restaura_cronograma(client):
    """Reversar un prepago restaura el cronograma pristino (idempotencia del recompute)."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    cuota_orig = c["cuotas"][1]["total"]; saldo_orig = c["saldo_capital"]
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PARTIAL_PREPAYMENT", "importe": 300000, "modo": "BAJA_CUOTA"}).json()
    act = next(a for a in r["actividades"] if a["tipo"] == "PARTIAL_PREPAYMENT")
    assert r["cuotas"][1]["total"] < cuota_orig
    rr = client.post(f"/api/creditos/contratos/{cid}/actividad/{act['id']}/reversar", headers=h).json()
    assert abs(rr["cuotas"][1]["total"] - cuota_orig) < 0.01 and abs(rr["saldo_capital"] - saldo_orig) < 0.01


def test_prepago_supera_saldo_rechaza(client):
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    bad = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PARTIAL_PREPAYMENT", "importe": 99_000_000})
    assert bad.status_code == 422


def test_diferimiento_capitaliza_interes(client):
    """Payment holiday: difiere N cuotas ($0), capitaliza interés (sube el resto), reversa restaura."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    cuota_orig = c["cuotas"][3]["total"]; saldo0 = c["saldo_capital"]
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT_HOLIDAY", "importe": 2}).json()
    diferidas = [q for q in r["cuotas"] if q["total"] == 0 and q["estado"] == "PENDIENTE"]
    resto = [q for q in r["cuotas"] if q["total"] > 0 and q["estado"] == "PENDIENTE"]
    assert len(diferidas) == 2
    assert resto[0]["total"] > cuota_orig          # el resto sube por la capitalización
    assert r["saldo_capital"] > saldo0             # el saldo creció (interés capitalizado)
    assert r["cuotas"][-1]["saldo_final"] == 0
    # reversa restaura
    act = next(a for a in r["actividades"] if a["tipo"] == "PAYMENT_HOLIDAY")
    rr = client.post(f"/api/creditos/contratos/{cid}/actividad/{act['id']}/reversar", headers=h).json()
    assert abs(rr["saldo_capital"] - saldo0) < 0.01


def test_diferir_cuotas_invalidas_rechaza(client):
    h = _auth(client)
    c = _prep(client, h)
    assert client.post(f"/api/creditos/contratos/{c['id']}/actividad", headers=h, json={"tipo": "PAYMENT_HOLIDAY", "importe": 99}).status_code == 422


def test_refinanciacion_cierra_viejo_y_crea_nuevo(client):
    """Refi: nueva tasa+plazo sobre el saldo; el viejo queda REFINANCIADO y no admite pagos."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    saldo = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()["saldo_capital"]
    r = client.post(f"/api/creditos/contratos/{cid}/refinanciar", headers=h, json={"tasa": 40, "plazo": 18}).json()
    ant, nue = r["anterior"], r["nuevo"]
    assert ant["estado"] == "REFINANCIADO"
    assert nue["estado"] == "ACTIVO" and len(nue["cuotas"]) == 18
    assert abs(nue["monto_original"] - saldo) < 0.01 and nue["snapshot"]["tna"] == 40
    assert abs(sum(q["capital"] for q in nue["cuotas"]) - saldo) < 0.5 and nue["cuotas"][-1]["saldo_final"] == 0
    # el viejo no admite más actividades
    assert client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).status_code == 409


def test_no_reversar_refinanciacion_evita_doble_capital(client):
    """H-154: reversar la actividad RENEGOTIATION del contrato viejo lo reactivaría con el saldo entero
    mientras el nuevo sigue vivo → mismo capital colocado dos veces. Debe bloquearse (422) y el viejo
    seguir REFINANCIADO."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/refinanciar", headers=h, json={"tasa": 40, "plazo": 18})
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    reneg = next(a for a in det["actividades"] if a["tipo"] == "RENEGOTIATION")
    r = client.post(f"/api/creditos/contratos/{cid}/actividad/{reneg['id']}/reversar", headers=h)
    assert r.status_code == 422, r.text
    assert client.get(f"/api/creditos/contratos/{cid}", headers=h).json()["estado"] == "REFINANCIADO"


def test_cobro_caja_registra_medio_pago(client):
    """Caja: el cobro guarda el medio de pago en la actividad (para el recibo)."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h,
                    json={"tipo": "PAYMENT", "medio_pago": "TRANSFERENCIA"}).json()
    act = next(a for a in r["actividades"] if a["tipo"] == "PAYMENT")
    assert act["dato"]["medio_pago"] == "TRANSFERENCIA"


def test_adelanto_de_n_cuotas(client):
    """Adelanto: paga N cuotas de una (N actividades + N asientos), saldo baja por el capital de las N."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    cap3 = sum(c["cuotas"][i]["capital"] for i in range(3))
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "cuotas": 3, "medio_pago": "EFECTIVO"}).json()
    assert len([q for q in r["cuotas"] if q["estado"] == "PAGADA"]) == 3
    assert len([a for a in r["actividades"] if a["tipo"] == "PAYMENT"]) == 3
    assert abs(r["saldo_capital"] - (c["saldo_capital"] - cap3)) < 0.5


def test_prepago_no_pierde_pago_parcial_previo(client):
    """QA navegador: un pago parcial seguido de un prepago no debe perder el abono (H-096)."""
    h = _auth(client)
    c = _prep(client, h); cid = c["id"]
    t2 = c["cuotas"][1]["total"]
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})            # cuota 1
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT", "importe": round(t2/2, 2)})  # parcial cuota 2
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PARTIAL_PREPAYMENT", "importe": 100000, "modo": "BAJA_CUOTA"}).json()
    q2 = next(q for q in r["cuotas"] if q["numero_cuota"] == 2)
    assert abs(q2["pagado"] - round(t2/2, 2)) < 0.01, f"el abono parcial se perdió: pagado={q2['pagado']}"
