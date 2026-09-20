"""QA de ciclo de vida completo por variante de préstamo:
crear línea → solicitud → aprobar → originar → desembolsar → cobrar todas las cuotas → finalizar.
Más refinanciación y cancelación anticipada. Verifica invariantes en cada paso.
"""
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


def _cliente_id(client, h):
    return client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]


def _crear_linea_publicada(client, hcred, hadmin, sistema, nombre):
    """Crea una línea con el sistema dado y la publica (cuatro-ojos)."""
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": nombre}).json()
    pid = p["id"]
    r = client.put(f"/api/creditos/productos/{pid}/config", headers=hcred,
                   json={**p["cfg"], "sistema": sistema, "tna": 48, "montoMin": 100000, "montoMax": 5000000,
                         "plazoMin": 6, "plazoMax": 60})
    assert r.status_code == 200, r.text
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    pub = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    assert pub.status_code == 200 and pub.json()["estado"] == "PUBLICADO", pub.text
    return pid


def _asientos_balancean(det):
    for a in det.get("asientos", []):
        debe = sum(l.get("debe", 0) for l in a["lineas"])
        haber = sum(l.get("haber", 0) for l in a["lineas"])
        assert abs(debe - haber) < 0.01, f"asiento desbalanceado: {a['concepto']}"


@pytest.mark.parametrize("sistema", ["FRANCES", "ALEMAN", "AMERICANO", "BULLET"])
def test_ciclo_completo_por_sistema(client, sistema):
    """Ciclo de vida completo de un préstamo, para cada sistema de amortización."""
    hcred = _auth(client, "creditos", "cred123")
    hadmin = _auth(client)
    pid = _crear_linea_publicada(client, hcred, hadmin, sistema, f"Línea {sistema}")

    # --- SOLICITUD (cliente registrado) → enviar → aprobar (cuatro-ojos) ---
    sol = client.post("/api/creditos/solicitudes", headers=hcred, json={
        "producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": 12,
        "solicitante_tipo": "REGISTRADO", "cliente_id": _cliente_id(client, hcred)}).json()
    sid = sol["id"]
    assert sol["evaluacion"]["elegible"] is True
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "enviar"})
    ap = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert ap.status_code == 200 and ap.json()["estado"] == "APROBADA"

    # --- ORIGINAR (otorgar, sin desembolsar) → A_LIQUIDAR ---
    c = client.post("/api/creditos/contratos/originar", headers=hadmin, json={
        "producto_id": pid, "cliente_nombre": "CICLO", "monto": 1_000_000, "plazo": 12,
        "solicitud_pp_id": sid, "desembolsar": False}).json()
    cid = c["id"]
    assert c["estado"] == "A_LIQUIDAR" and len(c["cuotas"]) == 12
    assert abs(sum(q["capital"] for q in c["cuotas"]) - 1_000_000) < 0.5   # Σcapital = monto
    assert c["cuotas"][-1]["saldo_final"] == 0                              # cierra exacto
    assert not c["asientos"]                                               # sin asiento hasta desembolsar
    # la solicitud quedó ORIGINADA
    assert client.get(f"/api/creditos/solicitudes/{sid}", headers=hadmin).json()["estado"] == "ORIGINADA"

    # --- DESEMBOLSAR → ACTIVO ---
    d = client.post(f"/api/creditos/contratos/{cid}/desembolsar", headers=hadmin).json()
    assert d["estado"] == "ACTIVO"
    assert any(a["tipo"] == "DISBURSEMENT" for a in d["actividades"])

    # --- COBRAR todas las cuotas → CERRADO ---
    for _ in range(20):
        det = client.get(f"/api/creditos/contratos/{cid}", headers=hadmin).json()
        if det["estado"] == "CERRADO":
            break
        client.post(f"/api/creditos/contratos/{cid}/actividad", headers=hadmin, json={"tipo": "PAYMENT"})
    det = client.get(f"/api/creditos/contratos/{cid}", headers=hadmin).json()
    assert det["estado"] == "CERRADO"
    assert det["saldo_capital"] == 0
    assert all(q["estado"] == "PAGADA" for q in det["cuotas"])
    _asientos_balancean(det)


def test_ciclo_con_cancelacion_anticipada(client):
    """Otorgar → desembolsar → pagar algunas → cancelación anticipada (payoff) → CERRADO."""
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": "CANCELA", "monto": 1_000_000, "plazo": 24}).json()
    cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYOFF"}).json()
    assert r["estado"] == "CERRADO" and r["saldo_capital"] == 0
    assert all(q["estado"] == "PAGADA" for q in r["cuotas"])
    _asientos_balancean(r)


