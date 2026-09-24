"""Importación de los DBF del sistema anterior.

Los tests arman DBF de verdad (mismo formato VFP que el backup) con los campos que mira el
importador, y corren el proceso completo contra la base de tests.
"""
import struct
import zipfile
from datetime import date

import pytest

from app.models import (IMPORT_PROCESANDO, ImportacionDespacho, ModeloResolucion, Resolucion,
                        ResolucionBeneficiario)
from app.services import importacion as svc

# (nombre, tipo, largo) de cada DBF del backup.
CAMPOS_RTF = [("COD_MOD", "N", 6), ("DES_MOD", "C", 120), ("DISPOSICIO", "L", 1),
              ("SEGUROS", "L", 1), ("MODELO", "C", 200)]
CAMPOS_RES = [("NRO_RES", "N", 8), ("FEC_RES", "D", 8), ("DISPOSICIO", "L", 1),
              ("NRO_REAL", "N", 8), ("FEC_REAL", "D", 8), ("COD_MOT", "N", 6),
              ("IMPORTE", "N", 14), ("TEXTO", "C", 200), ("LANULADA", "L", 1),
              ("ID_TRAMITE", "C", 10), ("ID_LETRA", "C", 2), ("ID_NRO", "C", 6),
              ("ID_ANO", "C", 4), ("NRO_OP", "N", 8)]
CAMPOS_BEN = [("NRO_RES", "N", 8), ("FEC_RES", "D", 8), ("DISPOSICIO", "L", 1),
              ("TIPO_DOC", "N", 2), ("NRO_DOC", "C", 11), ("NOMBRE", "C", 80),
              ("TIPO_BENE", "N", 2), ("IMPORTE", "N", 14)]


def escribir_dbf(ruta, campos, filas):
    largo_reg = 1 + sum(c[2] for c in campos)
    hdr = 32 + 32 * len(campos) + 1
    hoy = date.today()
    out = bytearray()
    out += struct.pack("<BBBBIHH", 0x30, hoy.year - 2000, hoy.month, hoy.day,
                       len(filas), hdr, largo_reg) + b"\x00" * 20
    for nom, tipo, largo in campos:
        out += nom.encode("latin-1").ljust(11, b"\x00") + tipo.encode()
        out += b"\x00" * 4 + bytes([largo, 0]) + b"\x00" * 14
    out += b"\x0d"
    for f in filas:
        out += b" "
        for nom, tipo, largo in campos:
            v = f.get(nom)
            if tipo == "L":
                out += b"T" if v else b"F"
            elif tipo == "D":
                out += (v.strftime("%Y%m%d") if isinstance(v, date) else "        ").encode("latin-1")
            elif tipo == "N":
                out += str(v if v is not None else "").rjust(largo)[:largo].encode("latin-1")
            else:
                out += str(v or "").ljust(largo)[:largo].encode("latin-1")
    with open(ruta, "wb") as fh:
        fh.write(bytes(out) + b"\x1a")
    return str(ruta)


@pytest.fixture
def backup(tmp_path):
    """Arma el ZIP con los tres DBF, como el backup del sistema anterior."""
    def _armar(modelos=None, resoluciones=None, beneficiarios=None, en_carpeta=True):
        carpeta = tmp_path / "dbf"
        carpeta.mkdir(exist_ok=True)
        escribir_dbf(carpeta / "rtf.dbf", CAMPOS_RTF, modelos or [])
        escribir_dbf(carpeta / "resoluciones.dbf", CAMPOS_RES, resoluciones or [])
        if beneficiarios is not None:
            escribir_dbf(carpeta / "beneficiarios.dbf", CAMPOS_BEN, beneficiarios)
        zip_ruta = tmp_path / "despacho.zip"
        with zipfile.ZipFile(zip_ruta, "w") as z:
            for archivo in carpeta.iterdir():
                z.write(archivo, f"Despacho/{archivo.name}" if en_carpeta else archivo.name)
        return str(zip_ruta)
    return _armar


