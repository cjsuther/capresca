"""Maestro de feriados por país (calendario de días no laborables).

Lo consume el motor de cronograma para no fechar vencimientos en días inhábiles cuando el
producto ajusta a día hábil. Se puede cargar/editar manualmente o **importar de una fuente
oficial** (Nager.Date, agregador público de feriados por país). Si la fuente no está
disponible, cae a un cálculo local: feriados nacionales de fecha fija + los basados en Pascua
(Carnaval y Viernes Santo para Argentina).
"""
import json
import urllib.request
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permisos import requiere_permiso
from app.deps import get_current_user
from app import models

router = APIRouter(prefix="/api/creditos/feriados", tags=["feriados"],
                   dependencies=[Depends(get_current_user)])

# H-156: las escrituras del calendario exigen nivel ESCRITURA sobre "/contabilidad/feriados" (enforcement
# RBAC en el backend, no sólo en el front). ADMG y roles sin RBAC configurado pasan (sin_restricciones).
_req_escritura_feriado = requiere_permiso("/contabilidad/feriados", "ESCRITURA")

# Países soportados por el maestro (código ISO alpha-2 + nombre).
PAISES = [
    {"codigo": "AR", "nombre": "Argentina"},
    {"codigo": "UY", "nombre": "Uruguay"},
    {"codigo": "CL", "nombre": "Chile"},
    {"codigo": "BR", "nombre": "Brasil"},
    {"codigo": "MX", "nombre": "México"},
    {"codigo": "ES", "nombre": "España"},
]

# Feriados nacionales argentinos de FECHA FIJA (mes, día, nombre).
_AR_FIJOS = [
    (1, 1, "Año Nuevo"), (3, 24, "Día de la Memoria"), (4, 2, "Malvinas"),
    (5, 1, "Día del Trabajador"), (5, 25, "Revolución de Mayo"),
    (7, 9, "Día de la Independencia"), (12, 8, "Inmaculada Concepción"),
    (12, 25, "Navidad"),
]


def _pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo de Butcher/Meeus, calendario gregoriano)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * mm + 114) // 31
    dia = ((h + l - 7 * mm + 114) % 31) + 1
    return date(anio, mes, dia)


def _ar_calculados(anio: int) -> list[tuple[date, str, str]]:
    """(fecha, nombre, tipo) de feriados AR: fijos + basados en Pascua."""
    out = [(date(anio, m, d), n, "INAMOVIBLE") for m, d, n in _AR_FIJOS]
    pascua = _pascua(anio)
    out.append((pascua - timedelta(days=2), "Viernes Santo", "TRASLADABLE"))
    out.append((pascua - timedelta(days=48), "Carnaval (lunes)", "TRASLADABLE"))
    out.append((pascua - timedelta(days=47), "Carnaval (martes)", "TRASLADABLE"))
    return out


def _desde_nager(pais: str, anio: int) -> list[tuple[date, str, str]] | None:
    """Intenta la fuente oficial pública Nager.Date. None si no está disponible."""
    url = f"https://date.nager.at/api/v3/PublicHolidays/{anio}/{pais}"
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        out = []
        for h in data:
            f = date.fromisoformat(h["date"])
            nombre = h.get("localName") or h.get("name") or "Feriado"
            tipo = "INAMOVIBLE" if h.get("fixed") else "TRASLADABLE"
            out.append((f, nombre, tipo))
        return out or None
    except Exception:
        return None


class FeriadoIn(BaseModel):
    pais: str = "AR"
    fecha: date
    nombre: str
    tipo: str = "INAMOVIBLE"
    activo: bool = True


class ImportarIn(BaseModel):
    pais: str = "AR"
    anio: int


def _serial(f: models.Feriado) -> dict:
    return {"id": f.id, "pais": f.pais, "fecha": str(f.fecha), "nombre": f.nombre,
            "tipo": f.tipo, "origen": f.origen, "activo": f.activo}


