"""QA PROFUNDO — no sólo la API: verifica que los datos se PERSISTAN como se espera.

Cada flujo muta vía HTTP (TestClient = commits reales) y luego abre una sesión NUEVA a la
base para leer las filas efectivamente guardadas (pp_contrato, pp_cuota_contrato, pp_actividad,
asiento/asiento_linea), aseverando:
  · persistencia real de contratos, cuotas, actividades y asientos;
  · coherencia motor↔datos: la simulación de refinanciación == el contrato persistido;
  · event-sourcing: reversa marca REVERSADA en DB, restaura cuotas y es idempotente;
  · contabilidad: los asientos quedan guardados y balancean.
Nada de probes de llamada directa (dan falsos positivos con recompute); todo por HTTP + relectura.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cliente_id(client, h):
    return client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]


def _pers(client, h):
    return next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"]
               if p["codigo"] == "LP-PERS-01")


def _originar(client, h, nombre, monto=1_000_000, plazo=24, desembolsar=True):
    pers = _pers(client, h)
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": nombre, "monto": monto,
        "plazo": plazo, "desembolsar": desembolsar}).json()
    return c["id"]


def _db():
    from app.core.database import SessionLocal
    return SessionLocal()


def _gw(username: str, *perms: str, user_id: int = 950) -> dict:
    """Headers del gateway de Portezuelo para un usuario con estos permisos (sin prefijo `creditos:`)."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"creditos:{p}" for p in perms)}


def _activar_wf(objeto: str) -> None:
    """El cuatro-ojos se siembra INACTIVO (app nueva single-admin, H-141); los tests que ejercitan el
    workflow lo activan explícitamente en Configuraciones."""
    from tests.config_falsa import CONFIG
    CONFIG.activar(objeto)

def _asientos_de(db, numero_contrato):
    from app import models
    return db.query(models.Asiento).filter(
        models.Asiento.concepto.like(f"%{numero_contrato}%")).all()


def _balancea(db, numero_contrato):
    for a in _asientos_de(db, numero_contrato):
        debe = sum(Decimal(str(l.debe or 0)) for l in a.lineas)
        haber = sum(Decimal(str(l.haber or 0)) for l in a.lineas)
        assert abs(debe - haber) < Decimal("0.01"), f"asiento '{a.concepto}' desbalanceado {debe} vs {haber}"


# ─────────────────────────────────────────────────────────────────────────────
# 1) DESEMBOLSO: persiste contrato ACTIVO, cuotas y actividad + asiento
# ─────────────────────────────────────────────────────────────────────────────
def test_desembolso_persiste_todo(client):
    from app import models_productos as mp
    h = _auth(client)
    cid = _originar(client, h, "DEEP-DESEMB", 1_000_000, 12)

    with _db() as db:
        c = db.get(mp.PPContrato, cid)
        assert c is not None and c.estado == "ACTIVO"
        # cuotas persistidas: 12 filas, Σcapital = monto, cierra en 0
        cuotas = db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all()
        assert len(cuotas) == 12
        scap = sum(Decimal(str(q.capital)) for q in cuotas)
        assert abs(scap - Decimal("1000000")) < Decimal("0.5")
        ult = max(cuotas, key=lambda q: q.numero_cuota)
        assert abs(Decimal(str(ult.saldo_final))) < Decimal("0.01")
        # actividad de desembolso persistida
        acts = db.query(mp.PPActividad).filter_by(contrato_id=cid).all()
        assert any(a.tipo == "DISBURSEMENT" and a.estado == "EJECUTADA" for a in acts)
        # asiento de originación/desembolso guardado y balanceado
        assert _asientos_de(db, c.numero_contrato), "no se guardó ningún asiento"
        _balancea(db, c.numero_contrato)


# ─────────────────────────────────────────────────────────────────────────────
# 2) PAGO: persiste actividad + cuota.pagado/estado + asiento; saldo baja
# ─────────────────────────────────────────────────────────────────────────────
def test_pago_persiste_cuota_actividad_y_asiento(client):
    from app import models_productos as mp
    h = _auth(client)
    cid = _originar(client, h, "DEEP-PAGO", 1_000_000, 12)
    with _db() as db:
        saldo0 = Decimal(str(db.get(mp.PPContrato, cid).saldo_capital))

    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    assert r.status_code == 200, r.text

    with _db() as db:
        c = db.get(mp.PPContrato, cid)
        num = c.numero_contrato
        cuotas = sorted(db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all(),
                        key=lambda q: q.numero_cuota)
        q1 = cuotas[0]
        assert q1.estado == "PAGADA", "la cuota 1 no quedó PAGADA en DB"
        assert Decimal(str(q1.pagado)) >= Decimal(str(q1.total)) - Decimal("0.01")
        # saldo persistido bajó por el capital de la cuota
        assert Decimal(str(c.saldo_capital)) < saldo0
        assert abs((saldo0 - Decimal(str(c.saldo_capital))) - Decimal(str(q1.capital))) < Decimal("0.5")
        # actividad PAYMENT persistida y ejecutada
        acts = db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="PAYMENT").all()
        assert len(acts) == 1 and acts[0].estado == "EJECUTADA"
        _balancea(db, num)


