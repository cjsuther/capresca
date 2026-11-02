"""Rango de edades de la línea (Disponibilidad) al cargar la solicitud, por la plataforma y por el portal,
y el parámetro que decide si las cuotas pueden vencer después de la edad máxima (H-224)."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import models
from app.core.database import SessionLocal
from app.core.personas import edad_de
from tests.test_portal import CONSENT, _ingresar, padron  # noqa: F401  (padron: fixture autouse del portal)


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pers(client, h):
    return next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"]
                if p["codigo"] == "LP-PERS-01")["id"]


def _hace(anios: int) -> date:
    """La fecha de nacimiento de alguien que hoy cumple `anios` (el 29/2 cae al 28)."""
    hoy = date.today()
    try:
        return hoy.replace(year=hoy.year - anios)
    except ValueError:
        return hoy.replace(year=hoy.year - anios, day=28)


def _disponibilidad(client, h, pid, **cambios):
    """LP-PERS-01 tiene 18–65 años; `cambios` pisa lo que haga falta."""
    body = {"activo": True, "segmentos": ["AGENTE_PUBLICO", "DOCENTE", "MUNICIPAL"],
            "canales": ["SUCURSAL", "WEB", "APP"], "edadMin": 18, "edadMax": 65, **cambios}
    r = client.put(f"/api/creditos/productos/{pid}/disponibilidad", headers=h, json=body)
    assert r.status_code == 200, r.text


def _express(client, h, pid, plazo=24, nacimiento=None, **kw):
    body = {"producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": plazo,
            "solicitante_tipo": "NO_REGISTRADO",
            "cliente_datos": {"apellido_nombre": "GOMEZ, JUAN", "cuil": "20111111119", "dni": "11111111"},
            "fecha_nacimiento": nacimiento.isoformat() if nacimiento else None, **kw}
    return client.post("/api/creditos/solicitudes", headers=h, json=body)


def _plazo_max(pid, nacimiento):
    from app.api.productos import _disponibilidad as disp, _version_efectiva, plazo_maximo_por_edad
    from app import models_productos as m
    with SessionLocal() as db:
        v = _version_efectiva(db.get(m.PPProducto, pid))
        return plazo_maximo_por_edad(v, disp(v), nacimiento)


# ------------------------------------------------------------------------------- configuración
def test_la_linea_guarda_si_las_cuotas_pueden_pasar_la_edad_maxima(client):
    h = _auth(client)
    pid = _pers(client, h)
    prod = client.get(f"/api/creditos/productos/{pid}", headers=h).json()
    assert prod["disponibilidad"]["permiteCuotasMasAllaEdadMax"] is True     # por defecto, como hasta hoy
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    prod = client.get(f"/api/creditos/productos/{pid}", headers=h).json()
    assert prod["disponibilidad"]["permiteCuotasMasAllaEdadMax"] is False


# ------------------------------------------------------------------------------- plataforma
def test_fuera_del_rango_de_edades_no_se_carga(client):
    h = _auth(client)
    pid = _pers(client, h)
    r = _express(client, h, pid, nacimiento=_hace(70))
    assert r.status_code == 422 and "Edad máxima 65" in r.json()["detail"], r.text
    r = _express(client, h, pid, nacimiento=_hace(17))
    assert r.status_code == 422 and "Edad mínima 18" in r.json()["detail"], r.text


def test_con_rango_de_edades_la_fecha_de_nacimiento_es_obligatoria(client):
    h = _auth(client)
    pid = _pers(client, h)
    r = _express(client, h, pid)
    assert r.status_code == 422 and "fecha de nacimiento" in r.json()["detail"], r.text


def test_el_cliente_del_padron_usa_su_fecha_de_nacimiento(client):
    h = _auth(client)
    pid = _pers(client, h)
    with SessionLocal() as db:
        db.get(models.Cliente, 2).fecha_nacimiento = _hace(40)
        db.commit()
    r = client.post("/api/creditos/solicitudes", headers=h, json={
        "producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": 24,
        "solicitante_tipo": "REGISTRADO", "cliente_id": 2})
    assert r.status_code == 201, r.text
    assert r.json()["edad"] == 40
    with SessionLocal() as db:
        db.get(models.Cliente, 2).fecha_nacimiento = None
        db.commit()
    r = client.post("/api/creditos/solicitudes", headers=h, json={
        "producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": 24,
        "solicitante_tipo": "REGISTRADO", "cliente_id": 2})
    assert r.status_code == 422 and "fecha de nacimiento" in r.json()["detail"], r.text


def test_si_la_linea_lo_permite_las_cuotas_pasan_la_edad_maxima(client):
    h = _auth(client)
    pid = _pers(client, h)
    r = _express(client, h, pid, plazo=60, nacimiento=_hace(63))      # termina de pagar con 68
    assert r.status_code == 201, r.text


def test_si_la_linea_no_lo_permite_rechaza_y_dice_el_plazo_maximo(client):
    h = _auth(client)
    pid = _pers(client, h)
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    nac = _hace(63)
    maximo = _plazo_max(pid, nac)
    assert 6 <= maximo < 60

    r = _express(client, h, pid, plazo=maximo + 1, nacimiento=nac)
    assert r.status_code == 422, r.text
    assert f"el plazo máximo es de {maximo} cuotas" in r.json()["detail"]
    assert _express(client, h, pid, plazo=maximo, nacimiento=nac).status_code == 201


def test_la_ultima_cuota_puede_vencer_con_la_edad_maxima_cumplida(client):
    """Edad máxima 65: puede terminar de pagar con 65 años, no con 66."""
    from app.api.productos import _disponibilidad as disp, _version_efectiva, _params_cronograma
    from app.services.productos_calc import vencimiento
    from app import models_productos as m
    h = _auth(client)
    pid = _pers(client, h)
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    nac = _hace(63)
    maximo = _plazo_max(pid, nac)
    with SessionLocal() as db:
        v = _version_efectiva(db.get(m.PPProducto, pid))
        p = _params_cronograma(v)
        ult = vencimiento(date.today(), maximo, frecuencia=p["frecuencia"], dia_pago=p["dia_pago"],
                          primer_venc_dias=p["primer_venc_dias"], ajuste_fin_semana=p["ajuste_fin_semana"])
        sig = vencimiento(date.today(), maximo + 1, frecuencia=p["frecuencia"], dia_pago=p["dia_pago"],
                          primer_venc_dias=p["primer_venc_dias"], ajuste_fin_semana=p["ajuste_fin_semana"])
    assert edad_de(nac, ult) == 65 and edad_de(nac, sig) == 66


def test_si_por_la_edad_no_entra_ni_el_plazo_minimo_lo_dice(client):
    h = _auth(client)
    pid = _pers(client, h)
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    nac = _hace(66) + timedelta(days=60)                              # tiene 65 y cumple 66 en 2 meses
    assert _plazo_max(pid, nac) < 6                                   # el plazo mínimo de la línea
    r = _express(client, h, pid, plazo=6, nacimiento=nac)
    assert r.status_code == 422, r.text
    assert "por la edad no puede pedir esta línea" in r.json()["detail"]


def test_al_modificar_el_plazo_tambien_se_controla(client):
    h = _auth(client)
    pid = _pers(client, h)
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    nac = _hace(63)
    maximo = _plazo_max(pid, nac)
    sid = _express(client, h, pid, plazo=maximo, nacimiento=nac).json()["id"]
    r = client.put(f"/api/creditos/solicitudes/{sid}", headers=h, json={"plazo_solicitado": maximo + 1})
    assert r.status_code == 422 and f"el plazo máximo es de {maximo} cuotas" in r.json()["detail"], r.text


# ------------------------------------------------------------------------------- portal
def test_el_portal_ofrece_solo_los_plazos_que_entran_por_la_edad(client):
    h, hp = _auth(client), _ingresar(client)
    pid = _pers(client, h)
    nac = _hace(63)
    url = f"/api/creditos/portal/productos?nacimiento={nac.isoformat()}"
    p = next(x for x in client.get(url, headers=hp).json() if x["id"] == pid)
    assert p["plazo_max_edad"] is None                                 # la línea lo permite

    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    p = next(x for x in client.get(url, headers=hp).json() if x["id"] == pid)
    assert p["plazo_max_edad"] == _plazo_max(pid, nac)
    sin = next(x for x in client.get("/api/creditos/portal/productos", headers=hp).json() if x["id"] == pid)
    assert sin["plazo_max_edad"] is None                               # sin fecha no hay tope por edad


def test_el_portal_no_deja_enviar_si_las_cuotas_pasan_la_edad_maxima(client):
    h, hp = _auth(client), _ingresar(client)
    pid = _pers(client, h)
    _disponibilidad(client, h, pid, permiteCuotasMasAllaEdadMax=False)
    nac = _hace(63)
    maximo = _plazo_max(pid, nac)
    body = {**CONSENT, "producto_id": pid, "monto": 500000.0, "segmento": "AGENTE_PUBLICO",
            "fecha_nacimiento": nac.isoformat()}
    sim = client.post("/api/creditos/portal/simular", headers=hp, json={**body, "plazo": maximo + 1}).json()
    assert sim["elegible"] is False and any("plazo máximo" in x for x in sim["motivos"])
    r = client.post("/api/creditos/portal/solicitudes", headers=hp, json={**body, "plazo": maximo + 1})
    assert r.status_code == 422 and f"el plazo máximo es de {maximo} cuotas" in r.json()["detail"], r.text
    r = client.post("/api/creditos/portal/solicitudes", headers=hp, json={**body, "plazo": maximo})
    assert r.status_code == 201, r.text