def test_ciclo_con_refinanciacion(client):
    """Desembolsar → pagar → refinanciar → el nuevo contrato se puede cancelar hasta CERRADO."""
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": "REFICICLO", "monto": 1_000_000, "plazo": 24}).json()
    cid = c["id"]
    client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json={"tipo": "PAYMENT"})
    r = client.post(f"/api/creditos/contratos/{cid}/refinanciar", headers=h, json={"tasa": 40, "plazo": 18}).json()
    nuevo_id = r["nuevo"]["id"]
    assert r["anterior"]["estado"] == "REFINANCIADO"
    # cancelar el nuevo por completo
    pay = client.post(f"/api/creditos/contratos/{nuevo_id}/actividad", headers=h, json={"tipo": "PAYOFF"}).json()
    assert pay["estado"] == "CERRADO" and pay["saldo_capital"] == 0
    _asientos_balancean(pay)




def _invariantes(det):
    """Invariantes de un contrato: asientos balanceados, saldo = Σcapital pendiente, sin negativos."""
    for a in det.get("asientos", []):
        deb = sum(l.get("debe", 0) for l in a["lineas"]); hab = sum(l.get("haber", 0) for l in a["lineas"])
        assert abs(deb - hab) < 0.01, f"asiento desbalanceado: {a['concepto']}"
    if det["estado"] == "ACTIVO":
        pend_cap = sum(q["capital"] for q in det["cuotas"] if q["estado"] == "PENDIENTE")
        assert abs(det["saldo_capital"] - pend_cap) < 0.5, f"saldo {det['saldo_capital']} ≠ Σcapital pendiente {pend_cap}"
    for q in det["cuotas"]:
        assert q["total"] >= -0.01 and q["capital"] >= -0.01, "importe negativo"


def test_operaciones_combinadas_y_reversa(client):
    """QA de punta a punta: pago normal + parcial + mora (backdating) + prepago + diferimiento +
    reversas (idempotencia) + adelanto + payoff, verificando invariantes en cada paso."""
    import datetime
    from app.core.database import SessionLocal
    from app import models_productos as mp
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    cid = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": "MIX", "monto": 1_200_000, "plazo": 24}).json()["id"]

    def D():
        return client.get(f"/api/creditos/contratos/{cid}", headers=h).json()
    def act(**kw):
        r = client.post(f"/api/creditos/contratos/{cid}/actividad", headers=h, json=kw)
        assert r.status_code == 200, r.text
        _invariantes(r.json()); return r.json()

    _invariantes(D())
    act(tipo="PAYMENT")                                              # cuota 1
    t2 = D()["cuotas"][1]["total"]
    act(tipo="PAYMENT", importe=round(t2 / 2, 2))                    # parcial cuota 2
    # backdating: cuota 2 vencida → mora al completar
    with SessionLocal() as db:
        ct = db.get(mp.PPContrato, cid); q2 = next(q for q in ct.cuotas if q.numero_cuota == 2)
        q2.fecha_vencimiento = datetime.date.today() - datetime.timedelta(days=20); db.commit()
    act(tipo="PAYMENT")                                              # completa cuota 2 con mora

    estado_pre_prepago = D()
    d5 = act(tipo="PARTIAL_PREPAYMENT", importe=200000, modo="BAJA_CUOTA")
    assert abs(d5["saldo_capital"] - (estado_pre_prepago["saldo_capital"] - 200000)) < 1

    # diferimiento y su reversa → estado idéntico al de d5
    dif = act(tipo="PAYMENT_HOLIDAY", importe=2)
    assert dif["saldo_capital"] > d5["saldo_capital"]               # capitalizó interés
    act_hol = next(a for a in D()["actividades"] if a["tipo"] == "PAYMENT_HOLIDAY")
    rev = client.post(f"/api/creditos/contratos/{cid}/actividad/{act_hol['id']}/reversar", headers=h).json()
    _invariantes(rev)
    assert abs(rev["saldo_capital"] - d5["saldo_capital"]) < 0.01
    assert [round(q["total"], 2) for q in rev["cuotas"]] == [round(q["total"], 2) for q in d5["cuotas"]]

    # reversa del prepago → cuotas y saldo vuelven a antes del prepago
    act_pre = next(a for a in D()["actividades"] if a["tipo"] == "PARTIAL_PREPAYMENT")
    rev2 = client.post(f"/api/creditos/contratos/{cid}/actividad/{act_pre['id']}/reversar", headers=h).json()
    _invariantes(rev2)
    assert abs(rev2["saldo_capital"] - estado_pre_prepago["saldo_capital"]) < 0.01

    # adelanto de 5 cuotas y payoff final → CERRADO
    act(tipo="PAYMENT", cuotas=5)
    fin = act(tipo="PAYOFF")
    assert fin["estado"] == "CERRADO" and fin["saldo_capital"] == 0
    assert all(q["estado"] == "PAGADA" for q in fin["cuotas"])