# ─────────────────────────────────────────────────────────────────────────────
# 3) REVERSA: marca REVERSADA en DB, restaura la cuota, contra-asiento; idempotente
# ─────────────────────────────────────────────────────────────────────────────
def test_reversa_persiste_y_es_idempotente(client):
    from app import models_productos as mp
    h = _auth(client)
    cid = _originar(client, h, "DEEP-REVERSA", 1_000_000, 12)
    pay = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"}).json()
    act_id = next(a["id"] for a in pay["actividades"] if a["tipo"] == "PAYMENT")

    with _db() as db:
        saldo_post_pago = Decimal(str(db.get(mp.PPContrato, cid).saldo_capital))

    rev = client.post(f"/api/creditos/contratos/{cid}/actividad/{act_id}/reversar", headers=h)
    assert rev.status_code == 200, rev.text

    with _db() as db:
        c = db.get(mp.PPContrato, cid)
        num = c.numero_contrato
        # la actividad original quedó REVERSADA
        orig = db.get(mp.PPActividad, act_id)
        assert orig.estado == "REVERSADA", "el PAYMENT no quedó REVERSADA en DB"
        # hay una entrada REVERSAL que apunta a ella
        reversal = db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="REVERSAL").all()
        assert any(x.reversa_de == act_id for x in reversal), "no se guardó REVERSAL apuntando al pago"
        # la cuota 1 volvió a PENDIENTE con pagado 0 (recompute desde pristino)
        q1 = min(db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all(), key=lambda q: q.numero_cuota)
        assert q1.estado == "PENDIENTE" and Decimal(str(q1.pagado)) == Decimal("0")
        # saldo restaurado (mayor que tras el pago)
        assert Decimal(str(c.saldo_capital)) > saldo_post_pago
        _balancea(db, num)

    # idempotencia: re-reversar la MISMA actividad no debe duplicar ni romper
    n_reversal_1 = None
    with _db() as db:
        n_reversal_1 = db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="REVERSAL").count()
    client.post(f"/api/creditos/contratos/{cid}/actividad/{act_id}/reversar", headers=h)  # segundo intento
    with _db() as db:
        n_reversal_2 = db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="REVERSAL").count()
        # no se agregan REVERSAL nuevos (o el estado sigue coherente): la cuota sigue PENDIENTE
        q1 = min(db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all(), key=lambda q: q.numero_cuota)
        assert q1.estado == "PENDIENTE"
    assert n_reversal_2 == n_reversal_1, "la reversa no es idempotente: duplicó REVERSAL"


# ─────────────────────────────────────────────────────────────────────────────
# 4) REFINANCIACIÓN: simulación (preview) == contrato PERSISTIDO; viejo REFINANCIADO
#    Esto valida lo que el panel flotante le muestra al usuario antes de confirmar.
# ─────────────────────────────────────────────────────────────────────────────
def test_refinanciacion_simulacion_igual_a_persistido(client):
    from app import models_productos as mp
    h = _auth(client)
    cid = _originar(client, h, "DEEP-REFI", 1_200_000, 24)
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})

    # estado del contrato para armar el preview igual que el frontend
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    saldo = det["saldo_capital"]
    snap = det["snapshot"] or {}
    nueva_tasa, nuevo_plazo = 40.0, 18

    # SIMULACIÓN: lo que ve el usuario en el panel flotante (mismos params que refinanciar)
    sim = client.post("/api/creditos/productos/preview", headers=h, json={
        "sistema": det["sistema"], "monto": saldo, "plazo": nuevo_plazo, "tna": nueva_tasa,
        "cargoOtorg": 0, "frecuencia": snap.get("frecuencia", "MENSUAL"),
        "impuestos": snap.get("impuestos", [])}).json()
    sim_rows = sim["rows"]
    sim_total_interes = sim["resumen"]["totalInteres"]
    sim_total_capital = round(sum(r["capital"] for r in sim_rows), 2)

    # CONFIRMAR refinanciación
    r = client.post(f"/api/creditos/contratos/{cid}/refinanciar", headers=h,
                    json={"tasa": nueva_tasa, "plazo": nuevo_plazo})
    assert r.status_code == 200, r.text
    nuevo_id = r.json()["nuevo"]["id"]

    with _db() as db:
        viejo = db.get(mp.PPContrato, cid)
        nuevo = db.get(mp.PPContrato, nuevo_id)
        # viejo cerrado como REFINANCIADO y con actividad RENEGOTIATION persistida
        assert viejo.estado == "REFINANCIADO"
        assert db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="RENEGOTIATION").count() == 1
        assert (viejo.datos_adicionales or {}).get("refinanciado_en") == nuevo.numero_contrato
        # nuevo persistido sobre el saldo, con su cronograma y su DISBURSEMENT
        assert nuevo.estado == "ACTIVO"
        assert abs(Decimal(str(nuevo.monto_original)) - Decimal(str(saldo))) < Decimal("0.5")
        assert nuevo.plazo == nuevo_plazo
        assert (nuevo.datos_adicionales or {}).get("refinancia_de") == viejo.numero_contrato
        assert db.query(mp.PPActividad).filter_by(contrato_id=nuevo_id, tipo="DISBURSEMENT").count() == 1

        cuotas = sorted(db.query(mp.PPCuotaContrato).filter_by(contrato_id=nuevo_id).all(),
                        key=lambda q: q.numero_cuota)
        # COHERENCIA: las cuotas persistidas == la simulación mostrada (cuota a cuota)
        assert len(cuotas) == len(sim_rows) == nuevo_plazo
        for q, sr in zip(cuotas, sim_rows):
            assert abs(Decimal(str(q.capital)) - Decimal(str(sr["capital"]))) < Decimal("0.01")
            assert abs(Decimal(str(q.interes)) - Decimal(str(sr["interes"]))) < Decimal("0.01")
            assert abs(Decimal(str(q.total)) - Decimal(str(sr["total"]))) < Decimal("0.01")
        # totales persistidos == KPIs de la simulación (capital + interés que se muestran)
        cap_persistido = round(float(sum(Decimal(str(q.capital)) for q in cuotas)), 2)
        int_persistido = round(float(sum(Decimal(str(q.interes)) for q in cuotas)), 2)
        assert abs(cap_persistido - sim_total_capital) < 0.5
        assert abs(int_persistido - sim_total_interes) < 0.5
        _balancea(db, nuevo.numero_contrato)