@pytest.fixture
def correr(db):
    def _correr(ruta, archivo="despacho.zip"):
        imp = ImportacionDespacho(archivo=archivo, tamano=1, usuario_id=7)
        db.add(imp)
        db.commit()
        svc.procesar(imp.id, ruta, session_factory=lambda: db)
        db.expire_all()
        return db.get(ImportacionDespacho, imp.id)
    return _correr


MODELO = {"COD_MOD": 103, "DES_MOD": "TRANSFERENCIA", "DISPOSICIO": False,
          "MODELO": "VISTO: el expediente de transferencia"}
RESOL = {"NRO_RES": 45, "FEC_RES": date(2024, 6, 10), "DISPOSICIO": False, "COD_MOT": 103,
         "IMPORTE": "125000.50", "TEXTO": "Cuerpo de la resolución", "NRO_REAL": 812,
         "FEC_REAL": date(2024, 7, 1), "ID_TRAMITE": "EXP", "ID_LETRA": "C", "ID_NRO": "1234",
         "ID_ANO": "2024"}


def test_importa_modelos_resoluciones_y_beneficiarios(db, backup, correr):
    ruta = backup(
        modelos=[MODELO, {"COD_MOD": 7, "DES_MOD": "BAJA", "DISPOSICIO": True}],
        resoluciones=[RESOL, {"NRO_RES": 2, "FEC_RES": date(2024, 1, 5), "DISPOSICIO": True,
                              "COD_MOT": 7, "TEXTO": "Disposición"}],
        beneficiarios=[{"NRO_RES": 45, "FEC_RES": date(2024, 6, 10), "DISPOSICIO": False,
                        "NRO_DOC": "30111222", "NOMBRE": "PEREZ JUAN", "IMPORTE": "1000"}])
    imp = correr(ruta)

    assert imp.estado == "TERMINADA"
    assert (imp.modelos, imp.resoluciones, imp.beneficiarios) == (2, 2, 1)

    r = db.query(Resolucion).filter(Resolucion.numero == 45).one()
    assert (r.tipo, r.anio, r.numero_real) == ("RES", 2024, 812)
    assert r.fecha_real == date(2024, 7, 1)
    assert r.motivo == "TRANSFERENCIA"          # COD_MOT resuelve contra el modelo
    assert float(r.importe) == 125000.50
    assert r.origen == "EXP C 1234 2024"        # el origen viene partido en cuatro campos
    assert r.estado == "F"                      # lo importado ya fue emitido
    assert "Cuerpo de la resolución" in r.texto

    dis = db.query(Resolucion).filter(Resolucion.tipo == "DIS").one()
    assert dis.numero == 2 and dis.motivo == "BAJA"

    b = db.query(ResolucionBeneficiario).one()
    assert (b.nombre, b.resolucion_id) == ("PEREZ JUAN", r.id)


def test_el_texto_rtf_se_convierte_a_html(db, backup, correr):
    ruta = backup(modelos=[{**MODELO, "MODELO": r"{\rtf1\ansi {\b NEGRITA} normal}"}],
                  resoluciones=[RESOL])
    correr(ruta)
    m = db.query(ModeloResolucion).one()
    assert "<" in m.plantilla and "NEGRITA" in m.plantilla and "rtf1" not in m.plantilla


def test_volver_a_subir_el_mismo_archivo_no_duplica(db, backup, correr):
    ruta = backup(modelos=[MODELO], resoluciones=[RESOL],
                  beneficiarios=[{"NRO_RES": 45, "FEC_RES": date(2024, 6, 10), "DISPOSICIO": False,
                                  "NRO_DOC": "30111222", "NOMBRE": "PEREZ JUAN"}])
    primera = correr(ruta)
    segunda = correr(ruta)

    assert (primera.modelos, primera.resoluciones) == (1, 1)
    assert (segunda.modelos, segunda.resoluciones, segunda.beneficiarios) == (0, 0, 0)
    assert segunda.omitidas >= 2
    assert db.query(Resolucion).count() == 1 and db.query(ModeloResolucion).count() == 1
    assert db.query(ResolucionBeneficiario).count() == 1


