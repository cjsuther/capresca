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
    """Créditos de mentira: las solicitudes del anexo son suyas y se consultan por su API interna.

    Reproduce sus reglas (aprobada + cubicada, y no puede estar en dos resoluciones) para poder
    probar el circuito completo del anexo sin levantar el otro módulo. Las reglas de verdad tienen
    sus propios tests en Créditos.
    """
    from decimal import Decimal

    from fastapi import HTTPException

    from app.services import creditos_central

    filas: dict[int, dict] = {}
    proximo = {"id": 1000}

    def alta(cantidad=3, linea=8050, estado="A", cubica="C", cartera=0):
        creadas = []
        for i in range(cantidad):
            proximo["id"] += 1
            filas[proximo["id"]] = {
                "id": proximo["id"], "fecha_solicitud": None, "cuil": f"2030504757{i}",
                "apellido_nombre": f"PEREZ {i}", "dni": "30504757", "monto": Decimal(100000 + i),
                "linea": linea, "linea_nombre": "AGAP", "cartera": cartera, "estado": estado,
                "cubica": cubica, "lote": 0, "numero_resolucion": 0, "en_resolucion": False}
            creadas.append(filas[proximo["id"]])
        return creadas

    def candidatas(*, linea_min=None, linea_max=None, cartera=None, lote=None):
        if lote:
            items = [f for f in filas.values() if f["en_resolucion"] and f["lote"] == lote]
        else:
            items = [f for f in filas.values()
                     if f["estado"] == "A" and f["cubica"] in ("C", "DC") and not f["en_resolucion"]]
            if cartera is not None:
                items = [f for f in items if f["cartera"] == cartera]
            elif linea_min is not None:
                items = [f for f in items if linea_min <= f["linea"] <= linea_max]
        return {"items": items, "cantidad": len(items),
                "total": sum((f["monto"] for f in items), Decimal("0"))}

    def asignar(*, solicitud_ids, numero_resolucion, fecha_resolucion):
        elegidas = [filas[i] for i in solicitud_ids if i in filas]
        ajenas = [f["id"] for f in elegidas
                  if f["en_resolucion"] and f["numero_resolucion"] != numero_resolucion]
        if ajenas:
            raise HTTPException(422, f"Estas solicitudes ya están en otra resolución: {ajenas}.")
        for f in elegidas:
            f.update(en_resolucion=True, numero_resolucion=numero_resolucion, lote=numero_resolucion)
        return {"asignadas": len(elegidas), "total": sum((f["monto"] for f in elegidas), Decimal("0"))}

    def quitar(solicitud_ids):
        sacadas = [filas[i] for i in solicitud_ids if i in filas]
        for f in sacadas:
            f.update(en_resolucion=False, numero_resolucion=0, lote=0)
        return {"quitadas": len(sacadas)}

    monkeypatch.setattr(creditos_central, "habilitado", lambda: True)
    monkeypatch.setattr(creditos_central, "candidatas", candidatas)
    monkeypatch.setattr(creditos_central, "asignar", asignar)
    monkeypatch.setattr(creditos_central, "quitar", quitar)
    return SimpleNamespace(alta=alta, filas=filas)