# ─────────────────────────────────────────────────────────────────────────────
# 5) SITUACIÓN DEL CLIENTE: el endpoint refleja EXACTAMENTE lo persistido en DB
# ─────────────────────────────────────────────────────────────────────────────
def test_situacion_cliente_refleja_la_db(client):
    from app import models_productos as mp
    h = _auth(client)
    # dos contratos del mismo cliente + uno de otro (para probar el filtro)
    marca = "DEEPSIT-XYZ"
    cid1 = _originar(client, h, marca, 1_000_000, 12)
    cid2 = _originar(client, h, marca, 2_000_000, 24)
    _originar(client, h, "OTRO-CLIENTE-Q", 500_000, 6)
    client.post(f"/api/creditos/contratos/{cid1}/actividad", headers=h, json={"tipo": "PAYMENT"})

    resp = client.get(f"/api/creditos/contratos/situacion?q={marca}", headers=h).json()
    items = {x["numero"]: x for x in resp["items"]}

    with _db() as db:
        # el filtro por nombre trae exactamente los 2 del cliente
        numeros_db = {c.numero_contrato for c in
                      db.query(mp.PPContrato).filter(mp.PPContrato.cliente_nombre == marca).all()}
        assert set(items.keys()) == numeros_db, "el filtro por nombre no coincide con la DB"

        # por contrato: saldo, cuotas pagadas/pendientes y estado == DB
        tot_colocado = Decimal("0")
        tot_saldo = Decimal("0")
        for c in db.query(mp.PPContrato).filter(mp.PPContrato.cliente_nombre == marca).all():
            it = items[c.numero_contrato]
            assert abs(Decimal(str(it["saldo"])) - Decimal(str(c.saldo_capital))) < Decimal("0.01")
            assert it["estado"] == c.estado
            cuotas = db.query(mp.PPCuotaContrato).filter_by(contrato_id=c.id).all()
            pag = sum(1 for q in cuotas if q.estado == "PAGADA")
            pen = sum(1 for q in cuotas if q.estado == "PENDIENTE")
            assert it["cuotasPagadas"] == pag and it["cuotasPendientes"] == pen
            tot_colocado += Decimal(str(c.monto_original))
            if c.estado == "ACTIVO":
                tot_saldo += Decimal(str(c.saldo_capital))
        # resumen consolidado == agregación real de la DB
        assert abs(Decimal(str(resp["resumen"]["capitalColocado"])) - tot_colocado) < Decimal("0.01")
        assert abs(Decimal(str(resp["resumen"]["saldoVigente"])) - tot_saldo) < Decimal("0.01")
        assert resp["resumen"]["saldoVigente"] <= resp["resumen"]["capitalColocado"] + 0.01


# ─────────────────────────────────────────────────────────────────────────────
# 6) RECOMPUTE DETERMINISTA: releer el contrato da el mismo estado (sin drift)
# ─────────────────────────────────────────────────────────────────────────────
def test_recompute_determinista_sin_drift(client):
    h = _auth(client)
    cid = _originar(client, h, "DEEP-DRIFT", 1_000_000, 12)
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h,
                json={"tipo": "PARTIAL_PREPAYMENT", "importe": 100000, "modo": "BAJA_CUOTA"})

    a = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    b = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    assert a["saldo_capital"] == b["saldo_capital"]
    assert [round(q["total"], 2) for q in a["cuotas"]] == [round(q["total"], 2) for q in b["cuotas"]]
    assert [q["estado"] for q in a["cuotas"]] == [q["estado"] for q in b["cuotas"]]


# ─────────────────────────────────────────────────────────────────────────────
# END-TO-END: de la CREACIÓN de la línea al CIERRE del préstamo, verificando
# la persistencia en la base en cada hito del ciclo de vida.
# ─────────────────────────────────────────────────────────────────────────────
def _crear_linea_publicada(client, hcred, hadmin, sistema, nombre, tna=48):
    """Crea una línea nueva, la configura y la publica (cuatro-ojos). Devuelve su id."""
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": nombre}).json()
    pid = p["id"]
    r = client.put(f"/api/creditos/productos/{pid}/config", headers=hcred,
                   json={**p["cfg"], "sistema": sistema, "tna": tna, "montoMin": 100000,
                         "montoMax": 5000000, "plazoMin": 6, "plazoMax": 60})
    assert r.status_code == 200, r.text
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    pub = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    assert pub.status_code == 200 and pub.json()["estado"] == "PUBLICADO", pub.text
    return pid


