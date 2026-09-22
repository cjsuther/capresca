"""H-216: con el desembolso por Tesorería, liquidar manda la transferencia a Tesorería y el contrato pasa
a ACTIVO recién cuando Tesorería avisa que se acreditó."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models_productos as m
from app.core import tesoreria
from app.core.config import get_settings
from app.core.database import SessionLocal

CBU = "2850590940090418135201"
CLAVE = "clave-tesoreria-test"
AVISO = "/internal/creditos/tesoreria/resultado"


class TesoreriaFalsa:
    def __init__(self):
        self.lotes, self.caida, self.rechazar = [], False, {}

    def __call__(self, referencia, descripcion, pagos, usuario):
        if self.caida:
            raise tesoreria.TesoreriaNoDisponible("connection refused")
        self.lotes.append({"referencia": referencia, "descripcion": descripcion, "pagos": pagos, "usuario": usuario})
        ok = [p for p in pagos if p["referencia_externa"] not in self.rechazar]
        return {"codigo": f"LOT-2026-{len(self.lotes):05d}", "estado": "PENDIENTE_APROBACION",
                "pagos": [{"referencia_externa": p["referencia_externa"], "estado": "PENDIENTE"} for p in ok],
                "rechazados": [{"referencia_externa": r, "motivo": mot} for r, mot in self.rechazar.items()]}


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def teso(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "desembolso_via_tesoreria", True)
    monkeypatch.setattr(s, "tesoreria_internal_api_key", CLAVE)
    falsa = TesoreriaFalsa()
    monkeypatch.setattr(tesoreria, "enviar_lote", falsa)
    return falsa


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _a_liquidar(client, h, nombre="PEREZ JUAN", cbu=CBU, monto=800_000):
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    pers = next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": nombre, "monto": monto, "plazo": 12, "desembolsar": False,
        "datos_adicionales": {"cbu": cbu}}).json()
    assert c["estado"] == "A_LIQUIDAR", c
    return c


def _contrato(client, h, cid):
    return client.get(f"/api/creditos/contratos/{cid}", headers=h).json()


def _desembolsos(cid):
    with SessionLocal() as db:
        return db.query(m.PPActividad).filter_by(contrato_id=cid, tipo="DISBURSEMENT").count()


def _avisar(client, lote, *pagos, clave=CLAVE):
    return client.post(AVISO, headers={"X-Api-Key": clave}, json={
        "lote": lote, "simulado": True,
        "pagos": [{"referencia_externa": cid, "estado": est, "motivo": mot} for cid, est, mot in pagos]})


def test_liquidar_lote_manda_a_tesoreria_y_no_activa(client, teso):
    h = _auth(client)
    a, b = _a_liquidar(client, h, "PEREZ JUAN"), _a_liquidar(client, h, "GOMEZ ANA", monto=500_000)
    hoy = date.today().isoformat()

    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"fecha": hoy}).json()
    assert r["desembolsados"] == [] and sorted(r["enTesoreria"]) == sorted([a["numero_contrato"], b["numero_contrato"]])
    assert r["loteTesoreria"] == "LOT-2026-00001"
    assert len(teso.lotes) == 1
    pago = next(p for p in teso.lotes[0]["pagos"] if p["referencia_externa"] == a["id"])
    assert pago["cbu"] == CBU and pago["monto"] == 800_000 and pago["beneficiario"] == "PEREZ JUAN"
    assert _contrato(client, h, a["id"])["estado"] == "A_LIQUIDAR" and _desembolsos(a["id"]) == 0

    lote = next(l for l in client.get("/api/creditos/contratos/lotes-liquidacion", headers=h).json()["items"] if l["fecha"] == hoy)
    assert lote["enTesoreria"] == 2
    assert {c["desembolso"]["estado"] for c in lote["contratos"]} == {"EN_TESORERIA"}

    # Volver a liquidar no los manda de nuevo.
    r2 = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"fecha": hoy}).json()
    assert len(r2["yaEnTesoreria"]) == 2 and len(teso.lotes) == 1


def test_confirmado_activa_el_contrato_una_sola_vez(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h)
    client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h)

    r = _avisar(client, "LOT-2026-00001", (c["id"], "CONFIRMADO", "")).json()
    assert r["activados"] == [c["numero_contrato"]]
    d = _contrato(client, h, c["id"])
    assert d["estado"] == "ACTIVO" and _desembolsos(c["id"]) == 1

    assert _avisar(client, "LOT-2026-00001", (c["id"], "CONFIRMADO", "")).json()["ignorados"] == [c["numero_contrato"]]
    assert _desembolsos(c["id"]) == 1


def test_el_aviso_exige_la_clave_interna(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h)
    assert _avisar(client, "LOT-X", (c["id"], "CONFIRMADO", ""), clave="otra").status_code == 401
    assert client.post(AVISO, json={"lote": "LOT-X", "pagos": []}).status_code == 401
    assert _contrato(client, h, c["id"])["estado"] == "A_LIQUIDAR"


def test_fallido_queda_observado_y_se_puede_volver_a_mandar(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h)
    client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h)
    # Un aviso de otro lote no toca el contrato.
    assert _avisar(client, "LOT-VIEJO", (c["id"], "FALLIDO", "x")).json()["ignorados"] == [c["numero_contrato"]]

    r = _avisar(client, "LOT-2026-00001", (c["id"], "FALLIDO", "CBU inexistente")).json()
    assert r["observados"] == [c["numero_contrato"]]
    hoy = date.today().isoformat()
    item = next(x for l in client.get("/api/creditos/contratos/lotes-liquidacion", headers=h).json()["items"]
                if l["fecha"] == hoy for x in l["contratos"] if x["id"] == c["id"])
    assert item["desembolso"] == {"estado": "OBSERVADO", "lote": "LOT-2026-00001", "motivo": "CBU inexistente"}
    assert _contrato(client, h, c["id"])["estado"] == "A_LIQUIDAR"

    r = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).json()
    assert r["desembolso"]["estado"] == "EN_TESORERIA" and r["desembolso"]["lote"] == "LOT-2026-00002"
    assert teso.lotes[0]["referencia"] != teso.lotes[1]["referencia"]      # nuevo intento, nuevo lote


def test_desembolsar_de_a_uno_y_no_dos_veces(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h)
    r = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).json()
    assert r["estado"] == "A_LIQUIDAR" and "Tesorería" in r["mensaje"]
    again = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h)
    assert again.status_code == 409 and "LOT-2026-00001" in again.json()["detail"]
    assert len(teso.lotes) == 1


def test_sin_cbu_no_se_manda(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h, cbu="123")
    r = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h)
    assert r.status_code == 422 and "CBU" in r.json()["detail"]
    assert teso.lotes == []


def test_tesoreria_caida_no_cambia_nada(client, teso):
    h = _auth(client)
    c = _a_liquidar(client, h)
    teso.caida = True
    r = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h)
    assert r.status_code == 503 and "A_LIQUIDAR" in r.json()["detail"]
    teso.caida = False
    assert client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).status_code == 200


def test_si_ya_estaba_en_otro_lote_se_registra_ese(client, teso):
    """Un pedido anterior se cortó después de que Tesorería lo cargó: no se duplica, se toma ese lote."""
    h = _auth(client)
    c = _a_liquidar(client, h)
    teso.rechazar = {c["id"]: "Ya está en el lote LOT-2026-00077 (PENDIENTE)."}
    r = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).json()
    assert r["desembolso"]["lote"] == "LOT-2026-00077"


def test_originar_con_desembolso_directo_tambien_pasa_por_tesoreria(client, teso):
    h = _auth(client)
    of = client.get("/api/creditos/contratos/oferta", headers=h).json()
    pers = next(p for p in of["items"] if p["codigo"] == "LP-PERS-01")
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": pers["id"], "cliente_nombre": "DIRECTO", "monto": 300_000, "plazo": 6, "desembolsar": True,
        "datos_adicionales": {"cbu": CBU}}).json()
    assert c["estado"] == "A_LIQUIDAR" and c["desembolso"]["estado"] == "EN_TESORERIA"
    assert _desembolsos(c["id"]) == 0


def test_aprobado_por_workflow_se_manda_a_tesoreria(client, teso):
    from tests.config_falsa import CONFIG
    CONFIG.activar("DESEMBOLSO")
    h = _auth(client)
    aprobador = {"X-User-Id": "950", "X-Username": "aprobador",
                 "X-User-Permissions": "creditos:creditos:read,creditos:aprobaciones:aprobar"}
    c = _a_liquidar(client, h)
    pid = client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).json()["pendienteId"]
    assert teso.lotes == []
    ap = client.post(f"/api/creditos/aprobaciones/pendientes/{pid}/aprobar", headers=aprobador).json()
    assert ap["aprobado"] and ap["ejecutado"], ap
    assert len(teso.lotes) == 1 and _contrato(client, h, c["id"])["estado"] == "A_LIQUIDAR"


def test_sin_el_flag_se_desembolsa_como_siempre(client):
    h = _auth(client)
    c = _a_liquidar(client, h)
    assert client.post(f"/api/creditos/contratos/{c['id']}/desembolsar", headers=h).json()["estado"] == "ACTIVO"
