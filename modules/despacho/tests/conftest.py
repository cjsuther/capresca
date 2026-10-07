"""Base de tests de Despacho: SQLite en memoria y la identidad que inyecta el gateway."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
# Los tests no auditan: el contenedor hereda la clave del compose y el hilo de Auditoría saldría a
# la red en cada flush.
os.environ["AUDITORIA_INTERNAL_API_KEY"] = ""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine("sqlite+pysqlite:///:memory:",
                       connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk_on(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def gateway(*acciones, user_id=7, username="despacho"):
    """Las cabeceras que inyecta el gateway después de resolver los permisos."""
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"despacho:{a}" for a in acciones)}


TODO = ("resoluciones:read", "resoluciones:write", "resoluciones:firmar",
        "modelos:write", "expedientes:write", "importar")


@pytest.fixture
def h():
    """Un usuario de Despacho con todos los permisos del módulo."""
    return gateway(*TODO)


@pytest.fixture
def solo_lectura():
    return gateway("resoluciones:read")


@pytest.fixture
def modelo(client, h):
    """Un modelo de resolución, que es lo que alimenta el combo 'Modelo a utilizar'."""
    def _crear(descripcion="TRANSFERENCIA", tipo="RES", plantilla="<p>VISTO: …</p>"):
        r = client.post("/api/despacho/modelos", headers=h,
                        json={"descripcion": descripcion, "tipo": tipo, "plantilla": plantilla})
        assert r.status_code == 201, r.text
        return r.json()
    return _crear


@pytest.fixture
def resolucion(client, h):
    """Una resolución en borrador."""
    def _crear(**extra):
        datos = {"tipo": "RES", "asunto": "Otorgamiento de créditos", "organo": "DIRECTORIO"}
        datos.update(extra)
        r = client.post("/api/despacho/resoluciones", headers=h, json=datos)
        assert r.status_code == 201, r.text
        return r.json()
    return _crear


@pytest.fixture(autouse=True)
def creditos(monkeypatch):
    """Créditos de mentira: los lotes son suyos y se consultan por su API interna.

    Reproduce sus reglas (un lote no recibe dos resoluciones y la suma de los lotes de una
    resolución no pasa su importe) para probar el circuito completo sin levantar el otro módulo.
    Las reglas de verdad tienen sus propios tests en Créditos.
    """
    from decimal import Decimal

    from fastapi import HTTPException

    from app.services import creditos_central

    PRODUCTOS = [{"tipo": "prod-personal", "nombre": "Préstamo personal"},
                 {"tipo": "prod-vivienda", "nombre": "Vivienda"}]
    lotes: dict[int, dict] = {}
    proximo = {"n": 0}
    avisos: list[dict] = []

    def alta(montos=(100000, 200000), producto="prod-personal", resolucion=None, estado="CERRADO"):
        proximo["n"] += 1
        n = proximo["n"]
        lotes[n] = {"id": n, "codigo": f"2026-{n:04d}", "anio": 2026, "numero": n, "fecha": "2026-10-06",
                    "productoId": producto,
                    "producto": next(p["nombre"] for p in PRODUCTOS if p["tipo"] == producto),
                    "estado": "CON_RESOLUCION" if resolucion else estado, "resolucion": resolucion,
                    "cantidad": len(montos), "montoTotal": float(sum(montos)),
                    "solicitudes": [{"id": f"s{n}-{i}", "numero": f"SOL-{n}-{i}", "cuil": "20305047579",
                                     "apellido_nombre": f"PEREZ {i}", "producto": "Préstamo personal",
                                     "monto": Decimal(m), "lote": f"2026-{n:04d}"}
                                    for i, m in enumerate(montos)]}
        return lotes[n]

    def _de(resolucion_id=None, numero=0, anio=None):
        out = []
        for lt in lotes.values():
            r = lt["resolucion"] or {}
            if (resolucion_id and r.get("id") == resolucion_id) or \
                    (numero and not r.get("id") and r.get("numero") == numero and r.get("anio") == anio):
                out.append(lt)
        return out

    def _sin_detalle(lt):
        return {k: v for k, v in lt.items() if k != "solicitudes"}

    def listar(*, estado=None, producto_id=None, resolucion_id=None, numero=0, anio=None):
        items = _de(resolucion_id, numero, anio) if (resolucion_id or numero) else list(lotes.values())
        if estado:
            items = [x for x in items if x["estado"] == estado]
        if producto_id:
            items = [x for x in items if x["productoId"] == producto_id]
        return {"items": [_sin_detalle(x) for x in items], "cantidad": len(items),
                "total": Decimal(str(sum(x["montoTotal"] for x in items)))}

    def lote(lote_id):
        if lote_id not in lotes:
            raise HTTPException(404, "Lote no encontrado.")
        return _sin_detalle(lotes[lote_id])

    def asignar_resolucion(lote_ids, r):
        elegidos = [lotes[i] for i in lote_ids]
        abiertos = [x["codigo"] for x in elegidos if x["estado"] == "ABIERTO"]
        if abiertos:
            raise HTTPException(409, f"Estos lotes todavía no se cerraron: {', '.join(abiertos)}.")
        con = [x["codigo"] for x in elegidos if x["estado"] != "CERRADO"]
        if con:
            raise HTTPException(409, f"Estos lotes ya tienen resolución: {', '.join(con)}.")
        ya = _de(r["id"], r["numero"], r["anio"])
        total = sum(x["montoTotal"] for x in {id(x): x for x in elegidos + ya}.values())
        if Decimal(str(total)) > Decimal(str(r["importe"])):
            raise HTTPException(409, "La suma de los lotes supera el importe de la resolución.")
        for x in elegidos:
            x.update(estado="CON_RESOLUCION", resolucion=dict(r))
        return {"asignados": [x["codigo"] for x in elegidos], "totalResolucion": Decimal(str(total))}

    def quitar_resolucion(lote_id):
        lotes[lote_id].update(estado="CERRADO", resolucion=None)
        return {"lote": lotes[lote_id]["codigo"], "estado": "CERRADO"}

    def resolucion_actualizada(r):
        de = _de(r["id"], r["numero"], r["anio"])
        if de and Decimal(str(sum(x["montoTotal"] for x in de))) > Decimal(str(r["importe"])):
            raise HTTPException(409, "La suma de los lotes supera el importe de la resolución.")
        for x in de:
            x["resolucion"] = dict(r)
        avisos.append(dict(r))
        return {"lotes": len(de)}

    def solicitudes_de_resolucion(resolucion_id, numero, anio):
        filas = [s for lt in _de(resolucion_id, numero, anio) for s in lt["solicitudes"]]
        return {"items": filas, "cantidad": len(filas)}

    monkeypatch.setattr(creditos_central, "habilitado", lambda: True)
    monkeypatch.setattr(creditos_central, "tipos", lambda: PRODUCTOS)
    monkeypatch.setattr(creditos_central, "lotes", listar)
    monkeypatch.setattr(creditos_central, "lote", lote)
    monkeypatch.setattr(creditos_central, "asignar_resolucion", asignar_resolucion)
    monkeypatch.setattr(creditos_central, "quitar_resolucion", quitar_resolucion)
    monkeypatch.setattr(creditos_central, "resolucion_actualizada", resolucion_actualizada)
    monkeypatch.setattr(creditos_central, "solicitudes_de_resolucion", solicitudes_de_resolucion)
    return SimpleNamespace(alta=alta, lotes=lotes, productos=PRODUCTOS, avisos=avisos)
