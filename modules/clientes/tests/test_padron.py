"""Importación del padrón del sistema anterior (maeclientes.dbf).

Los tests arman un DBF de verdad (mismo formato VFP que el archivo real, con los campos que usa el
importador) y corren el proceso completo contra la base de tests.
"""
import struct
import zipfile
from datetime import date

import pytest

from app.models import (Client, ClientCbu, ClientImport, ClientImportRechazo, ClientLegacyRef,
                        ClientPadron, HumanClient, IMPORT_PROCESANDO, IMPORT_TERMINADA)
from app.services import padron_import
from app.services.padron_import import partir_nombre, clave_persona, procesar

# (nombre, tipo, largo) — el subconjunto del padrón real que mira el importador.
CAMPOS = [
    ("CIDCLIENTE", "C", 15), ("CCUIL", "C", 11), ("CAPENOM", "C", 40), ("EDNI", "I", 4),
    ("FNACIM", "D", 8), ("CSEXO", "C", 1), ("CDOMICILIO", "C", 30), ("CBARRIO", "C", 30),
    ("CLOCALIDAD", "C", 30), ("CDEPTO", "C", 30), ("CCPA", "C", 8), ("CTELEFONO", "C", 25),
    ("CEMAIL", "C", 100), ("NORGANO", "N", 12), ("CORGA", "C", 3), ("NTIPOCLI", "N", 2),
    ("CBENEF", "C", 20), ("CCATFUN", "C", 40), ("NSUELDO", "N", 10), ("NSITUACION", "N", 1),
    ("CCBUCTA", "C", 23), ("LDEBAUTO", "L", 1), ("LBAJA", "L", 1), ("CMOTBAJA", "C", 60),
]


def escribir_dbf(ruta, filas, borradas=()):
    """Arma un .dbf VFP con CAMPOS y las filas dadas (dict campo→valor)."""
    largo_reg = 1 + sum(c[2] for c in CAMPOS)
    hdr_len = 32 + 32 * len(CAMPOS) + 1
    hoy = date.today()
    out = bytearray()
    out += struct.pack("<BBBBIHH", 0x30, hoy.year - 2000, hoy.month, hoy.day,
                       len(filas), hdr_len, largo_reg) + b"\x00" * 20
    for nom, tipo, largo in CAMPOS:
        out += nom.encode("latin-1").ljust(11, b"\x00") + tipo.encode()
        out += b"\x00" * 4 + bytes([largo, 0]) + b"\x00" * 14
    out += b"\x0d"
    for i, f in enumerate(filas):
        out += b"*" if i in borradas else b" "
        for nom, tipo, largo in CAMPOS:
            v = f.get(nom)
            if tipo == "I":
                out += struct.pack("<i", int(v or 0))
            elif tipo == "L":
                out += b"T" if v else b"F"
            elif tipo == "D":
                out += (v.strftime("%Y%m%d") if v else "        ").encode("latin-1")
            elif tipo == "N":
                out += str(v if v is not None else "").rjust(largo)[:largo].encode("latin-1")
            else:
                out += str(v or "").ljust(largo)[:largo].encode("latin-1")
    with open(ruta, "wb") as fh:
        fh.write(bytes(out) + b"\x1a")
    return str(ruta)


def fila(cid, cuil, apenom, dni, **extra):
    base = {"CIDCLIENTE": cid, "CCUIL": cuil, "CAPENOM": apenom, "EDNI": dni,
            "NORGANO": 13, "CORGA": "ACA", "NSUELDO": 900000, "CCATFUN": "AGENTE"}
    base.update(extra)
    return base


@pytest.fixture
def correr(db, tmp_path):
    """Crea la importación y la corre en la sesión de tests (el hilo real usa la suya)."""
    def _correr(filas, borradas=(), archivo="maeclientes.dbf"):
        ruta = escribir_dbf(tmp_path / archivo, filas, borradas)
        imp = ClientImport(archivo=archivo, tamano=1, usuario_id=7)
        db.add(imp)
        db.commit()
        procesar(imp.id, ruta, session_factory=lambda: db)
        db.expire_all()
        return db.get(ClientImport, imp.id)
    return _correr


