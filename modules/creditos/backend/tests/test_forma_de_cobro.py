"""Forma de cobro de la línea (componente COLLECTION): con código de descuento, la solicitud le avisa al
solicitante cómo le va a venir la cuota detallada en el recibo de sueldo."""
import pytest
from fastapi.testclient import TestClient

from app import models_productos as m
from app.api.productos import _version_publicada_vigente
from app.core.database import SessionLocal
from app.services import cobro
from tests.test_portal import _enviar, _ingresar, _un_producto

DESCUENTO = {"modalidad": "CODIGO_DESCUENTO", "codigoDescuento": "4521",
             "conceptoRecibo": "CAPRESCA PREST PERSONAL", "detalle": "Se descuenta desde el mes siguiente."}


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _configurar(producto_id: str, config: dict, activo: bool = True) -> None:
    with SessionLocal() as db:
        v = _version_publicada_vigente(db.get(m.PPProducto, producto_id))
        db.add(m.PPComponente(producto_version_id=v.id, componente_codigo=cobro.COMPONENTE, orden=15,
                              requerido=False, activo=activo, config=config))
        db.commit()


def test_la_configuracion_exige_codigo_y_concepto_con_descuento():
    assert cobro.errores(DESCUENTO) == []
    e = cobro.errores({"modalidad": "CODIGO_DESCUENTO", "codigoDescuento": " ", "conceptoRecibo": ""})
    assert "forma de cobro: falta el código de descuento" in e
    assert "forma de cobro: falta cómo figura en el recibo de sueldo" in e
    assert cobro.errores({"modalidad": "VENTANILLA"}) == []
    assert cobro.errores({"modalidad": "OTRA"}) == ["forma de cobro: elegí la modalidad"]


def test_guardar_la_linea_con_la_forma_de_cobro_incompleta_da_422(client):
    h = _auth(client)
    nueva = client.post("/api/creditos/productos", headers=h, json={"nombre": "LINEA COBRO"}).json()
    comps = [c for c in nueva["componentes"] if c["activo"]]
    comps.append({"codigo": "COLLECTION", "activo": True, "config": {"modalidad": "CODIGO_DESCUENTO"}})
    r = client.put(f"/api/creditos/productos/{nueva['id']}/config", headers=h, json={**nueva["cfg"], "componentes": comps})
    assert r.status_code == 422 and "falta el código de descuento" in r.json()["detail"]
    comps[-1]["config"] = DESCUENTO
    r = client.put(f"/api/creditos/productos/{nueva['id']}/config", headers=h, json={**nueva["cfg"], "componentes": comps})
    assert r.status_code == 200, r.text
    assert r.json()["cobro"]["codigoDescuento"] == "4521"


def test_el_portal_y_la_oferta_dicen_como_se_cobra(client):
    hp = _ingresar(client)
    p = _un_producto(client, hp)
    assert p["cobro"] is None                       # sin el componente, no se avisa nada
    _configurar(p["id"], DESCUENTO)
    p = next(x for x in client.get("/api/creditos/portal/productos", headers=hp).json() if x["id"] == p["id"])
    assert p["cobro"]["codigoDescuento"] == "4521" and p["cobro"]["conceptoRecibo"] == "CAPRESCA PREST PERSONAL"
    of = client.get("/api/creditos/contratos/oferta", headers=_auth(client)).json()["items"]
    assert next(x for x in of if x["id"] == p["id"])["cobro"]["modalidad"] == "CODIGO_DESCUENTO"


def test_la_solicitud_guarda_lo_que_se_le_aviso(client):
    hp = _ingresar(client)
    p = _un_producto(client, hp)
    _configurar(p["id"], DESCUENTO)
    r = _enviar(client, hp, p)
    assert r.status_code in (200, 201), r.text
    h = _auth(client)
    s = next(x for x in client.get("/api/creditos/solicitudes", headers=h).json()["items"] if x["numero"] == r.json()["numero"])
    assert s["datosAdicionales"]["cobro"]["codigoDescuento"] == "4521"
    # Desde el backoffice, igual.
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    b = client.post("/api/creditos/solicitudes", headers=h, json={
        "producto_id": p["id"], "monto_solicitado": 500000, "plazo_solicitado": 12, "canal": "WEB",
        "solicitante_tipo": "REGISTRADO", "cliente_id": cli})
    assert b.status_code == 201, b.text
    assert b.json()["datosAdicionales"]["cobro"]["conceptoRecibo"] == "CAPRESCA PREST PERSONAL"


def test_una_forma_de_cobro_inactiva_no_se_avisa(client):
    hp = _ingresar(client)
    p = _un_producto(client, hp)
    _configurar(p["id"], DESCUENTO, activo=False)
    p = next(x for x in client.get("/api/creditos/portal/productos", headers=hp).json() if x["id"] == p["id"])
    assert p["cobro"] is None
