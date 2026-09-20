"""Servicios del módulo Despacho: resoluciones/disposiciones y expedientes (pases)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


class ReglaNegocioError(Exception):
    pass


# ---------------- Resoluciones / Disposiciones ----------------
def _proximo_numero_resol(db: Session, anio: int, tipo: str) -> int:
    n = db.scalar(select(func.max(models.Resolucion.numero)).where(
        models.Resolucion.anio == anio, models.Resolucion.tipo == tipo))
    return (n or 0) + 1


def crear_resolucion(db: Session, *, tipo: str, asunto: str, texto: str, organo: str,
                     fecha: date | None = None, modelo_id: int | None = None,
                     modelo_codigo: int | None = None, importe: Decimal | float = 0, origen: str = "",
                     beneficiarios: list[dict] | None = None) -> models.Resolucion:
    tipo = (tipo or "RES").upper()
    if tipo not in ("RES", "DIS"):
        raise ReglaNegocioError("Tipo inválido (RES o DIS)")
    f = fecha or date.today()
    # "Modelo a utilizar": su descripción es el MOTIVO y, si no vino texto, su plantilla es el cuerpo base.
    # El id es único (el COD_MOD se repite entre tipos); si sólo vino el código, se resuelve por código.
    motivo_cod, motivo = 0, ""
    m = None
    if modelo_id:
        m = db.get(models.ModeloResolucion, modelo_id)
        if not m:
            raise ReglaNegocioError("Modelo de resolución inexistente")
    elif modelo_codigo:
        m = db.scalar(select(models.ModeloResolucion).where(models.ModeloResolucion.codigo == modelo_codigo))
        if not m:
            raise ReglaNegocioError("Modelo de resolución inexistente")
    if m is not None:
        modelo_codigo = m.codigo
        motivo_cod, motivo = m.codigo, m.descripcion
        if not (texto or "").strip():
            texto = m.plantilla or ""
    if not (asunto or "").strip():
        asunto = (texto[:120].strip() or f"{tipo} {f.year}")
    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        r = models.Resolucion(numero=n, anio=f.year, tipo=tipo, fecha=f, organo=organo,
                              asunto=asunto[:200], texto=texto or "", estado="B",
                              motivo_cod=motivo_cod, motivo=(motivo or "")[:120],
                              importe=Decimal(str(importe or 0)), modelo_codigo=modelo_codigo,
                              origen=(origen or "")[:40])
        db.add(r); db.flush()
        for b in (beneficiarios or []):
            db.add(models.ResolucionBeneficiario(
                resolucion_id=r.id, tipo_doc=int(b.get("tipo_doc") or 0),
                nro_doc=str(b.get("nro_doc") or "")[:11], nombre=str(b.get("nombre") or "")[:80],
                tipo_bene=int(b.get("tipo_bene") or 0)))
        return r
    r = crear_con_numero_unico(db, lambda: _proximo_numero_resol(db, f.year, tipo), _construir)  # árbitro DB (H-108)
    db.commit()
    db.refresh(r)
    return r


def editar_resolucion(db: Session, *, resol_id: int, fecha: date | None = None,
                      modelo_id: int | None = None, modelo_codigo: int | None = None,
                      texto: str | None = None, importe: Decimal | float | None = None,
                      origen: str | None = None, beneficiarios: list[dict] | None = None) -> models.Resolucion:
    """Edita un BORRADOR. Un instrumento OFICIAL (firmado / con Nº Real) o ANULADO es inmutable
    (no se cambia un acto ya emitido). No cambia tipo/número/año (rompería la serie del correlativo)."""
    import re
    r = db.get(models.Resolucion, resol_id)
    if not r:
        raise ReglaNegocioError("Resolución inexistente")
    if r.anulada:
        raise ReglaNegocioError("La resolución está anulada; no se puede editar")
    if r.estado == "F" or r.numero_real:
        raise ReglaNegocioError("La resolución es oficial (firmada o con Nº Real); no se puede editar")
    # "Modelo a utilizar": su descripción es el MOTIVO; si el texto queda vacío, su plantilla es el cuerpo.
    if modelo_id or modelo_codigo:
        m = (db.get(models.ModeloResolucion, modelo_id) if modelo_id
             else db.scalar(select(models.ModeloResolucion).where(models.ModeloResolucion.codigo == modelo_codigo)))
        if not m:
            raise ReglaNegocioError("Modelo de resolución inexistente")
        r.modelo_codigo = m.codigo
        r.motivo_cod, r.motivo = m.codigo, (m.descripcion or "")[:120]
        if texto is not None and not texto.strip():
            texto = m.plantilla or ""
    if fecha is not None:
        if fecha.year != r.anio:
            raise ReglaNegocioError("No se puede cambiar el año de la resolución")
        r.fecha = fecha
    if texto is not None:
        r.texto = texto or ""
    if importe is not None:
        r.importe = Decimal(str(importe or 0))
    if origen is not None:
        r.origen = (origen or "")[:40]
    # asunto derivado (mismo criterio que el alta): plano del texto, o tipo+año
    plano = re.sub(r"<[^>]+>", " ", r.texto or "").strip()
    r.asunto = (plano[:120].strip() or f"{r.tipo} {r.anio}")[:200]
    if beneficiarios is not None:  # reemplaza la grilla completa
        for b in list(r.beneficiarios):
            db.delete(b)
        db.flush()
        for b in beneficiarios:
            db.add(models.ResolucionBeneficiario(
                resolucion_id=r.id, tipo_doc=int(b.get("tipo_doc") or 0),
                nro_doc=str(b.get("nro_doc") or "")[:11], nombre=str(b.get("nombre") or "")[:80],
                tipo_bene=int(b.get("tipo_bene") or 0)))
    db.commit(); db.refresh(r)
    return r


def _proximo_numero_real(db: Session, anio: int, tipo: str) -> int:
    """Nº Real = MAX(numero_real)+1 por tipo y año (secuencial oficial; VFP form7). Arranca en 1."""
    n = db.scalar(select(func.max(models.Resolucion.numero_real)).where(
        models.Resolucion.tipo == tipo, models.Resolucion.anio == anio))
    return (n or 0) + 1


def asignar_numero_real(db: Session, resol_id: int, fecha_real: date | None = None) -> models.Resolucion:
    """Carga el Nº Real oficial (pantalla VFP "Carga Nº Real de RESOLUCIÓN")."""
    r = db.get(models.Resolucion, resol_id)
    if not r:
        raise ReglaNegocioError("Resolución inexistente")
    if r.numero_real:
        raise ReglaNegocioError(f"La resolución ya tiene Nº Real ({r.numero_real}).")
    freal = fecha_real or date.today()
    r.numero_real = _proximo_numero_real(db, freal.year, r.tipo)
    r.fecha_real = freal
    r.estado = "F"
    db.commit(); db.refresh(r)
    return r


def firmar_resolucion(db: Session, resol_id: int) -> models.Resolucion:
    r = db.get(models.Resolucion, resol_id)
    if not r:
        raise ReglaNegocioError("Resolución inexistente")
    if r.estado == "F":
        raise ReglaNegocioError("La resolución ya está firmada")
    r.estado = "F"
    db.commit()
    db.refresh(r)
    return r


# ---------------- Anexo de Resolución (reconstruido del fuente VFP, H-026) ----------------
# Tipo de anexo -> rango de líneas de crédito (del método m_obtiene_datos del
# form 120100000anexo_res_dis). Cartera GAS se filtra aparte (cartera=11).
TIPO_ANEXO = {
    1: {"nombre": "AGAP", "linea_min": 8050, "linea_max": 8051},
    2: {"nombre": "Microcréditos", "linea_min": 6810, "linea_max": 6813},
    3: {"nombre": "Productivos", "linea_min": 6800, "linea_max": 6801},
    4: {"nombre": "Vivienda", "linea_min": 8130, "linea_max": 8133},
    5: {"nombre": "Gas", "cartera": 11},
    6: {"nombre": "Resto", "todos": True},
}


def _filtro_tipo_anexo(base, tipo: int):
    S = models.SolicitudCredito
    cfg = TIPO_ANEXO.get(tipo, TIPO_ANEXO[6])
    if cfg.get("todos"):
        return base
    if "cartera" in cfg:  # GAS: por cartera de la línea
        lineas = select(models.LineaCredito.id).where(models.LineaCredito.cartera == cfg["cartera"])
        return base.where(S.linea.in_(lineas))
    return base.where(S.linea.between(cfg["linea_min"], cfg["linea_max"]))


def solicitudes_para_anexo(db: Session, tipo: int, *, lote: int | None = None) -> dict:
    """Solicitudes candidatas al anexo (estado A, cubica C/DC, sin resolución) del
    tipo dado; o las de un `lote` ya asignado (reimpresión). VFP: m_obtiene_datos."""
    S = models.SolicitudCredito
    L = models.LineaCredito
    base = select(S, L.nombre).outerjoin(L, L.id == S.linea)
    if lote:
        base = base.where(S.lote == lote, S.en_reso.is_(True))
    else:
        base = base.where(S.estado == "A", S.cubica.in_(("C", "DC")),
                          S.no_resol == 0, S.en_reso.is_(False))
        base = _filtro_tipo_anexo(base, tipo)
    filas, total = [], Decimal("0")
    for s, linea_nom in db.execute(base.order_by(S.linea, S.apellido_nombre)).all():
        total += s.montosol
        filas.append({
            "no_solicitud": s.id, "fecha_soli": s.fecha_soli, "cuil": s.cuil,
            "apellido_nombre": s.apellido_nombre, "montosol": s.montosol,
            "no_credpp": s.no_credpp, "importepp": s.importepp, "linea": s.linea,
            "denominacion": linea_nom or "", "en_reso": s.en_reso, "lote": s.lote,
        })
    return {"tipo": tipo, "nombre": TIPO_ANEXO.get(tipo, {}).get("nombre", ""),
            "cantidad": len(filas), "total": total, "items": filas}


def asignar_anexo(db: Session, *, tipo: int, numero: int, fecha: date,
                  solicitud_ids: list[int]) -> dict:
    """Asigna las solicitudes seleccionadas a la resolución (lote = N° correlativo),
    marcando en_reso/no_resol/fecha_resol. VFP: Command1 'Vista Previa'."""
    if not numero:
        raise ReglaNegocioError("Ingresá el N° correlativo de la resolución")
    if not solicitud_ids:
        raise ReglaNegocioError("Seleccioná al menos una solicitud")
    sols = db.scalars(select(models.SolicitudCredito)
                      .where(models.SolicitudCredito.id.in_(solicitud_ids))).all()
    for s in sols:
        if s.en_reso and s.lote != numero:
            raise ReglaNegocioError(f"La solicitud {s.id} ya está en otra resolución (lote {s.lote})")
    for s in sols:
        s.lote = numero
        s.en_reso = True
        s.no_resol = numero
        s.fecha_resol = fecha
    db.commit()
    return {"tipo": tipo, "numero": numero, "fecha": fecha,
            "asignadas": len(sols), "total": sum((s.montosol for s in sols), Decimal("0"))}


# ---------------- Expedientes y pases ----------------
def crear_expediente(db: Session, *, numero: str, caratula: str, iniciador: str,
                     oficina_inicial: str, fecha: date | None = None) -> models.Expediente:
    # El N° de expediente lo tipea la persona (viene del papel/mesa de entradas): NO se autogenera.
    # Chequeo amistoso + la CONSTRAINT única como árbitro real (mismo criterio que el CUIL, H-154): dos
    # altas concurrentes con el mismo número no crean duplicado; la 2ª cae en IntegrityError → 409 (no 500).
    if db.scalar(select(models.Expediente).where(models.Expediente.numero == numero)):
        raise ReglaNegocioError("Ya existe un expediente con ese número")
    f = fecha or date.today()
    exp = models.Expediente(
        numero=numero, caratula=caratula, iniciador=iniciador,
        fecha_inicio=f, estado="T", oficina_actual=oficina_inicial,
    )
    db.add(exp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ReglaNegocioError("Ya existe un expediente con ese número")
    # pase inicial (alta en la oficina iniciadora)
    db.add(models.Pase(expediente_id=exp.id, orden=1, fecha=f,
                       oficina_origen="", oficina_destino=oficina_inicial,
                       motivo="Inicio de expediente", usuario=iniciador))
    db.commit()
    db.refresh(exp)
    return exp


def pasar_expediente(db: Session, exp_id: int, *, oficina_destino: str,
                     motivo: str, usuario: str, fecha: date | None = None) -> models.Pase:
    exp = db.get(models.Expediente, exp_id)
    if not exp:
        raise ReglaNegocioError("Expediente inexistente")
    if exp.estado == "A":
        raise ReglaNegocioError("El expediente está archivado")
    orden = (db.scalar(select(func.max(models.Pase.orden)).where(
        models.Pase.expediente_id == exp_id)) or 0) + 1
    pase = models.Pase(
        expediente_id=exp_id, orden=orden, fecha=fecha or date.today(),
        oficina_origen=exp.oficina_actual, oficina_destino=oficina_destino,
        motivo=motivo, usuario=usuario,
    )
    db.add(pase)
    exp.oficina_actual = oficina_destino
    db.commit()
    db.refresh(pase)
    return pase


def archivar_expediente(db: Session, exp_id: int, usuario: str) -> models.Expediente:
    exp = db.get(models.Expediente, exp_id)
    if not exp:
        raise ReglaNegocioError("Expediente inexistente")
    exp.estado = "A"
    db.commit()
    db.refresh(exp)
    return exp
