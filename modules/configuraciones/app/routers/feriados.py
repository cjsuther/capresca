"""Calendario de feriados por país. Créditos lo usa para correr vencimientos a día hábil; cargar un
feriado cambia los cronogramas que se simulen/originen desde ese momento (no los ya contratados)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import requiere, usuario_actual
from app.services.feriados import PAISES, ar_calculados, desde_nager

router = APIRouter(prefix="/feriados", tags=["feriados"], dependencies=[Depends(usuario_actual)])
_escribe = requiere("feriados:write")
CODIGOS_PAIS = {p["codigo"] for p in PAISES}
TIPOS = ("INAMOVIBLE", "TRASLADABLE", "PUENTE")


class FeriadoIn(BaseModel):
    pais: str = "AR"
    fecha: date
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = "INAMOVIBLE"
    activo: bool = True


class ImportarIn(BaseModel):
    pais: str = "AR"
    anio: int = Field(ge=1990, le=2100)


def serial(f: models.Feriado) -> dict:
    return {"id": f.id, "pais": f.pais, "fecha": f.fecha.isoformat(), "nombre": f.nombre,
            "tipo": f.tipo, "origen": f.origen, "activo": f.activo}


def _pais(codigo: str) -> str:
    codigo = (codigo or "").upper()
    if codigo not in CODIGOS_PAIS:
        raise HTTPException(422, f"País no soportado: {codigo}.")
    return codigo


def _validar(data: FeriadoIn) -> dict:
    if data.tipo not in TIPOS:
        raise HTTPException(422, f"Tipo inválido. Opciones: {', '.join(TIPOS)}.")
    return {"pais": _pais(data.pais), "fecha": data.fecha, "nombre": data.nombre.strip(),
            "tipo": data.tipo, "activo": data.activo}


def fechas_activas(db: Session, pais: str, desde: date, hasta: date) -> list[date]:
    rows = db.query(models.Feriado.fecha).filter(
        models.Feriado.pais == pais.upper(), models.Feriado.activo.is_(True),
        models.Feriado.fecha >= desde, models.Feriado.fecha <= hasta).order_by(models.Feriado.fecha).all()
    return [r[0] for r in rows]


@router.get("/paises")
def paises():
    return {"items": PAISES}


@router.get("")
def listar(pais: str = Query("AR"), anio: int | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Feriado).filter(models.Feriado.pais == pais.upper())
    anios = sorted({f.year for (f,) in q.with_entities(models.Feriado.fecha).all()})
    if anio:
        q = q.filter(models.Feriado.fecha >= date(anio, 1, 1), models.Feriado.fecha <= date(anio, 12, 31))
    return {"items": [serial(f) for f in q.order_by(models.Feriado.fecha).all()], "anios": anios}


@router.post("", status_code=201, dependencies=[Depends(_escribe)])
def crear(data: FeriadoIn, db: Session = Depends(get_db)):
    valores = _validar(data)
    if db.query(models.Feriado).filter_by(pais=valores["pais"], fecha=valores["fecha"]).first():
        raise HTTPException(409, "Ya hay un feriado ese día para ese país")
    f = models.Feriado(**valores, origen="MANUAL")
    db.add(f); db.commit(); db.refresh(f)
    return serial(f)


@router.put("/{fid}", dependencies=[Depends(_escribe)])
def editar(fid: int, data: FeriadoIn, db: Session = Depends(get_db)):
    f = db.get(models.Feriado, fid)
    if not f:
        raise HTTPException(404, "Feriado no encontrado")
    valores = _validar(data)
    otro = db.query(models.Feriado).filter_by(pais=valores["pais"], fecha=valores["fecha"]).first()
    if otro and otro.id != f.id:
        raise HTTPException(409, "Ya hay un feriado ese día para ese país")
    for k, v in valores.items():
        setattr(f, k, v)
    db.commit(); db.refresh(f)
    return serial(f)


@router.delete("/{fid}", dependencies=[Depends(_escribe)])
def borrar(fid: int, db: Session = Depends(get_db)):
    f = db.get(models.Feriado, fid)
    if not f:
        raise HTTPException(404, "Feriado no encontrado")
    db.delete(f); db.commit()
    return {"ok": True}


@router.post("/importar", dependencies=[Depends(_escribe)])
def importar(data: ImportarIn, db: Session = Depends(get_db)):
    """Importa el calendario de un país/año de la fuente oficial (o el cálculo local para AR).
    Idempotente: agrega los que faltan, no duplica ni pisa los cargados a mano."""
    pais = _pais(data.pais)
    fuente = "OFICIAL (Nager.Date)"
    filas = desde_nager(pais, data.anio)
    if filas is None:
        if pais != "AR":
            raise HTTPException(502, "Fuente oficial no disponible y no hay cálculo local para ese país")
        filas, fuente = ar_calculados(data.anio), "cálculo local (fuente oficial no disponible)"
    # activos o dados de baja: un feriado que alguien desactivó a mano no se revive al importar
    existentes = {f for (f,) in db.query(models.Feriado.fecha).filter(
        models.Feriado.pais == pais, models.Feriado.fecha >= date(data.anio, 1, 1),
        models.Feriado.fecha <= date(data.anio, 12, 31)).all()}
    nuevos = 0
    for fecha, nombre, tipo in filas:
        if fecha in existentes:
            continue
        db.add(models.Feriado(pais=pais, fecha=fecha, nombre=nombre, tipo=tipo, origen="OFICIAL"))
        existentes.add(fecha)
        nuevos += 1
    db.commit()
    return {"pais": pais, "anio": data.anio, "fuente": fuente, "importados": nuevos, "totalFuente": len(filas)}