@pytest.mark.parametrize("sistema", ["FRANCES", "ALEMAN", "AMERICANO", "BULLET"])
def test_e2e_linea_a_cierre_con_persistencia(client, sistema):
    """FLUJO COMPLETO por sistema, con asserts sobre la DB en cada paso:
    crear línea → publicar → solicitud → aprobar → originar (desde solicitud) →
    desembolsar → cobrar todas las cuotas → CERRADO. Verifica pp_producto_version,
    pp_solicitud, pp_contrato, pp_cuota_contrato, pp_actividad y asientos.
    """
    from app import models_productos as mp
    hcred = _auth(client, "creditos", "cred123")
    hadmin = _auth(client)

    # ── 1) Línea publicada ──
    pid = _crear_linea_publicada(client, hcred, hadmin, sistema, f"E2E {sistema}")
    with _db() as db:
        vers = db.query(mp.PPVersion).filter_by(producto_id=pid).all()
        assert any(v.estado == "PUBLICADO" for v in vers), "no quedó una versión PUBLICADA en DB"

    # ── 2) Solicitud registrada → enviar → aprobar (cuatro-ojos) ──
    cliente_id = client.get("/api/creditos/clientes", headers=hcred).json()["items"][0]["id"]
    sol = client.post("/api/creditos/solicitudes", headers=hcred, json={
        "producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": 12,
        "solicitante_tipo": "REGISTRADO", "cliente_id": cliente_id}).json()
    sid = sol["id"]
    assert sol["evaluacion"]["elegible"] is True
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "enviar"})
    ap = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert ap.status_code == 200 and ap.json()["estado"] == "APROBADA"
    with _db() as db:
        s = db.get(mp.PPSolicitud, sid)
        assert s.estado == "APROBADA"

    # ── 3) Originar desde la solicitud (sin desembolsar) → A_LIQUIDAR ──
    c = client.post("/api/creditos/contratos/originar", headers=hadmin, json={
        "producto_id": pid, "cliente_nombre": "E2E-CLIENTE", "monto": 1_000_000, "plazo": 12,
        "solicitud_pp_id": sid, "desembolsar": False}).json()
    cid = c["id"]
    with _db() as db:
        ct = db.get(mp.PPContrato, cid)
        assert ct.estado == "A_LIQUIDAR"
        cuotas = db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all()
        assert len(cuotas) == 12
        assert abs(sum(Decimal(str(q.capital)) for q in cuotas) - Decimal("1000000")) < Decimal("0.5")
        # la solicitud quedó ORIGINADA y ligada al contrato
        s = db.get(mp.PPSolicitud, sid)
        assert s.estado == "ORIGINADA"
        assert (s.contrato_id == cid) or (str(cid) in str(s.contrato_id))
        # todavía no hay asiento (no se desembolsó)
        assert not _asientos_de(db, ct.numero_contrato)

    # ── 4) Desembolsar → ACTIVO + asiento ──
    d = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=hadmin).json()
    assert d["estado"] == "ACTIVO"
    with _db() as db:
        ct = db.get(mp.PPContrato, cid)
        assert ct.estado == "ACTIVO"
        assert db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="DISBURSEMENT").count() == 1
        assert _asientos_de(db, ct.numero_contrato)
        _balancea(db, ct.numero_contrato)

    # ── 5) Cobrar todas las cuotas → CERRADO ──
    for _ in range(30):
        det = client.get(f"/api/creditos/contratos/{cid}", headers=hadmin).json()
        if det["estado"] == "CERRADO":
            break
        client.post(f"/api/creditos/contratos/{cid}/actividad", headers=hadmin, json={"tipo": "PAYMENT"})

    # ── 6) Estado final PERSISTIDO: CERRADO, saldo 0, todas las cuotas PAGADA, asientos OK ──
    with _db() as db:
        ct = db.get(mp.PPContrato, cid)
        assert ct.estado == "CERRADO", f"{sistema}: no cerró (quedó {ct.estado})"
        assert abs(Decimal(str(ct.saldo_capital))) < Decimal("0.01")
        cuotas = db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all()
        assert all(q.estado == "PAGADA" for q in cuotas), f"{sistema}: quedaron cuotas sin pagar"
        # hay al menos un PAYMENT persistido y ninguna actividad quedó colgada
        assert db.query(mp.PPActividad).filter_by(contrato_id=cid, tipo="PAYMENT").count() >= 1
        _balancea(db, ct.numero_contrato)


def test_crear_linea_no_colisiona_codigo(client):
    """Regresión del bug 'Crear y diseñar → Error 500' en Configurar Créditos:
    el código LP-NUEVA-NN se generaba con count(productos)+1 y colisionaba con la constraint
    única cuando ya existía ese sufijo. Sembramos justo el código que la vieja lógica elegiría
    y verificamos que crear NO rompa (y que dos creaciones den códigos distintos)."""
    from app import models_productos as mp
    hcred = _auth(client, "creditos", "cred123")
    with _db() as db:
        c = db.query(mp.PPProducto).count()
        fam = db.query(mp.PPFamilia).first()
        db.add(mp.PPProducto(familia_id=fam.id, codigo=f"LP-NUEVA-{c + 1:02d}", nombre="colisión-seed"))
        db.commit()
    r1 = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "QA sin colisión 1"})
    assert r1.status_code in (200, 201), r1.text        # antes: 500 UniqueViolation
    r2 = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "QA sin colisión 2"})
    assert r2.status_code in (200, 201), r2.text
    with _db() as db:
        cods = [p.codigo for p in db.query(mp.PPProducto)
                .filter(mp.PPProducto.nombre.like("QA sin colisión%")).all()]
        assert len(cods) == 2 and len(set(cods)) == 2, f"códigos duplicados: {cods}"