@router.get("/paises")
def paises():
    return {"items": PAISES}


@router.get("")
def listar(pais: str = Query("AR"), anio: int | None = Query(None),
           db: Session = Depends(get_db)):
    q = db.query(models.Feriado).filter(models.Feriado.pais == pais.upper())
    if anio:
        q = q.filter(models.Feriado.fecha >= date(anio, 1, 1),
                     models.Feriado.fecha <= date(anio, 12, 31))
    items = [_serial(f) for f in q.order_by(models.Feriado.fecha).all()]
    anios = sorted({date.fromisoformat(i["fecha"]).year for i in items})
    return {"items": items, "anios": anios}


@router.post("", status_code=201)
def crear(data: FeriadoIn, db: Session = Depends(get_db), _perm=Depends(_req_escritura_feriado)):
    pais = data.pais.upper()
    if db.query(models.Feriado).filter_by(pais=pais, fecha=data.fecha).first():
        raise HTTPException(409, "Ya hay un feriado ese día para ese país")
    f = models.Feriado(pais=pais, fecha=data.fecha, nombre=data.nombre.strip(),
                       tipo=data.tipo, origen="MANUAL", activo=data.activo)
    db.add(f); db.commit(); db.refresh(f)
    return _serial(f)


@router.put("/{fid}")
def editar(fid: int, data: FeriadoIn, db: Session = Depends(get_db), _perm=Depends(_req_escritura_feriado)):
    f = db.get(models.Feriado, fid)
    if not f:
        raise HTTPException(404, "Feriado no encontrado")
    f.pais = data.pais.upper(); f.fecha = data.fecha; f.nombre = data.nombre.strip()
    f.tipo = data.tipo; f.activo = data.activo
    db.commit(); db.refresh(f)
    return _serial(f)


@router.delete("/{fid}")
def borrar(fid: int, db: Session = Depends(get_db), _perm=Depends(_req_escritura_feriado)):
    f = db.get(models.Feriado, fid)
    if not f:
        raise HTTPException(404, "Feriado no encontrado")
    db.delete(f); db.commit()
    return {"ok": True}


@router.post("/importar")
def importar(data: ImportarIn, db: Session = Depends(get_db), _perm=Depends(_req_escritura_feriado)):
    """Importa el calendario de un país/año desde la fuente oficial (o cálculo local de respaldo).

    Idempotente: inserta los que faltan y no duplica los ya cargados (por país+fecha).
    """
    pais = data.pais.upper()
    fuente = "OFICIAL (Nager.Date)"
    filas = _desde_nager(pais, data.anio)
    if filas is None:
        if pais == "AR":
            filas = _ar_calculados(data.anio)
            fuente = "cálculo local (fuente oficial no disponible)"
        else:
            raise HTTPException(502, "Fuente oficial no disponible y no hay cálculo local para ese país")
    existentes = {f.fecha for f in db.query(models.Feriado).filter(
        models.Feriado.pais == pais,
        models.Feriado.fecha >= date(data.anio, 1, 1),
        models.Feriado.fecha <= date(data.anio, 12, 31)).all()}
    nuevos = 0
    for f, nombre, tipo in filas:
        if f in existentes:
            continue
        db.add(models.Feriado(pais=pais, fecha=f, nombre=nombre, tipo=tipo, origen="OFICIAL", activo=True))
        nuevos += 1
    db.commit()
    return {"pais": pais, "anio": data.anio, "fuente": fuente,
            "importados": nuevos, "totalFuente": len(filas)}


def feriados_set(db: Session, pais: str, desde: date, hasta: date) -> set[date]:
    """Conjunto de fechas de feriados activos de un país en un rango — para el motor de cronograma."""
    rows = db.query(models.Feriado.fecha).filter(
        models.Feriado.pais == pais.upper(), models.Feriado.activo.is_(True),
        models.Feriado.fecha >= desde, models.Feriado.fecha <= hasta).all()
    return {r[0] for r in rows}
