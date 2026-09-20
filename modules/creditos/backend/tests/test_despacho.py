"""Módulo Despacho: resoluciones/disposiciones y expedientes con pases."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_resolucion_alta_numeracion_y_firma(client):
    h = _auth(client)
    r1 = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "asunto": "Aprobación de créditos lote 1",
        "organo": "Directorio", "fecha": "2026-05-02"}).json()
    r2 = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "asunto": "Otra resolución", "fecha": "2026-05-03"}).json()
    # numeración correlativa por año/tipo
    assert r2["numero"] == r1["numero"] + 1
    assert r1["estado"] == "B"

    firmada = client.post(f"/api/creditos/despacho/resoluciones/{r1['id']}/firmar", headers=h).json()
    assert firmada["estado"] == "F"
    # no se puede refirmar
    assert client.post(f"/api/creditos/despacho/resoluciones/{r1['id']}/firmar", headers=h).status_code == 409


def test_resolucion_modelo_beneficiarios_y_numero_real(client):
    """H-164: la resolución replica la pantalla legacy — el MODELO define el motivo y su plantilla es el
    cuerpo base; guarda importe, origen y la grilla de beneficiarios; el N° Real se carga aparte."""
    from app.core.database import SessionLocal
    from app import models as m
    with SessionLocal() as db:
        db.add(m.ModeloResolucion(codigo=900, descripcion="TRANSFERENCIA",
                                  plantilla="Por ello, EL DIRECTOR RESUELVE: ...")); db.commit()
    h = _auth(client)
    r = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "fecha": "2026-06-01", "modelo_codigo": 900, "importe": 250000.5,
        "origen": "E10 55/2026",
        "beneficiarios": [{"tipo_doc": 1, "nro_doc": "27345678", "nombre": "GOMEZ, ANA", "tipo_bene": 1},
                          {"nombre": "ASOC MUTUAL X"}]}).json()
    assert r["motivo"] == "TRANSFERENCIA" and r["motivo_cod"] == 900   # el modelo define el motivo
    assert "RESUELVE" in r["texto"]                                    # plantilla cargada como cuerpo
    assert float(r["importe"]) == 250000.5 and r["origen"] == "E10 55/2026"
    assert len(r["beneficiarios"]) == 2 and r["numero_real"] is None and r["estado"] == "B"

    nr = client.post(f"/api/creditos/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={}).json()
    assert nr["numero_real"] == 1 and nr["estado"] == "F"
    # no se puede recargar el N° Real
    assert client.post(f"/api/creditos/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={}).status_code == 409
    # un beneficiario sin nombre es inválido (422)
    assert client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "modelo_codigo": 900, "beneficiarios": [{"nombre": ""}]}).status_code == 422


def test_resolucion_editar_borrador(client):
    """H-168: un borrador se puede editar (texto, modelo→motivo, importe, origen, beneficiarios) sin
    cambiar tipo/número/año; una vez OFICIAL (Nº Real) queda inmutable (422)."""
    from app.core.database import SessionLocal
    from app import models as m
    with SessionLocal() as db:
        db.add(m.ModeloResolucion(codigo=910, descripcion="SUBSIDIO"))
        db.add(m.ModeloResolucion(codigo=911, descripcion="AYUDA ECONOMICA")); db.commit()
    h = _auth(client)
    r = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "fecha": "2026-07-01", "modelo_codigo": 910, "importe": 1000,
        "beneficiarios": [{"nombre": "UNO"}]}).json()
    n0 = r["numero"]
    assert r["motivo"] == "SUBSIDIO" and float(r["importe"]) == 1000

    # editar: cambia modelo (motivo), texto, importe, origen y reemplaza beneficiarios
    e = client.put(f"/api/creditos/despacho/resoluciones/{r['id']}", headers=h, json={
        "modelo_codigo": 911, "texto": "<h2>VISTO</h2><p>Nuevo cuerpo.</p>", "importe": 2500.75,
        "origen": "E20 9/2026",
        "beneficiarios": [{"tipo_doc": 1, "nro_doc": "30111222", "nombre": "DOS"}, {"nombre": "TRES"}]})
    assert e.status_code == 200
    ed = e.json()
    assert ed["numero"] == n0 and ed["tipo"] == "RES" and ed["anio"] == 2026   # no cambia la serie
    assert ed["motivo"] == "AYUDA ECONOMICA" and float(ed["importe"]) == 2500.75
    assert ed["origen"] == "E20 9/2026" and "Nuevo cuerpo" in ed["texto"]
    assert len(ed["beneficiarios"]) == 2 and {b["nombre"] for b in ed["beneficiarios"]} == {"DOS", "TRES"}

    # una vez con Nº Real (oficial) ya no se puede editar
    client.post(f"/api/creditos/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={})
    bad = client.put(f"/api/creditos/despacho/resoluciones/{r['id']}", headers=h, json={"importe": 5})
    assert bad.status_code == 422 and "oficial" in bad.json()["detail"].lower()


def test_resolucion_word_nombre_y_html(client):
    """H-166: el Word usa el nombre institucional correcto (PRESTACIONES, no 'Previsión Popular') y
    renderiza el texto HTML del editor mini-Word (títulos/negrita), sin duplicar el título."""
    import io, zipfile, re
    from app.core.database import SessionLocal
    from app import models as m
    with SessionLocal() as db:
        db.add(m.ModeloResolucion(codigo=901, descripcion="AYUDA SOCIAL")); db.commit()
    h = _auth(client)
    r = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "modelo_codigo": 901,
        "texto": "<h2>VISTO</h2><p>El <b>expediente X</b>.</p><h2>RESUELVE</h2><p>Art. 1.</p>"}).json()
    docx = client.get(f"/api/creditos/despacho/resoluciones/{r['id']}/word", headers=h)
    assert docx.status_code == 200 and docx.headers["content-type"].startswith("application/vnd")
    xml = re.sub("<[^>]+>", " ", zipfile.ZipFile(io.BytesIO(docx.content)).read("word/document.xml").decode("utf-8", "ignore"))
    assert "PRESTACIONES" in xml and "Previsión Popular" not in xml   # nombre correcto
    assert "AYUDA SOCIAL" in xml                                       # motivo como subtítulo
    assert "VISTO" in xml and "RESUELVE" in xml and "expediente X" in xml   # HTML renderizado


def test_expediente_con_pases(client):
    h = _auth(client)
    exp = client.post("/api/creditos/despacho/expedientes", headers=h, json={
        "numero": "EXP-2026-000123", "caratula": "Solicitud de crédito - PEREZ",
        "iniciador": "Mesa de Entradas", "oficina_inicial": "Mesa de Entradas",
        "fecha": "2026-05-02"}).json()
    assert exp["estado"] == "T"
    assert exp["oficina_actual"] == "Mesa de Entradas"
    assert len(exp["pases"]) == 1  # pase inicial

    # pasar a Créditos y luego a Directorio
    exp = client.post(f"/api/creditos/despacho/expedientes/{exp['id']}/pase", headers=h, json={
        "oficina_destino": "Créditos", "motivo": "Evaluación"}).json()
    exp = client.post(f"/api/creditos/despacho/expedientes/{exp['id']}/pase", headers=h, json={
        "oficina_destino": "Directorio", "motivo": "Aprobación"}).json()
    assert exp["oficina_actual"] == "Directorio"
    assert len(exp["pases"]) == 3
    assert exp["pases"][-1]["oficina_origen"] == "Créditos"

    # archivar y ya no se puede pasar
    client.post(f"/api/creditos/despacho/expedientes/{exp['id']}/archivar", headers=h)
    r = client.post(f"/api/creditos/despacho/expedientes/{exp['id']}/pase", headers=h, json={
        "oficina_destino": "Archivo", "motivo": "x"})
    assert r.status_code == 409


def test_resolucion_word(client):
    h = _auth(client)
    r = client.post("/api/creditos/despacho/resoluciones", headers=h, json={
        "tipo": "RES", "asunto": "Aprobación de créditos", "organo": "Directorio",
        "texto": "VISTO:\nEl expediente EXP-2026-000123;\nCONSIDERANDO:\nQue procede;",
        "fecha": "2026-05-02"}).json()
    doc = client.get(f"/api/creditos/despacho/resoluciones/{r['id']}/word", headers=h)
    assert doc.status_code == 200
    assert doc.content[:2] == b"PK"   # firma de archivo .docx (zip)
    assert "wordprocessingml" in doc.headers["content-type"]
    assert "RES_" in doc.headers.get("content-disposition", "")


def test_numero_expediente_unico(client):
    h = _auth(client)
    body = {"numero": "EXP-2026-000999", "caratula": "X",
            "oficina_inicial": "Mesa", "fecha": "2026-05-02"}
    assert client.post("/api/creditos/despacho/expedientes", headers=h, json=body).status_code == 201
    assert client.post("/api/creditos/despacho/expedientes", headers=h, json=body).status_code == 409


def test_modelos_resolucion(client):
    h = _auth(client)
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.ModeloResolucion(tipo_res=1, codigo=3,
        descripcion="AYUDAS SOCIALES A PERSONAS", es_disposicion=False,
        es_seguros=False, tiene_plantilla=False))
    db.commit(); db.close()
    r = client.get("/api/creditos/despacho/modelos", headers=h).json()
    m = next(x for x in r if x["codigo"] == 3)
    assert m["descripcion"] == "AYUDAS SOCIALES A PERSONAS"
    assert m["tipo"] == "Resolución"
    # búsqueda
    r2 = client.get("/api/creditos/despacho/modelos?q=AYUDAS", headers=h).json()
    assert len(r2) >= 1


def test_modelo_abm_crear_editar(client):
    """H-167: los modelos de resolución se crean y editan desde la ABM con el mismo editor mini-Word.
    El código se asigna solo (MAX+1), el tipo mapea a disposición/resolución y la plantilla se guarda
    como HTML (tiene_plantilla refleja si hay contenido)."""
    h = _auth(client)
    prev = client.get("/api/creditos/despacho/modelos", headers=h).json()
    prev_max = max((x["codigo"] for x in prev), default=0)

    # alta: código autoasignado, disposición, plantilla HTML del editor
    r = client.post("/api/creditos/despacho/modelos", headers=h, json={
        "descripcion": "acta volante qa", "tipo": "DIS", "seguros": True,
        "plantilla": "<h2>VISTO</h2><p>Cuerpo base.</p>"})
    assert r.status_code == 201
    m = r.json()
    assert m["codigo"] == prev_max + 1 and m["descripcion"] == "ACTA VOLANTE QA"
    assert m["tipo"] == "Disposición" and m["es_seguros"] is True and m["tiene_plantilla"] is True

    # edición: cambia descripción/tipo y vacía la plantilla
    e = client.put(f"/api/creditos/despacho/modelos/{m['id']}", headers=h, json={
        "descripcion": "acta editada", "tipo": "RES", "seguros": False, "plantilla": ""}).json()
    assert e["descripcion"] == "ACTA EDITADA" and e["tipo"] == "Resolución"
    assert e["es_seguros"] is False and e["tiene_plantilla"] is False and e["codigo"] == m["codigo"]

    # persistió y sigue accesible por id
    det = client.get(f"/api/creditos/despacho/modelos/{m['id']}", headers=h).json()
    assert det["descripcion"] == "ACTA EDITADA" and det["plantilla"] == ""
    # descripción vacía es inválida (422)
    assert client.post("/api/creditos/despacho/modelos", headers=h, json={"descripcion": "  "}).status_code == 422


def test_anexo_resolucion_lote(client):
    """Regresión del Anexo de Resolución real (H-026): asignación de lote de
    solicitudes AGAP (línea 8050) a una resolución."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    # solicitud AGAP aprobada, sin resolución
    db.add(models.SolicitudCredito(id=120349, fecha_soli=datetime.date(2018, 4, 9),
        cuil="27137090541", apellido_nombre="MORALES ELENA", montosol=Decimal("30000"),
        linea=8050, estado="A", cubica="C", no_resol=0, en_reso=False, lote=0))
    # otra que NO es AGAP (línea fuera de rango) — no debe aparecer
    db.add(models.SolicitudCredito(id=120350, cuil="20111111112", apellido_nombre="OTRO",
        montosol=Decimal("5000"), linea=6800, estado="A", cubica="C", no_resol=0, en_reso=False, lote=0))
    db.commit(); db.close()

    # tipos disponibles
    tipos = client.get("/api/creditos/despacho/anexo/tipos", headers=h).json()
    assert any(t["tipo"] == 1 and t["nombre"] == "AGAP" for t in tipos)

    # candidatas AGAP (tipo 1) -> solo la 120349
    cand = client.get("/api/creditos/despacho/anexo/solicitudes?tipo=1", headers=h).json()
    ids = [s["no_solicitud"] for s in cand["items"]]
    assert 120349 in ids and 120350 not in ids

    # asignar a resolución N° 45
    r = client.post("/api/creditos/despacho/anexo/asignar", headers=h, json={
        "tipo": 1, "numero": 45, "fecha": "2026-08-04", "solicitud_ids": [120349]}).json()
    assert r["asignadas"] == 1 and r["numero"] == 45

    # ya no aparece entre candidatas (en_reso)
    cand2 = client.get("/api/creditos/despacho/anexo/solicitudes?tipo=1", headers=h).json()
    assert 120349 not in [s["no_solicitud"] for s in cand2["items"]]

    # reimpresión por lote 45 -> aparece
    reimp = client.get("/api/creditos/despacho/anexo/solicitudes?tipo=1&lote=45", headers=h).json()
    assert 120349 in [s["no_solicitud"] for s in reimp["items"]]

    # excel del anexo
    x = client.get("/api/creditos/despacho/anexo/excel?tipo=1&lote=45", headers=h)
    assert x.status_code == 200 and x.content[:2] == b"PK"

    # no se puede reasignar a otra resolución
    bad = client.post("/api/creditos/despacho/anexo/asignar", headers=h, json={
        "tipo": 1, "numero": 99, "fecha": "2026-08-04", "solicitud_ids": [120349]})
    assert bad.status_code == 422


def test_expedientes_por_oficina(client):
    h = _auth(client)
    client.post("/api/creditos/despacho/expedientes", headers=h, json={
        "numero": "EXP-2026-777", "caratula": "X", "oficina_inicial": "Mesa de Entradas"})
    r = client.get("/api/creditos/despacho/expedientes-por-oficina", headers=h).json()
    assert any(o["oficina"] == "Mesa de Entradas" and o["cantidad"] >= 1 for o in r)