def test_numbering_reintenta_ante_colision_concurrente(client):
    """Concurrencia multi-usuario: si entre el cálculo del 'primer libre' y el INSERT otro request
    ya tomó ese número, la constraint única lo rechaza y crear_con_numero_unico debe REINTENTAR con
    un número fresco (no explotar con 500). Simulamos la carrera: el 1er número colisiona, el 2º libre."""
    from app.core.numbering import crear_con_numero_unico
    from app import models_productos as mp
    with _db() as db:                                   # otro usuario ya ocupó LP-RACE-01
        fam = db.query(mp.PPFamilia).first()
        db.add(mp.PPProducto(familia_id=fam.id, codigo="LP-RACE-01", nombre="ocupado-por-otro"))
        db.commit()
    with _db() as db:
        fam = db.query(mp.PPFamilia).first()
        seq = iter(["LP-RACE-01", "LP-RACE-02"])        # 1º choca, 2º libre
        def _build(cod):
            p = mp.PPProducto(familia_id=fam.id, codigo=cod, nombre="via-helper"); db.add(p); return p
        obj = crear_con_numero_unico(db, lambda: next(seq), _build)
        db.commit()
        assert obj.codigo == "LP-RACE-02"               # reintentó y usó el libre
        # y la transacción externa quedó sana (no PendingRollback): otra escritura funciona
        db.add(mp.PPProducto(familia_id=fam.id, codigo="LP-RACE-99", nombre="post-retry")); db.commit()
        assert db.query(mp.PPProducto).filter_by(codigo="LP-RACE-99").first() is not None


def test_originar_no_colisiona_numero_contrato(client):
    """Regresión (hermano de H-097): numero_contrato salía de count()+1 y, al borrarse un contrato,
    el siguiente reusaba un número existente → 500 por constraint única. Forzamos el hueco."""
    from app import models_productos as mp
    h = _auth(client)
    ids = [_originar(client, h, f"NUMCOL-{i}", 500_000, 6) for i in range(3)]
    with _db() as db:                                   # borrar el del medio → hueco en la numeración
        db.delete(db.get(mp.PPContrato, ids[1])); db.commit()
    r = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": _pers(client, h)["id"], "cliente_nombre": "NUMCOL-NUEVO",
        "monto": 500_000, "plazo": 6, "desembolsar": True})
    assert r.status_code in (200, 201), r.text          # antes: 500 UniqueViolation
    with _db() as db:
        nums = [c.numero_contrato for c in db.query(mp.PPContrato).all()]
        assert len(nums) == len(set(nums)), f"numero_contrato duplicado: {nums}"


def test_solicitud_no_colisiona_numero(client):
    """Regresión (hermano de H-097): el numero de solicitud (SOL-AAAA-NNNNN, único) salía de count()+1
    y colisionaba al borrar. Forzamos el hueco."""
    from app import models_productos as mp
    hcred = _auth(client, "creditos", "cred123")
    pid = _crear_linea_publicada(client, hcred, _auth(client), "FRANCES", "Línea sol-numcol")
    cid = _cliente_id(client, hcred)
    def crear():
        return client.post("/api/creditos/solicitudes", headers=hcred, json={
            "producto_id": pid, "monto_solicitado": 800_000, "plazo_solicitado": 12,
            "solicitante_tipo": "REGISTRADO", "cliente_id": cid})
    ids = [crear().json()["id"] for _ in range(3)]
    with _db() as db:
        db.delete(db.get(mp.PPSolicitud, ids[1])); db.commit()
    r = crear()
    assert r.status_code in (200, 201), r.text          # antes: 500 UniqueViolation
    with _db() as db:
        nums = [s.numero for s in db.query(mp.PPSolicitud).all()]
        assert len(nums) == len(set(nums)), f"numero de solicitud duplicado: {nums}"


def test_idempotency_key_no_duplica_altas(client):
    """Idempotency-Key: dos requests con la misma clave devuelven el MISMO resultado y crean UN solo
    registro; con clave distinta se crea otro; sin clave, cada request crea uno. Cubre solicitud y
    la actividad de servicing (pago) — el caso más sensible (no pagar dos veces)."""
    from app import models_productos as mp
    h = _auth(client)

    # --- Alta de solicitud ---
    pid = _pers(client, h)["id"]
    cid = _cliente_id(client, h)
    body = {"producto_id": pid, "monto_solicitado": 700_000, "plazo_solicitado": 12,
            "solicitante_tipo": "REGISTRADO", "cliente_id": cid}
    r1 = client.post("/api/creditos/solicitudes", headers={**h, "Idempotency-Key": "K-SOL-1"}, json=body).json()
    r2 = client.post("/api/creditos/solicitudes", headers={**h, "Idempotency-Key": "K-SOL-1"}, json=body).json()
    assert r1["id"] == r2["id"] and r1["numero"] == r2["numero"]     # replay: mismo registro
    r3 = client.post("/api/creditos/solicitudes", headers={**h, "Idempotency-Key": "K-SOL-2"}, json=body).json()
    assert r3["id"] != r1["id"]                                       # clave distinta: otro registro
    with _db() as db:
        assert db.query(mp.PPIdempotencia).filter_by(clave="K-SOL-1").count() == 1

    # --- Servicing: pagar la misma cuota con la misma clave no cobra dos veces ---
    contrato = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pid, "cliente_nombre": "IDEMPAGO", "monto": 1_000_000, "plazo": 12}).json()
    ccid = contrato["id"]
    p1 = client.post(f"/api/creditos/contratos/{ccid}/actividad", headers={**h, "Idempotency-Key": "K-PAY-1"},
                     json={"tipo": "PAYMENT"}).json()
    p2 = client.post(f"/api/creditos/contratos/{ccid}/actividad", headers={**h, "Idempotency-Key": "K-PAY-1"},
                     json={"tipo": "PAYMENT"}).json()
    # mismo saldo tras el replay (no se aplicó un segundo pago) y una sola actividad PAYMENT
    assert p1["saldo_capital"] == p2["saldo_capital"]
    with _db() as db:
        pays = db.query(mp.PPActividad).filter_by(contrato_id=ccid, tipo="PAYMENT", estado="EJECUTADA").count()
        assert pays == 1, f"el pago se registró {pays} veces (idempotencia rota)"


