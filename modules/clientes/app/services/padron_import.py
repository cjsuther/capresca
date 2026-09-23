"""Importación del padrón de clientes del sistema anterior (maeclientes.dbf).

Cómo funciona
-------------
El archivo se sube por la web (ZIP o DBF suelto), se guarda en disco y se procesa **en segundo
plano**: son ~78.000 registros y ninguna respuesta HTTP puede esperar eso (el gateway corta a los
120 s). La pantalla consulta el avance cada pocos segundos.

Unificación
-----------
En el sistema viejo la MISMA persona aparece una vez por organismo/categoría: el `CIDCLIENTE` es
prefijo + CUIL (ACA…, AGC…, AGJ…, ECA…). Por eso el padrón se unifica por **CUIL** (y por DNI cuando
no hay CUIL): una persona = un cliente, y cada fila del DBF queda como `ClientLegacyRef` para no
perder el vínculo con lo viejo.

Qué se pisa y qué no
--------------------
- Identidad y contacto (nombre, nacimiento, sexo, domicilio, teléfono, email): sólo se completan si
  están vacíos. El operador puede haber corregido a mano algo que en el padrón viejo está mal.
- Datos del padrón (organismo, categoría, sueldo, situación, baja): se actualizan siempre, porque de
  eso el maestro viejo ES la fuente de verdad.
- CBU: se agrega si el cliente no lo tenía. Nunca se pisa ni se desactiva uno cargado.

Es idempotente: volver a subir el mismo archivo no duplica nada.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (Client, ClientCbu, ClientImport, ClientImportRechazo, ClientLegacyRef,
                        ClientPadron, ClientType, HumanClient, IMPORT_ERROR, IMPORT_INTERRUMPIDA,
                        IMPORT_PROCESANDO, IMPORT_TERMINADA)
from app.services.dbf import DbfReader

log = logging.getLogger("clientes.padron")

LOTE = 500                      # registros por commit: avance visible sin castigar a la base


class Indices:
    """Lo que hay que buscar por cada registro, en memoria.

    Con una consulta por búsqueda eran 5,3 consultas por registro (medido) y, peor, el trabajo crecía
    con el tamaño de la tabla: la importación arrancaba rápido y se iba frenando. Se carga una vez lo
    que hace falta —CUIL y DNI ya cargados, referencias al sistema viejo, CBUs y quién ya tiene ficha
    de padrón— y durante la corrida se consulta y se actualiza acá.
    """

    def __init__(self, db: Session):
        self.cuil = dict(db.query(HumanClient.cuil, HumanClient.client_id)
                           .filter(HumanClient.cuil.isnot(None)).all())
        self.dni = dict(db.query(HumanClient.document_number, HumanClient.client_id)
                          .filter(HumanClient.document_number.isnot(None)).all())
        self.refs = {r for (r,) in db.query(ClientLegacyRef.cidcliente).all()}
        self.cbus = {c for (c,) in db.query(ClientCbu.cbu).all()}
        self.padrones = {c for (c,) in db.query(ClientPadron.client_id).all()}
        self._nuevos: list[tuple[str, str]] = []

    def agregar(self, coleccion: str, clave, valor=None) -> None:
        obj = getattr(self, coleccion)
        if isinstance(obj, dict):
            obj[clave] = valor
        else:
            obj.add(clave)
        self._nuevos.append((coleccion, clave))

    def marca(self) -> int:
        return len(self._nuevos)

    def deshacer(self, marca: int) -> None:
        """Un lote que se dio marcha atrás no puede dejar sus claves en los índices."""
        while len(self._nuevos) > marca:
            coleccion, clave = self._nuevos.pop()
            obj = getattr(self, coleccion)
            obj.pop(clave, None) if isinstance(obj, dict) else obj.discard(clave)


@dataclass
class Ctx:
    """Lo único que el proceso necesita saber de la importación. Se pasa como datos sueltos y no como
    la fila de la base, que no puede quedar adjunta a la sesión (se vacía después de cada lote)."""
    id: int
    usuario_id: int | None
DIR_IMPORTS = os.getenv("PADRON_IMPORT_DIR", "/data/padron")


# --------------------------------------------------------------------------- normalización
def _s(v) -> str:
    return str(v).strip() if v is not None else ""


def _digitos(v) -> str:
    return re.sub(r"\D", "", _s(v))


def _dec(v):
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def partir_nombre(apenom: str) -> tuple[str, str]:
    """"PEREZ, JUAN CARLOS" → ("PEREZ", "JUAN CARLOS"). Sin coma, la primera palabra es el apellido.

    El padrón viejo usa las dos formas ("CORDOBA, EDGARDO ADRIAN" y "BORDON FLAVIO LAZARO")."""
    apenom = " ".join(apenom.split())
    if "," in apenom:
        ape, _, nom = apenom.partition(",")
        return ape.strip(), nom.strip()
    partes = apenom.split(" ")
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], " ".join(partes[1:])


def clave_persona(cuil: str, dni: str) -> tuple[str, str] | None:
    """Con qué se unifica: el CUIL si es válido, si no el DNI. None = no se puede identificar."""
    if len(cuil) == 11:
        return ("CUIL", cuil)
    if 6 <= len(dni) <= 8:
        return ("DNI", dni)
    return None


# --------------------------------------------------------------------------- archivo
def extraer_dbf(ruta: str) -> str:
    """Devuelve la ruta del .dbf: si subieron un ZIP, saca el primer .dbf al lado del archivo."""
    if not zipfile.is_zipfile(ruta):
        return ruta
    with zipfile.ZipFile(ruta) as z:
        dbfs = [n for n in z.namelist() if n.lower().endswith(".dbf")]
        if not dbfs:
            raise ValueError("El ZIP no contiene ningún archivo .dbf")
        destino = os.path.join(os.path.dirname(ruta), os.path.basename(dbfs[0]))
        with z.open(dbfs[0]) as src, open(destino, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        return destino


CAMPOS_MINIMOS = {"cidcliente", "ccuil", "capenom"}


def validar_estructura(reader: DbfReader) -> None:
    faltan = CAMPOS_MINIMOS - {f.name.lower() for f in reader.fields}
    if faltan:
        raise ValueError("El archivo no parece el padrón de clientes: faltan los campos "
                         + ", ".join(sorted(faltan)).upper())


# --------------------------------------------------------------------------- proceso
def procesar(import_id: int, ruta: str, session_factory=None) -> None:
    """Corre la importación entera. Pensado para ejecutarse en segundo plano.

    `session_factory` existe para los tests: el hilo abre su propia sesión, que no es la del request.
    Cuando la sesión la trae el que llama, es suyo cerrarla."""
    propia = session_factory is None
    db = (session_factory or SessionLocal)()
    try:
        imp = db.get(ClientImport, import_id)
        if imp is None:
            return
        imp.estado = IMPORT_PROCESANDO
        db.commit()
        try:
            dbf = extraer_dbf(ruta)
            with DbfReader(dbf) as r:
                validar_estructura(r)
                imp.total = r.record_count
                db.commit()
                ctx = Ctx(id=imp.id, usuario_id=imp.usuario_id)
                db.expunge_all()
                _importar(db, ctx, r)
                imp = db.get(ClientImport, import_id)
        except Exception as e:                       # noqa: BLE001 — el motivo va a la pantalla
            log.exception("Importación %s: falló", import_id)
            db.rollback()
            imp = db.get(ClientImport, import_id)     # la sesión se vacía por lote: hay que volver a traerla
            imp.estado, imp.mensaje = IMPORT_ERROR, str(e)[:500]
            imp.terminado_en = datetime.now(timezone.utc)
            db.commit()
            return
        imp.estado = IMPORT_TERMINADA
        imp.terminado_en = datetime.now(timezone.utc)
        db.commit()
    finally:
        if propia:
            db.close()


def _importar(db: Session, imp: Ctx, reader: DbfReader) -> None:
    """Procesa el archivo de a lotes.

    Un SAVEPOINT por lote (rápido) y, si el lote falla por una fila mala, se rehace ese lote fila por
    fila para dejar afuera sólo la culpable. Con un SAVEPOINT por fila de entrada, Postgres se iba a
    ~30 registros por segundo; así va más de diez veces más rápido y el resultado es el mismo.
    """
    # Lo ya visto en ESTE archivo: la misma persona viene varias veces y así no se consulta la base
    # una vez por fila. cache[clave] = (id del cliente, si lo creamos en esta corrida)
    cache: dict[tuple[str, str], tuple[int, bool]] = {}
    marcador = _Marcador()
    idx = Indices(db)

    lote: list[tuple[int, dict]] = []
    for fila, row in enumerate(reader.records(), start=1):
        lote.append((fila, {k.lower(): v for k, v in row.items()}))
        if len(lote) >= LOTE:
            _procesar_lote(db, imp, lote, cache, marcador, idx)
            lote = []
    if lote:
        _procesar_lote(db, imp, lote, cache, marcador, idx)


class _Marcador:
    """Los contadores de la importación, que se van guardando para que la pantalla muestre el avance."""
    def __init__(self):
        self.procesados = self.creados = self.actualizados = self.rechazados = 0

    def sumar(self, resultado: str) -> None:
        self.procesados += 1
        if resultado == "creado":
            self.creados += 1
        elif resultado == "actualizado":
            self.actualizados += 1
        elif resultado == "rechazado":
            self.rechazados += 1

    def volcar(self, db: Session, import_id: int) -> None:
        db.query(ClientImport).filter(ClientImport.id == import_id).update(
            {"procesados": self.procesados, "creados": self.creados,
             "actualizados": self.actualizados, "rechazados": self.rechazados})


def _procesar_lote(db: Session, imp: Ctx, lote: list, cache: dict, marcador: _Marcador,
                   idx: Indices) -> None:
    antes, marca = dict(cache), idx.marca()
    estado = (marcador.procesados, marcador.creados, marcador.actualizados, marcador.rechazados)
    try:
        with db.begin_nested():
            for fila, row in lote:
                marcador.sumar(_fila(db, imp, row, cache, fila, idx))
    except Exception as e:                       # noqa: BLE001 — alguna fila del lote no entró
        log.warning("Importación %s: el lote que termina en la fila %s falló (%s); se rehace fila "
                    "por fila", imp.id, lote[-1][0], e)
        db.rollback()
        cache.clear()
        cache.update(antes)                      # lo que se deshizo no puede quedar cacheado
        idx.deshacer(marca)
        (marcador.procesados, marcador.creados,
         marcador.actualizados, marcador.rechazados) = estado
        for fila, row in lote:
            marca_fila = idx.marca()
            try:
                with db.begin_nested():
                    resultado = _fila(db, imp, row, cache, fila, idx)
            except Exception as err:             # noqa: BLE001 — sólo cae esta fila
                log.warning("Importación %s, fila %s: %s", imp.id, fila, err)
                db.rollback()
                idx.deshacer(marca_fila)
                cache.pop(_clave_de(row), None)
                _rechazar(db, imp, fila, row, f"No se pudo importar: {err}"[:120])
                resultado = "rechazado"
            marcador.sumar(resultado)
    marcador.volcar(db, imp.id)
    db.commit()
    # Sin esto, cada lote deja sus objetos en la sesión y los flush siguientes los recorren todos:
    # la importación arranca a 700 registros por segundo y termina a 10.
    db.expunge_all()


def _clave_de(row: dict):
    return clave_persona(_digitos(row.get("ccuil")), _digitos(row.get("edni")).lstrip("0"))


def _rechazar(db: Session, imp: Ctx, fila: int, row: dict, motivo: str) -> None:
    db.add(ClientImportRechazo(
        import_id=imp.id, fila=fila, cidcliente=_s(row.get("cidcliente"))[:15],
        documento=(_digitos(row.get("ccuil")) or _digitos(row.get("edni")))[:20],
        nombre=_s(row.get("capenom"))[:60], motivo=motivo[:120]))


def _fila(db: Session, imp: Ctx, row: dict, cache: dict, fila: int, idx: Indices) -> str:
    cuil = _digitos(row.get("ccuil"))
    dni = _digitos(row.get("edni")).lstrip("0")
    apenom = _s(row.get("capenom"))
    clave = clave_persona(cuil, dni)
    if clave is None:
        _rechazar(db, imp, fila, row, "Sin CUIL ni DNI válidos")
        return "rechazado"
    if not apenom:
        _rechazar(db, imp, fila, row, "Sin apellido y nombre")
        return "rechazado"

    # cache[clave] = (id del cliente, si lo creamos en esta misma corrida)
    en_cache = cache.get(clave)
    nuevo = False
    if en_cache is None:
        client_id = idx.cuil.get(cuil) or idx.dni.get(dni)
        if client_id is None:
            client_id = _crear(db, row, clave, cuil, dni, apenom, imp)
            nuevo = True
            if cuil:
                idx.agregar("cuil", cuil, client_id)
            if dni:
                idx.agregar("dni", dni, client_id)
        cache[clave] = (client_id, nuevo)
    else:
        client_id, nuevo_antes = en_cache
        # Lo que creamos recién ya tiene todo lo que trae el archivo: no hay nada que completar.
        if not nuevo_antes:
            _completar(db, client_id, row, cuil, dni, apenom)
    if not nuevo and en_cache is None:
        _completar(db, client_id, row, cuil, dni, apenom)
    _padron(db, client_id, row, idx)
    _cbu(db, client_id, row, imp, idx)
    _legacy_ref(db, client_id, row, imp, idx)
    return "creado" if nuevo else "actualizado"


def _codigo(clave: tuple[str, str]) -> str:
    """Código visible del cliente. Sale de la clave con la que se unifica el padrón (PAD + CUIL o
    PAD-DNI): es único por construcción y no cuesta una consulta por alta."""
    tipo, valor = clave
    return f"PAD{valor}" if tipo == "CUIL" else f"PAD-{valor}"


def _crear(db: Session, row: dict, clave: tuple[str, str], cuil: str, dni: str, apenom: str,
           imp: Ctx) -> int:
    apellido, nombres = partir_nombre(apenom)
    cliente = Client(
        client_type=ClientType.HUMAN, code=_codigo(clave),
        email=_s(row.get("cemail"))[:255] or None,
        phone=_s(row.get("ctelefono"))[:64] or None,
        address=_s(row.get("cdomicilio"))[:255] or None,
        neighborhood=_s(row.get("cbarrio"))[:64] or None,
        city=_s(row.get("clocalidad"))[:128] or None,
        department=_s(row.get("cdepto"))[:64] or None,
        postal_code=_s(row.get("ccpa"))[:12] or None,
        country="AR",
        is_active=not bool(row.get("lbaja")),
        created_by_user_id=imp.usuario_id,
    )
    db.add(cliente)
    db.flush()
    nac = row.get("fnacim")
    db.add(HumanClient(
        client_id=cliente.id, first_name=nombres or "-", last_name=apellido or "-",
        document_type="DNI", document_number=dni or None, cuil=cuil or None,
        birth_date=str(nac) if nac else None,
        gender=_s(row.get("csexo"))[:16] or None,
    ))
    return cliente.id


def _completar(db: Session, client_id: int, row: dict, cuil: str, dni: str, apenom: str) -> None:
    """Rellena lo que falte; no pisa lo que ya está cargado (puede haberse corregido a mano)."""
    cliente = db.get(Client, client_id)
    perfil = db.query(HumanClient).filter(HumanClient.client_id == client_id).first()
    if cliente is not None:
        for campo, valor in (("email", _s(row.get("cemail"))[:255]),
                             ("phone", _s(row.get("ctelefono"))[:64]),
                             ("address", _s(row.get("cdomicilio"))[:255]),
                             ("neighborhood", _s(row.get("cbarrio"))[:64]),
                             ("city", _s(row.get("clocalidad"))[:128]),
                             ("department", _s(row.get("cdepto"))[:64]),
                             ("postal_code", _s(row.get("ccpa"))[:12])):
            if valor and not getattr(cliente, campo):
                setattr(cliente, campo, valor)
    if perfil is not None:
        if cuil and not perfil.cuil:
            perfil.cuil = cuil
        if dni and not perfil.document_number:
            perfil.document_number = dni
        nac = row.get("fnacim")
        if nac and not perfil.birth_date:
            perfil.birth_date = str(nac)
        if not perfil.gender:
            perfil.gender = _s(row.get("csexo"))[:16] or None


def _padron(db: Session, client_id: int, row: dict, idx: Indices) -> None:
    """Datos de revista: acá el maestro viejo manda, así que se actualizan siempre.

    Va por sentencia directa (sin objeto del ORM): son 78.000 filas y la sesión no tiene que
    quedarse con ninguna."""
    valores = {
        "organismo_numero": _int(row.get("norgano")),
        "organismo_codigo": _s(row.get("corga"))[:3] or None,
        "categoria_numero": _int(row.get("ncatfun")),
        "categoria": _s(row.get("ccatfun"))[:40] or None,
        "sueldo": _dec(row.get("nsueldo")),
        "fecha_ingreso": row.get("ffperm"),
        "tipo_cliente": _int(row.get("ntipocli")),
        "situacion": _int(row.get("nsituacion")),
        "agente": _int(row.get("eagente")),
        "sucursal": _int(row.get("esucursal")),
        "cuenta": _int(row.get("ecuenta")),
        "beneficio": _s(row.get("cbenef"))[:20] or None,
        "debito_automatico": bool(row.get("ldebauto")),
        "baja": bool(row.get("lbaja")),
        "fecha_baja": row.get("fecbaja"),
        "motivo_baja": _s(row.get("cmotbaja"))[:60] or None,
    }
    tabla = ClientPadron.__table__
    if client_id in idx.padrones:
        db.execute(tabla.update().where(tabla.c.client_id == client_id).values(**valores))
    else:
        db.execute(tabla.insert().values(client_id=client_id, **valores))
        idx.agregar("padrones", client_id)


def _cbu(db: Session, client_id: int, row: dict, imp: Ctx, idx: Indices) -> None:
    cbu = _digitos(row.get("ccbucta"))
    if len(cbu) != 22 or cbu in idx.cbus:
        return                       # el CBU es único en toda la tabla: si ya está, no se toca
    db.execute(ClientCbu.__table__.insert().values(
        client_id=client_id, cbu=cbu, description="Padrón CCyPP", is_active=True,
        is_payment_account=False, created_by=imp.usuario_id or 0))
    idx.agregar("cbus", cbu)


def _legacy_ref(db: Session, client_id: int, row: dict, imp: Ctx, idx: Indices) -> None:
    cid = _s(row.get("cidcliente"))[:15]
    if not cid:
        return
    valores = {"client_id": client_id, "organismo_numero": _int(row.get("norgano")),
               "beneficio": _s(row.get("cbenef"))[:20] or None,
               "tipo_cliente": _int(row.get("ntipocli")), "importacion_id": imp.id}
    tabla = ClientLegacyRef.__table__
    if cid in idx.refs:              # el CIDCLIENTE viene repetido en el padrón real (156 casos)
        db.execute(tabla.update().where(tabla.c.cidcliente == cid).values(**valores))
    else:
        db.execute(tabla.insert().values(cidcliente=cid, **valores))
        idx.agregar("refs", cid)


# --------------------------------------------------------------------------- arranque / salida
def marcar_interrumpidas(db: Session) -> int:
    """Al arrancar el módulo: lo que quedó PROCESANDO murió con el proceso anterior. Los clientes que
    alcanzó a crear quedan; volver a subir el archivo completa el resto sin duplicar."""
    filas = db.query(ClientImport).filter(ClientImport.estado == IMPORT_PROCESANDO).all()
    for f in filas:
        f.estado = IMPORT_INTERRUMPIDA
        f.mensaje = "El módulo se reinició mientras se importaba. Volvé a subir el archivo."
        f.terminado_en = datetime.now(timezone.utc)
    if filas:
        db.commit()
    return len(filas)


def rechazos_csv(db: Session, import_id: int) -> str:
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["fila", "cidcliente", "documento", "nombre", "motivo"])
    for r in (db.query(ClientImportRechazo)
                .filter(ClientImportRechazo.import_id == import_id)
                .order_by(ClientImportRechazo.fila).all()):
        w.writerow([r.fila, r.cidcliente or "", r.documento or "", r.nombre or "", r.motivo])
    return salida.getvalue()