# --------------------------------------------------------------------------- utilidades
@pytest.mark.parametrize("entrada, esperado", [
    ("CORDOBA, EDGARDO ADRIAN", ("CORDOBA", "EDGARDO ADRIAN")),
    ("BORDON FLAVIO LAZARO", ("BORDON", "FLAVIO LAZARO")),
    ("PEREZ", ("PEREZ", "")),
    ("  GOMEZ ,  ANA  ", ("GOMEZ", "ANA")),
])
def test_separa_apellido_y_nombres(entrada, esperado):
    assert partir_nombre(entrada) == esperado


def test_la_clave_de_unificacion_es_el_cuil_y_si_no_el_dni():
    assert clave_persona("20305047571", "30504757") == ("CUIL", "20305047571")
    assert clave_persona("", "30504757") == ("DNI", "30504757")
    assert clave_persona("123", "45") is None        # ninguno sirve para identificar


# --------------------------------------------------------------------------- unificación
def test_la_misma_persona_en_varios_organismos_es_un_solo_cliente(db, correr):
    """En el padrón viejo el CIDCLIENTE es prefijo + CUIL: la misma persona viene una vez por
    organismo. Tienen que quedar UN cliente y las tres referencias al sistema anterior."""
    imp = correr([
        fila("ACA20305047571M", "20305047571", "CORDOBA, EDGARDO ADRIAN", 30504757, NORGANO=13),
        fila("AGC20305047571M", "20305047571", "CORDOBA, EDGARDO ADRIAN", 30504757, NORGANO=13),
        fila("AGJ20305047571M", "20305047571", "CORDOBA, EDGARDO ADRIAN", 30504757, NORGANO=9),
    ])
    assert (imp.estado, imp.total, imp.procesados) == (IMPORT_TERMINADA, 3, 3)
    assert (imp.creados, imp.actualizados, imp.rechazados) == (1, 2, 0)

    assert db.query(Client).count() == 1
    perfil = db.query(HumanClient).one()
    assert (perfil.last_name, perfil.first_name) == ("CORDOBA", "EDGARDO ADRIAN")
    assert (perfil.cuil, perfil.document_number) == ("20305047571", "30504757")
    refs = db.query(ClientLegacyRef).order_by(ClientLegacyRef.cidcliente).all()
    assert [r.cidcliente for r in refs] == ["ACA20305047571M", "AGC20305047571M", "AGJ20305047571M"]
    assert {r.client_id for r in refs} == {perfil.client_id}


def test_personas_distintas_quedan_separadas(db, correr):
    imp = correr([
        fila("ACA20305047571M", "20305047571", "CORDOBA, EDGARDO", 30504757),
        fila("ACA27327644434M", "27327644434", "PINETTA, PATRICIA", 32764443),
    ])
    assert imp.creados == 2 and db.query(Client).count() == 2


def test_sin_cuil_se_unifica_por_dni(db, correr):
    imp = correr([
        fila("X1", "", "SIN CUIL, JUAN", 12345678),
        fila("X2", "", "SIN CUIL, JUAN", 12345678),
    ])
    assert (imp.creados, imp.actualizados) == (1, 1)
    assert db.query(HumanClient).one().document_number == "12345678"


# --------------------------------------------------------------------------- datos
def test_trae_domicilio_completo_padron_y_cbu(db, correr):
    correr([fila("ACA20305047571M", "20305047571", "CORDOBA, EDGARDO", 30504757,
                 CDOMICILIO="SAN MARTIN 123", CBARRIO="CENTRO", CLOCALIDAD="SFV CATAMARCA",
                 CDEPTO="CAPITAL", CCPA="K4700", CTELEFONO="3834123456", CEMAIL="e@example.gob.ar",
                 FNACIM=date(1986, 3, 4), CSEXO="M", CCBUCTA="2850590940090418135201",
                 LDEBAUTO=True, NSITUACION=1, NTIPOCLI=2, CBENEF="BEN-1")])
    c = db.query(Client).one()
    assert (c.address, c.neighborhood, c.city) == ("SAN MARTIN 123", "CENTRO", "SFV CATAMARCA")
    assert (c.department, c.postal_code) == ("CAPITAL", "K4700")
    assert (c.phone, c.email) == ("3834123456", "e@example.gob.ar")
    perfil = db.query(HumanClient).one()
    assert perfil.birth_date == "1986-03-04" and perfil.gender == "M"

    p = db.get(ClientPadron, c.id)
    assert (p.organismo_numero, p.organismo_codigo, p.categoria) == (13, "ACA", "AGENTE")
    assert float(p.sueldo) == 900000 and p.debito_automatico is True
    assert (p.situacion, p.tipo_cliente, p.beneficio) == (1, 2, "BEN-1")

    cbu = db.query(ClientCbu).one()
    assert cbu.cbu == "2850590940090418135201" and cbu.client_id == c.id