def test_gate_desembolso_pendiente_y_aprobacion(client):
    """Fase 2b: con el workflow DESEMBOLSO activo, desembolsar NO ejecuta: queda pendiente de
    aprobación (aparece en el inbox del aprobador). Al aprobarlo, se ejecuta el desembolso (ACTIVO)."""
    # aprobador de Portezuelo (permiso aprobaciones:aprobar), distinto del emisor admin
    hcred = _gw("aprobador", "creditos:read", "aprobaciones:aprobar")
    hadmin = _auth(client)
    # activar la regla DESEMBOLSO en Configuraciones; su nivel 1 exige el rol APROBAR con cuatro-ojos
    _activar_wf("DESEMBOLSO")

    # admin origina un contrato SIN desembolsar, y pide el desembolso → queda PENDIENTE
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=hadmin).json()["items"] if p["codigo"] == "LP-PERS-01")
    cid = client.post("/api/creditos/contratos/originar", headers=hadmin, json={
        "producto_id": pers["id"], "cliente_nombre": "GATE-DESEMB", "monto": 800_000, "plazo": 12, "desembolsar": False}).json()["id"]
    r = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=hadmin).json()
    assert r.get("pendiente") is True, r
    pid = r["pendienteId"]
    assert client.get(f"/api/creditos/contratos/{cid}", headers=hadmin).json()["estado"] == "A_LIQUIDAR"  # no ejecutó

    # aparece en el inbox del aprobador del nivel, no en el de admin (emisor)
    assert any(t["id"] == pid for t in client.get("/api/creditos/aprobaciones/inbox", headers=hcred).json()["items"])
    assert all(t["id"] != pid for t in client.get("/api/creditos/aprobaciones/inbox", headers=hadmin).json()["items"])

    # el aprobador aprueba → se ejecuta el desembolso
    ap = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/aprobar", headers=hcred).json()
    assert ap["aprobado"] and ap["ejecutado"]
    assert client.get(f"/api/creditos/contratos/{cid}", headers=hadmin).json()["estado"] == "ACTIVO"


def test_workflow_cadena_n_niveles(client):
    """Fase 2: con 2 niveles en serie, una línea EN_REVISION necesita DOS aprobaciones distintas.
    La primera aprobación NO publica (sigue EN_REVISION); recién la segunda pasa a APROBADO."""
    _activar_wf("LINEA")
    hcred = _gw("revisor", "creditos:read", "aprobaciones:aprobar")   # sólo el rol APROBAR
    hadmin = _auth(client)                                             # tiene APROBAR y SUPERVISAR
    # configurar LINEA con 2 niveles: nivel 1 rol APROBAR (lo aprueba el revisor), nivel 2 rol SUPERVISAR
    # sin cuatro-ojos (lo cierra admin aunque sea el emisor; en prod sería otro gerente).
    from tests.config_falsa import CONFIG
    CONFIG.editar_nivel("LINEA", 1, nombre="Revisión")
    CONFIG.agregar_nivel("LINEA", "Gerencia", rol="SUPERVISAR", cuatro_ojos=False)

    # admin diseña y envía a revisión
    p = client.post("/api/creditos/productos", headers=hadmin, json={"nombre": "Cadena 2 niveles"}).json()
    pid = p["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hadmin,
               json={**p["cfg"], "sistema": "FRANCES", "tna": 40, "montoMin": 100000, "montoMax": 2000000, "plazoMin": 6, "plazoMax": 36})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "revisar"})

    # 1ª aprobación (revisor, nivel 1) → NO cierra, sigue EN_REVISION
    r1 = client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "aprobar"})
    assert r1.status_code == 200 and r1.json()["estado"] == "EN_REVISION", r1.text
    # el revisor no puede aprobar el nivel 2 (rol SUPERVISAR) → 403
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "aprobar"}).status_code == 403
    # 2ª aprobación (admin, nivel 2) → ahora sí APROBADO
    r2 = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert r2.status_code == 200 and r2.json()["estado"] == "APROBADO", r2.text


def test_workflow_quien_aprueba_via_permisos(client):
    """H-150/H-205: quién aprueba se define con los permisos de aprobación de Portezuelo. Sin el permiso,
    'creditos' no puede aprobar (403); cuando Seguridad de Portezuelo se lo asigna, el mismo usuario sí
    puede. La configuración del workflow ya no está en Créditos (vive en Configuraciones)."""
    _activar_wf("LINEA")
    hcred = _gw("creditos", "creditos:read", "creditos:write")
    hadmin = _auth(client)
    # admin crea + configura + envía a revisión (así 'creditos' no es el emisor y no lo frena el cuatro-ojos)
    p = client.post("/api/creditos/productos", headers=hadmin, json={"nombre": "WF-cfg"}).json()
    pid = p["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hadmin,
               json={**p["cfg"], "sistema": "FRANCES", "tna": 40, "montoMin": 100000, "montoMax": 2000000, "plazoMin": 6, "plazoMax": 36})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "revisar"})
    # sin permiso de aprobación: creditos NO puede aprobar → 403
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "aprobar"}).status_code == 403
    # el workflow ya no se configura desde Créditos
    assert client.put("/api/creditos/workflow/LINEA", headers=hcred, json={"activo": False}).status_code == 404
    # Seguridad de Portezuelo le asigna el permiso de aprobación → el mismo usuario SÍ puede aprobar
    hcred = _gw("creditos", "creditos:read", "creditos:write", "aprobaciones:aprobar")
    ap = client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "aprobar"})
    assert ap.status_code == 200 and ap.json()["estado"] == "APROBADO" and ap.json()["aprobadoPor"] == "creditos"