def test_el_correlativo_repetido_en_el_archivo_entra_una_vez(db, backup, correr):
    """El backup viejo trae repetidos: el correlativo es único por (año, tipo), gana el primero."""
    imp = correr(backup(modelos=[MODELO], resoluciones=[RESOL, {**RESOL, "TEXTO": "otra"}]))
    assert imp.resoluciones == 1 and imp.omitidas >= 1


def test_se_descartan_las_fechas_imposibles(db, backup, correr):
    """El backup trae fechas corruptas (año 0): esas filas no se importan."""
    imp = correr(backup(modelos=[MODELO],
                        resoluciones=[RESOL, {"NRO_RES": 99, "FEC_RES": None, "COD_MOT": 103}]))
    assert imp.resoluciones == 1 and imp.omitidas >= 1


def test_los_dbf_sueltos_tambien_sirven(db, backup, correr):
    """El ZIP puede traerlos dentro de 'Despacho/' o en la raíz."""
    imp = correr(backup(modelos=[MODELO], resoluciones=[RESOL], en_carpeta=False))
    assert imp.estado == "TERMINADA" and imp.resoluciones == 1


def test_sin_resoluciones_dbf_termina_con_error(db, tmp_path, correr):
    vacio = tmp_path / "otro.zip"
    with zipfile.ZipFile(vacio, "w") as z:
        z.writestr("leeme.txt", "nada")
    imp = correr(str(vacio))
    assert imp.estado == "ERROR" and "resoluciones.dbf" in imp.mensaje


def test_una_importacion_cortada_por_un_reinicio_se_marca(db):
    db.add(ImportacionDespacho(archivo="x.zip", tamano=1, estado=IMPORT_PROCESANDO))
    db.commit()
    assert svc.marcar_interrumpidas(db) == 1
    assert db.query(ImportacionDespacho).one().estado == "INTERRUMPIDA"


# --------------------------------------------------------------------------- endpoint
def test_la_subida_arranca_la_importacion(client, h, db, tmp_path, monkeypatch, backup):
    monkeypatch.setattr(svc, "DIR_IMPORTS", str(tmp_path / "subidas"))
    lanzados = []
    monkeypatch.setattr("app.routers.importacion.threading.Thread",
                        lambda **kw: type("T", (), {"start": lambda s: lanzados.append(kw)})())
    with open(backup(modelos=[MODELO], resoluciones=[RESOL]), "rb") as f:
        r = client.post("/api/despacho/importaciones", headers=h,
                        files={"file": ("despacho.zip", f, "application/zip")})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "PENDIENTE" and r.json()["tamano"] > 0
    assert lanzados and lanzados[0]["args"][0] == r.json()["id"]


def test_no_deja_subir_otra_cosa_ni_dos_a_la_vez(client, h, db, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "DIR_IMPORTS", str(tmp_path))
    r = client.post("/api/despacho/importaciones", headers=h,
                    files={"file": ("planilla.xlsx", b"x", "application/vnd.ms-excel")})
    assert r.status_code == 422

    db.add(ImportacionDespacho(archivo="otra.zip", tamano=1, estado=IMPORT_PROCESANDO))
    db.commit()
    r = client.post("/api/despacho/importaciones", headers=h,
                    files={"file": ("despacho.zip", b"x", "application/zip")})
    assert r.status_code == 409 and "en curso" in r.json()["detail"]


def test_importar_pide_su_permiso(client, solo_lectura):
    r = client.get("/api/despacho/importaciones", headers=solo_lectura)
    assert r.status_code == 403 and "despacho:importar" in r.json()["detail"]
