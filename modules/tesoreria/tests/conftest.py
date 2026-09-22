"""Base de tests: SQLite en memoria, workflow e Interbanking simulados, y avisos capturados."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["INTERNAL_API_KEY"] = "clave-de-test"
os.environ["ENVIO_SIMULADO"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services import avisos, interbanking, workflow

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)


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


class WorkflowFalso:
    """Regla LOTE_PAGO de Configuraciones: por defecto INACTIVA (aprueba quien tiene el permiso)."""
    def __init__(self):
        self.d = {"objeto": "LOTE_PAGO", "activo": False, "niveles": [
            {"orden": 1, "nombre": "Tesorero", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []}]}
        self.caido = False

    def __call__(self):
        if self.caido:
            raise ConnectionError("Configuraciones caído")
        return self.d

    def activar(self, niveles=None):
        self.d["activo"] = True
        if niveles:
            self.d["niveles"] = niveles
        workflow.usar_fuente(self)


@pytest.fixture(autouse=True)
def wf():
    f = WorkflowFalso()
    workflow.usar_fuente(f)
    return f


@pytest.fixture(autouse=True)
def simulado(monkeypatch):
    monkeypatch.setattr(settings, "envio_simulado", True)


class Banco:
    """Interbanking simulado para el modo real: se programa qué responde cada envío."""
    def __init__(self):
        self.enviados, self.respuestas, self.estados = [], [], {}

    def enviar(self, cbu, monto, concepto):
        self.enviados.append((cbu, monto, concepto))
        r = self.respuestas.pop(0) if self.respuestas else {"status": "INICIADA"}
        if isinstance(r, Exception):
            raise r
        tid = len(self.enviados)
        return {"id": tid, "id_operacion_ib": f"IB-{tid}", **r}

    def estado(self, transfer_id):
        return self.estados.get(transfer_id, "INICIADA")


@pytest.fixture
def banco(monkeypatch):
    b = Banco()
    monkeypatch.setattr(settings, "envio_simulado", False)
    monkeypatch.setattr(interbanking, "enviar", b.enviar)
    monkeypatch.setattr(interbanking, "estado", b.estado)
    return b


class Avisos:
    def __init__(self):
        self.recibidos, self.caido = [], False

    def post(self, url, json, headers, timeout):
        if self.caido:
            import httpx
            raise httpx.ConnectError("origen caído")
        self.recibidos.append((url, headers, json))

        class R:
            def raise_for_status(self):
                return None
        return R()


@pytest.fixture(autouse=True)
def origen(monkeypatch):
    a = Avisos()
    monkeypatch.setattr(avisos.httpx, "post", a.post)
    return a


@pytest.fixture
def client():
    return TestClient(app)


def gateway(*acciones, user_id=7, username="teso"):
    return {"X-User-Id": str(user_id), "X-Username": username,
            "X-User-Permissions": ",".join(f"tesoreria:{a}" for a in acciones)}


TESORERO = ("lotes:read", "lotes:write", "lotes:enviar", "aprobaciones:aprobar")


@pytest.fixture
def teso():
    return gateway(*TESORERO)


@pytest.fixture
def interna():
    return {"X-Api-Key": "clave-de-test"}


def pago(ref, monto=1000.0, cbu="2850590940090418135201", beneficiario="PEREZ JUAN", **extra):
    return {"referencia_externa": ref, "beneficiario": beneficiario, "documento": "20301234569",
            "cbu": cbu, "monto": monto, "concepto": "Desembolso", **extra}


@pytest.fixture
def lote_creditos(client, interna):
    """Lote de desembolsos que manda Créditos (dos pagos), con aviso de resultado."""
    def _crear(ref="liquidación 2026-09-22", pagos=None):
        r = client.post("/internal/tesoreria/lotes", headers=interna, json={
            "origen": "CREDITOS", "referencia_origen": ref, "descripcion": "Desembolsos del día",
            "callback_url": "http://creditos:8010/internal/creditos/tesoreria/resultado", "usuario": "ana.creditos",
            "pagos": pagos or [pago("cto-1", 500000), pago("cto-2", 300000, beneficiario="GOMEZ ANA")]})
        assert r.status_code == 201, r.text
        return r.json()
    return _crear