def _linea_en_revision(client, hadmin, nombre):
    p = client.post("/api/creditos/productos", headers=hadmin, json={"nombre": nombre}).json()
    client.put(f"/api/creditos/productos/{p['id']}/config", headers=hadmin,
               json={**p["cfg"], "sistema": "FRANCES", "tna": 40, "montoMin": 100000, "montoMax": 2000000, "plazoMin": 6, "plazoMax": 36})
    client.post(f"/api/creditos/productos/{p['id']}/estado", headers=hadmin, json={"accion": "revisar"})
    return p["id"]


def test_workflow_override_excluir_saca_la_aprobacion_aunque_tenga_el_rol(client):
    """Los overrides del nivel se configuran en Configuraciones y el motor los aplica (antes se guardaban
    pero el evaluador los ignoraba): EXCLUIR le saca la aprobación a quien tiene el rol."""
    from tests.config_falsa import CONFIG
    _activar_wf("LINEA")
    CONFIG.override("LINEA", 1, "pz.excluido", "EXCLUIR")
    hadmin = _auth(client)
    pid = _linea_en_revision(client, hadmin, "WF-excluir")
    excluido = _gw("pz.excluido", "creditos:read", "aprobaciones:aprobar")
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=excluido, json={"accion": "aprobar"})
    assert r.status_code == 403 and "excluido" in r.json()["detail"]
    # tampoco la ve en su bandeja
    assert all(t["id"] != pid for t in client.get("/api/creditos/aprobaciones/inbox", headers=excluido).json()["items"])
    otro = _gw("pz.otro", "creditos:read", "aprobaciones:aprobar")
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=otro, json={"accion": "aprobar"}).json()["estado"] == "APROBADO"


def test_workflow_override_incluir_habilita_sin_el_rol(client):
    """INCLUIR habilita a aprobar ese nivel a alguien que no tiene el rol (p.ej. un gerente puntual)."""
    from tests.config_falsa import CONFIG
    _activar_wf("LINEA")
    CONFIG.override("LINEA", 1, "pz.gerente", "INCLUIR")
    hadmin = _auth(client)
    pid = _linea_en_revision(client, hadmin, "WF-incluir")
    sin_rol = _gw("pz.sinrol", "creditos:read", "creditos:write")
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=sin_rol, json={"accion": "aprobar"}).status_code == 403
    gerente = _gw("pz.gerente", "creditos:read")
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=gerente, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADO", r.text


def test_sin_configuraciones_no_se_aprueba_ni_se_simula(client):
    """Falla cerrado: si Configuraciones no responde y no hay copia, 503 (no se inventa una regla que
    saltee el cuatro-ojos ni un cronograma sin feriados)."""
    from tests.config_falsa import CONFIG
    _activar_wf("LINEA")
    hadmin = _auth(client)
    pid = _linea_en_revision(client, hadmin, "WF-caido")
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=hadmin).json()["items"] if p["codigo"] == "LP-PERS-01")
    CONFIG.caida = True
    CONFIG._cambio()   # sin copia en caché
    aprobador = _gw("pz.aprobador", "creditos:read", "aprobaciones:aprobar")
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=aprobador, json={"accion": "aprobar"})
    assert r.status_code == 503 and "Configuraciones" in r.json()["detail"]
    assert client.get("/api/creditos/contratos/oferta", headers=hadmin).status_code == 503
    r = client.post(f"/api/creditos/productos/{pers['id']}/simular-preview", headers=hadmin, json={"monto": 500000, "plazo": 12})
    assert r.status_code == 503


def test_con_configuraciones_caido_se_usa_la_copia_reciente(client):
    """Un corte breve no frena la operación: si hay copia reciente de la regla, se sigue con ella."""
    from tests.config_falsa import CONFIG
    _activar_wf("LINEA")
    hadmin = _auth(client)
    pid = _linea_en_revision(client, hadmin, "WF-copia")
    client.get("/api/creditos/aprobaciones/inbox", headers=hadmin)   # lee y cachea las reglas
    CONFIG.caida = True
    aprobador = _gw("pz.aprobador", "creditos:read", "aprobaciones:aprobar")
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=aprobador, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADO", r.text


def test_guardar_config_rechaza_invalidos(client):
    """QA Configurar Créditos (H-099): guardar config con contradicciones/negativos debe dar 422,
    no 200. Antes se persistía cualquier disparate (min>max, TNA negativa) y sólo se detectaba
    —parcialmente— al publicar."""
    hcred = _auth(client, "creditos", "cred123")
    pid = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "QA cfg check"}).json()["id"]
    cfg = client.get(f"/api/creditos/productos/{pid}", headers=hcred).json()["cfg"]
    base = {**cfg, "sistema": "FRANCES", "montoMin": 100000, "montoMax": 2000000, "plazoMin": 6, "plazoMax": 36}
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**base, "tna": 45}).status_code == 200
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=hcred,
                      json={**base, "tna": 45, "montoMin": 5_000_000, "montoMax": 100000}).status_code == 422
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**base, "tna": -10}).status_code == 422
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=hcred,
                      json={**base, "tna": 45, "plazoMin": 40, "plazoMax": 12}).status_code == 422


