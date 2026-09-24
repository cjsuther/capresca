"""Importación de despacho desde los DBF del sistema anterior.

Se sube un ZIP con `rtf.dbf` (los modelos), `resoluciones.dbf` y `beneficiarios.dbf`. Como el padrón
de clientes, se procesa **en segundo plano** y la pantalla muestra el avance.

Cosas del formato viejo que hay que respetar:

- Los textos son **RTF** (campos memo): se convierten al HTML que usa el editor.
- El "motivo" de una resolución no es una tabla aparte: `COD_MOT` es el **código del modelo**, y el
  motivo que se muestra es la descripción de ese modelo.
- El correlativo es único por (año, tipo): si el archivo trae repetidos, gana el primero.

Es idempotente: lo que ya está no se vuelve a crear ni se pisa.
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import zipfile
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (IMPORT_ERROR, IMPORT_INTERRUMPIDA, IMPORT_PROCESANDO, IMPORT_TERMINADA,
                        ImportacionDespacho, ModeloResolucion, Resolucion, ResolucionBeneficiario)
from app.services.dbf import DbfReader
from app.services.rtf import rtf_a_html

log = logging.getLogger("despacho.importacion")

DIR_IMPORTS = os.getenv("DESPACHO_IMPORT_DIR", "/data/despacho")
LOTE = 500


def _s(v) -> str:
    return str(v).strip() if v is not None else ""


def _i(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _anio_valido(fecha) -> int | None:
    """El backup trae fechas corruptas (año 0, o del siglo que no es). Se descartan."""
    if not isinstance(fecha, datetime.date):
        return None
    return fecha.year if 1950 <= fecha.year <= datetime.date.today().year + 1 else None


def _origen(x: dict) -> str:
    """Expediente/nota de origen: viene partido en cuatro campos."""
    partes = [_s(x.get(k)) for k in ("id_tramite", "id_letra", "id_nro", "id_ano")]
    return " ".join(p for p in partes if p)


def extraer(ruta: str) -> str:
    """Devuelve la carpeta con los DBF (si subieron un ZIP, lo descomprime al lado)."""
    if not zipfile.is_zipfile(ruta):
        return os.path.dirname(ruta)
    destino = os.path.splitext(ruta)[0] + "-extraido"
    os.makedirs(destino, exist_ok=True)
    with zipfile.ZipFile(ruta) as z:
        for nombre in z.namelist():
            if nombre.lower().endswith(".dbf") and not nombre.startswith("__"):
                with z.open(nombre) as src, open(os.path.join(destino, os.path.basename(nombre)), "wb") as dst:
                    dst.write(src.read())
    return destino


def _buscar_dbf(carpeta: str, nombre: str) -> str | None:
    """El ZIP puede traer los archivos sueltos o dentro de una carpeta 'Despacho'."""
    for raiz, _dirs, archivos in os.walk(carpeta):
        for a in archivos:
            if a.lower() == nombre.lower():
                return os.path.join(raiz, a)
    return None


def procesar(import_id: int, ruta: str, session_factory=None) -> None:
    """Corre la importación entera. Pensada para ejecutarse en segundo plano."""
    propia = session_factory is None
    db = (session_factory or SessionLocal)()
    try:
        imp = db.get(ImportacionDespacho, import_id)
        if imp is None:
            return
        imp.estado = IMPORT_PROCESANDO
        db.commit()
        try:
            carpeta = extraer(ruta)
            _importar(db, imp, carpeta)
        except Exception as e:                     # noqa: BLE001 — el motivo va a la pantalla
            log.exception("Importación de despacho %s: falló", import_id)
            db.rollback()
            imp = db.get(ImportacionDespacho, import_id)
            imp.estado, imp.mensaje = IMPORT_ERROR, str(e)[:500]
            imp.terminado_en = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            return
        imp = db.get(ImportacionDespacho, import_id)
        imp.estado = IMPORT_TERMINADA
        imp.terminado_en = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    finally:
        if propia:
            db.close()


def _importar(db: Session, imp: ImportacionDespacho, carpeta: str) -> None:
    modelos_por_codigo = _importar_modelos(db, imp, carpeta)
    _importar_resoluciones(db, imp, carpeta, modelos_por_codigo)
    _importar_beneficiarios(db, imp, carpeta)


def _importar_modelos(db: Session, imp: ImportacionDespacho, carpeta: str) -> dict[int, ModeloResolucion]:
    existentes = {(m.codigo, m.tipo): m for m in db.scalars(select(ModeloResolucion)).all()}
    ruta = _buscar_dbf(carpeta, "rtf.dbf")
    nuevos = 0
    if ruta:
        with DbfReader(ruta) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                codigo = _i(x.get("cod_mod"))
                if not codigo:
                    continue
                tipo = "DIS" if x.get("disposicio") else "RES"
                if (codigo, tipo) in existentes:
                    imp.omitidas += 1
                    continue
                m = ModeloResolucion(
                    codigo=codigo, descripcion=_s(x.get("des_mod"))[:120], tipo=tipo,
                    es_seguros=bool(x.get("seguros")),
                    plantilla=rtf_a_html(x.get("modelo") or "")[:20000])
                db.add(m)
                existentes[(codigo, tipo)] = m
                nuevos += 1
        db.commit()
    imp.modelos = nuevos
    db.commit()
    # Para resolver el motivo de cada resolución: COD_MOT es el código del modelo.
    return {m.codigo: m for m in existentes.values()}


def _importar_resoluciones(db: Session, imp: ImportacionDespacho, carpeta: str,
                           modelos: dict[int, ModeloResolucion]) -> None:
    ruta = _buscar_dbf(carpeta, "resoluciones.dbf")
    if not ruta:
        raise ValueError("El archivo no trae resoluciones.dbf")
    ya = {(r.anio, r.tipo, r.numero) for r in
          db.execute(select(Resolucion.anio, Resolucion.tipo, Resolucion.numero)).all()}
    nuevas = 0
    with DbfReader(ruta) as r:
        for i, x in enumerate(r.records(), start=1):
            x = {k.lower(): v for k, v in x.items()}
            numero = _i(x.get("nro_res"))
            fecha = x.get("fec_res")
            anio = _anio_valido(fecha)
            if not numero or anio is None:
                imp.omitidas += 1
                continue
            tipo = "DIS" if x.get("disposicio") else "RES"
            if (anio, tipo, numero) in ya:       # el correlativo es único: gana el primero
                imp.omitidas += 1
                continue
            ya.add((anio, tipo, numero))

            modelo = modelos.get(_i(x.get("cod_mot")))
            motivo = (modelo.descripcion if modelo else "")[:120]
            texto = rtf_a_html(x.get("texto") or "")[:20000]
            plano = re.sub(r"<[^>]+>", " ", texto).strip()
            fecha_real = x.get("fec_real")
            db.add(Resolucion(
                numero=numero, anio=anio, tipo=tipo,
                fecha=fecha if isinstance(fecha, datetime.date) else datetime.date(anio, 1, 1),
                numero_real=_i(x.get("nro_real")) or None,
                fecha_real=fecha_real if isinstance(fecha_real, datetime.date) else None,
                asunto=(motivo or plano[:120] or f"{tipo} {numero}/{anio}")[:200],
                motivo_codigo=_i(x.get("cod_mot")), motivo=motivo,
                importe=_dec(x.get("importe")),
                modelo_id=modelo.id if modelo is not None else None,
                origen=_origen(x)[:40], nro_op=_i(x.get("nro_op")) or None,
                texto=texto,
                # Lo importado ya fue emitido en su momento: entra como firmado, no como borrador.
                estado="F", anulada=bool(x.get("lanulada")),
                creado_por="importación"))
            nuevas += 1
            if nuevas % LOTE == 0:
                imp.resoluciones = nuevas
                db.commit()
    imp.resoluciones = nuevas
    db.commit()


def _importar_beneficiarios(db: Session, imp: ImportacionDespacho, carpeta: str) -> None:
    ruta = _buscar_dbf(carpeta, "beneficiarios.dbf")
    if not ruta:
        return
    # (numero, anio, tipo) → id, para colgar cada beneficiario de su resolución.
    por_clave = {(n, a, t): i for i, n, a, t in
                 db.execute(select(Resolucion.id, Resolucion.numero, Resolucion.anio,
                                   Resolucion.tipo)).all()}
    con_beneficiarios = {b for (b,) in db.execute(
        select(ResolucionBeneficiario.resolucion_id).distinct()).all()}
    nuevos = 0
    with DbfReader(ruta) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            numero = _i(x.get("nro_res"))
            fecha = x.get("fec_res")
            anio = _anio_valido(fecha)
            if not numero or anio is None:
                continue
            tipo = "DIS" if x.get("disposicio") else "RES"
            rid = por_clave.get((numero, anio, tipo))
            if rid is None or rid in con_beneficiarios:
                continue                          # sin su resolución, o ya cargados: no se duplica
            db.add(ResolucionBeneficiario(
                resolucion_id=rid, tipo_doc=_i(x.get("tipo_doc")),
                nro_doc=_s(x.get("nro_doc"))[:11], nombre=_s(x.get("nombre"))[:80],
                tipo_bene=_i(x.get("tipo_bene")), importe=_dec(x.get("importe"))))
            nuevos += 1
            if nuevos % LOTE == 0:
                imp.beneficiarios = nuevos
                db.commit()
    imp.beneficiarios = nuevos
    db.commit()


def marcar_interrumpidas(db: Session) -> int:
    """Al arrancar: lo que quedó PROCESANDO murió con el proceso anterior."""
    filas = db.scalars(select(ImportacionDespacho)
                       .where(ImportacionDespacho.estado == IMPORT_PROCESANDO)).all()
    for f in filas:
        f.estado = IMPORT_INTERRUMPIDA
        f.mensaje = "El módulo se reinició mientras se importaba. Volvé a subir el archivo."
        f.terminado_en = datetime.datetime.now(datetime.timezone.utc)
    if filas:
        db.commit()
    return len(filas)