def test_un_cbu_invalido_no_se_carga(db, correr):
    correr([fila("A1", "20305047571", "UNO, UNO", 30504757, CCBUCTA="123")])
    assert db.query(ClientCbu).count() == 0


# --------------------------------------------------------------------------- rechazos
def test_rechaza_lo_que_no_se_puede_identificar(db, correr):
    imp = correr([
        fila("A1", "", "SIN DOCUMENTO, JUAN", 0),
        fila("A2", "20305047571", "", 30504757),
        fila("A3", "20327644433", "VALIDO, ANA", 32764443),
    ])
    assert (imp.creados, imp.rechazados) == (1, 2)
    motivos = sorted(r.motivo for r in db.query(ClientImportRechazo).all())
    assert motivos == ["Sin CUIL ni DNI válidos", "Sin apellido y nombre"]
    csv = padron_import.rechazos_csv(db, imp.id)
    assert "SIN DOCUMENTO, JUAN" in csv and csv.startswith("fila;cidcliente")


def test_los_registros_borrados_del_dbf_no_se_importan(db, correr):
    imp = correr([
        fila("A1", "20305047571", "BORRADO, JUAN", 30504757),
        fila("A2", "20327644433", "VIVO, ANA", 32764443),
    ], borradas={0})
    assert imp.procesados == 1 and imp.creados == 1
    assert db.query(HumanClient).one().last_name == "VIVO"


# --------------------------------------------------------------------------- reimportación
def test_volver_a_subir_el_archivo_no_duplica(db, correr):
    filas = [fila("ACA20305047571M", "20305047571", "CORDOBA, EDGARDO", 30504757)]
    correr(filas)
    segunda = correr(filas)
    assert (segunda.creados, segunda.actualizados) == (0, 1)
    assert db.query(Client).count() == 1
    assert db.query(ClientLegacyRef).count() == 1


def test_no_pisa_lo_corregido_a_mano_pero_si_actualiza_el_padron(db, correr):
    correr([fila("A1", "20305047571", "CORDOBA, EDGARDO", 30504757,
                 CTELEFONO="3834000000", NSUELDO=900000)])
    c = db.query(Client).one()
    c.phone = "3834999999"          # el operador lo corrigió
    db.commit()

    correr([fila("A1", "20305047571", "CORDOBA, EDGARDO", 30504757,
                 CTELEFONO="3834000000", NSUELDO=1500000)])
    db.expire_all()
    assert db.query(Client).one().phone == "3834999999"          # el contacto no se pisa
    assert float(db.query(ClientPadron).one().sueldo) == 1500000  # el padrón sí se actualiza


# --------------------------------------------------------------------------- archivo y endpoints
def test_acepta_el_padron_dentro_de_un_zip(db, tmp_path, correr):
    dbf = escribir_dbf(tmp_path / "maeclientes.dbf",
                       [fila("A1", "20305047571", "CORDOBA, EDGARDO", 30504757)])
    zip_ruta = tmp_path / "maeclientes.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.write(dbf, "maeclientes.dbf")
    imp = ClientImport(archivo="maeclientes.zip", tamano=1, usuario_id=7)
    db.add(imp); db.commit()
    procesar(imp.id, str(zip_ruta), session_factory=lambda: db)
    db.expire_all()
    assert db.get(ClientImport, imp.id).creados == 1