def test_borrar_linea_con_referencias_da_409(client):
    """QA Configurar Créditos (H-099): borrar una línea que es padre de otra devolvía un 500 crudo
    (FK). Ahora devuelve 409 con mensaje claro; tras quitar la referencia sí se puede borrar."""
    hcred = _auth(client, "creditos", "cred123")
    padre = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "QA padre ref"}).json()
    hijo = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "QA hijo ref", "padre_id": padre["id"]}).json()
    r = client.delete(f"/api/creditos/productos/{padre['id']}", headers=hcred)
    assert r.status_code == 409, r.text                     # antes: 500 IntegrityError
    assert client.delete(f"/api/creditos/productos/{hijo['id']}", headers=hcred).status_code == 200
    assert client.delete(f"/api/creditos/productos/{padre['id']}", headers=hcred).status_code == 200


def test_inbox_aprobaciones_cuatro_ojos(client):
    """El Inbox de aprobaciones muestra lo que espera MI aprobación e informa quién lo pidió, y NO
    muestra lo que yo mismo envié a revisión (separación de funciones)."""
    _activar_wf("LINEA")
    hcred = _auth(client, "creditos", "cred123")
    hadmin = _auth(client)                              # ADMG: aprobador
    # creditos crea una línea y la envía a revisión
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Inbox línea QA"}).json()
    pid = p["id"]
    cfg = client.get(f"/api/creditos/productos/{pid}", headers=hcred).json()["cfg"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred,
               json={**cfg, "sistema": "FRANCES", "tna": 40, "montoMin": 100000, "montoMax": 3000000, "plazoMin": 6, "plazoMax": 48})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})

    # el ADMG (que NO la envió) la ve en su inbox, con el solicitante
    box_admin = client.get("/api/creditos/aprobaciones/inbox", headers=hadmin).json()
    mia = [t for t in box_admin["items"] if t["id"] == pid]
    assert mia, "la versión EN_REVISION no aparece en el inbox del aprobador"
    assert mia[0]["solicitante"] == "creditos" and mia[0]["accion"] == "aprobar"
    # la ruta es la del módulo dentro del frontend de Portezuelo (la SPA propia /creditos/ se retiró)
    assert mia[0]["tipo"] == "LINEA" and mia[0]["ruta"] == "/modules/creditos/configurar"

    # cuatro-ojos estricto: el ADMG crea OTRA línea y la envía él mismo → NO debe verla en su inbox
    p2 = client.post("/api/creditos/productos", headers=hadmin, json={"nombre": "Inbox línea propia ADMG"}).json()
    cfg2 = client.get(f"/api/creditos/productos/{p2['id']}", headers=hadmin).json()["cfg"]
    client.put(f"/api/creditos/productos/{p2['id']}/config", headers=hadmin,
               json={**cfg2, "sistema": "FRANCES", "tna": 40, "montoMin": 100000, "montoMax": 3000000, "plazoMin": 6, "plazoMax": 48})
    client.post(f"/api/creditos/productos/{p2['id']}/estado", headers=hadmin, json={"accion": "revisar"})
    box_admin2 = client.get("/api/creditos/aprobaciones/inbox", headers=hadmin).json()
    assert all(t["id"] != p2["id"] for t in box_admin2["items"]), "no debería ver su propia tarea (cuatro-ojos)"
    assert any(t["id"] == pid for t in box_admin2["items"]), "sí debe seguir viendo la ajena"


def test_e2e_con_situaciones_de_pago_hasta_payoff(client):
    """E2E con vida útil rica: desembolso → pago → pago parcial → prepago → diferimiento →
    payoff. Verifica que cada situación se PERSISTA y que el contrato cierre en DB."""
    from app import models_productos as mp
    h = _auth(client)
    cid = _originar(client, h, "E2E-SITUACIONES", 1_200_000, 24)

    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    det = client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    prox_total = next(q["total"] for q in det["cuotas"] if q["estado"] == "PENDIENTE")
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h,
                json={"tipo": "PAYMENT", "importe": round(prox_total / 2, 2)})   # parcial
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h,
                json={"tipo": "PARTIAL_PREPAYMENT", "importe": 150000, "modo": "BAJA_PLAZO"})
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h,
                json={"tipo": "PAYMENT_HOLIDAY", "importe": 2})                  # diferir 2

    with _db() as db:
        tipos = {a.tipo for a in db.query(mp.PPActividad).filter_by(contrato_id=cid)
                 .filter(mp.PPActividad.estado == "EJECUTADA").all()}
        assert {"PAYMENT", "PARTIAL_PREPAYMENT", "PAYMENT_HOLIDAY"} <= tipos, \
            f"faltó persistir alguna situación: {tipos}"

    fin = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYOFF"}).json()
    assert fin["estado"] == "CERRADO"
    with _db() as db:
        ct = db.get(mp.PPContrato, cid)
        assert ct.estado == "CERRADO" and abs(Decimal(str(ct.saldo_capital))) < Decimal("0.01")
        assert all(q.estado == "PAGADA" for q in db.query(mp.PPCuotaContrato).filter_by(contrato_id=cid).all())
        _balancea(db, ct.numero_contrato)