def test_un_archivo_que_no_es_el_padron_termina_en_error(db, tmp_path):
    otro = tmp_path / "otra.dbf"
    otro.write_bytes(b"no soy un dbf")
    imp = ClientImport(archivo="otra.dbf", tamano=1, usuario_id=7)
    db.add(imp); db.commit()
    procesar(imp.id, str(otro), session_factory=lambda: db)
    db.expire_all()
    assert db.get(ClientImport, imp.id).estado == "ERROR"


def test_subida_por_la_web_arranca_la_importacion(client, h, db, tmp_path, monkeypatch):
    monkeypatch.setattr(padron_import, "DIR_IMPORTS", str(tmp_path))
    lanzados = []
    monkeypatch.setattr("app.routers.padron.threading.Thread",
                        lambda **kw: type("T", (), {"start": lambda s: lanzados.append(kw)})())
    dbf = escribir_dbf(tmp_path / "origen.dbf",
                       [fila("A1", "20305047571", "CORDOBA, EDGARDO", 30504757)])
    with open(dbf, "rb") as f:
        r = client.post("/api/clientes/padron/importaciones", headers=h,
                        files={"file": ("maeclientes.dbf", f, "application/octet-stream")})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "PENDIENTE" and cuerpo["tamano"] > 0
    assert lanzados and lanzados[0]["args"][0] == cuerpo["id"]

    assert client.get("/api/clientes/padron/importaciones", headers=h).json()["items"][0]["id"] == cuerpo["id"]
    assert client.get(f"/api/clientes/padron/importaciones/{cuerpo['id']}", headers=h).status_code == 200


def test_no_deja_subir_otra_cosa_ni_dos_a_la_vez(client, h, db, tmp_path, monkeypatch):
    monkeypatch.setattr(padron_import, "DIR_IMPORTS", str(tmp_path))
    r = client.post("/api/clientes/padron/importaciones", headers=h,
                    files={"file": ("planilla.xlsx", b"x", "application/vnd.ms-excel")})
    assert r.status_code == 422

    db.add(ClientImport(archivo="otra.dbf", tamano=1, estado=IMPORT_PROCESANDO))
    db.commit()
    r = client.post("/api/clientes/padron/importaciones", headers=h,
                    files={"file": ("maeclientes.dbf", b"x", "application/octet-stream")})
    assert r.status_code == 409 and "en curso" in r.json()["detail"]


def test_una_importacion_cortada_por_un_reinicio_se_marca(db):
    db.add(ClientImport(archivo="x.dbf", tamano=1, estado=IMPORT_PROCESANDO))
    db.commit()
    assert padron_import.marcar_interrumpidas(db) == 1
    assert db.query(ClientImport).one().estado == "INTERRUMPIDA"


def test_una_fila_que_la_base_rechaza_no_tumba_el_lote(db, correr, monkeypatch, tmp_path):
    """El lote entero va en un SAVEPOINT por velocidad; si una fila no entra (un dato que se pasa del
    tamaño de su columna, por ejemplo), se rehace el lote fila por fila y sólo esa queda afuera."""
    original = padron_import._padron

    def _explota_en_una(db_, client_id, row, idx):
        if row.get("cidcliente") == "MALA":
            raise ValueError("integer out of range")
        return original(db_, client_id, row, idx)

    monkeypatch.setattr(padron_import, "_padron", _explota_en_una)
    imp = correr([
        fila("BUENA1", "20305047571", "UNO, UNO", 30504757),
        fila("MALA", "20327644433", "MALA, DOS", 32764443, NORGANO=370000000000),
        fila("BUENA2", "27354785669", "TRES, TRES", 35478566),
    ])
    assert (imp.creados, imp.rechazados) == (2, 1)
    assert imp.procesados == 3
    assert {c.code for c in db.query(Client).all()} == {"PAD20305047571", "PAD27354785669"}
    rechazo = db.query(ClientImportRechazo).one()
    assert rechazo.cidcliente == "MALA" and "integer out of range" in rechazo.motivo


def test_procesa_de_a_lotes_y_va_guardando_el_avance(db, correr, monkeypatch):
    monkeypatch.setattr(padron_import, "LOTE", 2)
    imp = correr([fila(f"A{i}", f"203050475{i:02d}", f"UNO{i}, UNO", 30504700 + i) for i in range(5)])
    assert (imp.procesados, imp.creados) == (5, 5)
    assert db.query(Client).count() == 5
