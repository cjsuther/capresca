"""Base de tests del módulo conciliación.

Dos decisiones que condicionan todo lo demás:

1. La config se lee al importar la app, así que las variables de entorno se
   setean ANTES de cualquier import de `app.*`.
2. Nada de red: los clientes HTTP hacia clientes/interbanking/notifications se
   reemplazan por dobles (fixture `servicios`, autouse). Los clientes reales se
   ejercitan aparte, con `httpx` falseado (fixture `http_falso` + `reales`).

El scheduler (APScheduler) sólo arranca en el lifespan de FastAPI: por eso el
`TestClient` NUNCA se usa como context manager.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CLIENTES_SERVICE_URL", "http://clientes-test:8003")
os.environ.setdefault("INTERBANKING_SERVICE_URL", "http://interbanking-test:8004")
os.environ.setdefault("LEGACY_SERVICE_URL", "http://legacy-test:8009")
os.environ.setdefault("LEGACY_INTERNAL_API_KEY", "clave-de-test")
os.environ.setdefault("NOTIFICATIONS_SERVICE_URL", "http://notifications-test:8005")
os.environ.setdefault("AUTO_PAYMENTS_ENABLED", "false")
os.environ.setdefault("PAYMENTS_DRY_RUN", "true")

from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import BigInteger, create_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
# Varios modelos sólo se importan dentro de funciones en producción: si no se importan
# acá, `create_all` no crea sus tablas y el resultado depende del orden de los tests.
from app.models import (cbu_agency_cache, liquidacion_record,  # noqa: E402,F401
                        reconciliation_adjustment, reconciliation_ib_link,
                        reconciliation_payment, reconciliation_status_history)
from app.models.reconciliation_record import ReconciliationRecord  # noqa: E402
from app.services import clientes_client, interbanking_client, legacy_client  # noqa: E402
from app.services.notifications_client import notifications_client  # noqa: E402


# En SQLite sólo autoincrementa un PK "INTEGER" (BIGINT no es alias de rowid): los ids de
# las tablas con BigInteger quedarían en NULL. Sólo aplica al dialecto de tests.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Fecha fija de trabajo: ningún test depende del día en que corre.
FECHA = date(2026, 3, 10)
OTRA_FECHA = date(2026, 3, 11)

# Referencias a las funciones reales, tomadas antes de que la fixture autouse las
# reemplace: los tests de degradación las llaman directamente.
REALES = {
    "clientes.get_agencies": clientes_client.get_agencies,
    "clientes.get_agency_by_cbu": clientes_client.get_agency_by_cbu,
    "ib.get_transactions": interbanking_client.get_transactions,
    "ib.get_consolidation_account": interbanking_client.get_consolidation_account,
    "ib.get_payment_account": interbanking_client.get_payment_account,
    "ib.get_movements": interbanking_client.get_movements,
    "ib.create_payment": interbanking_client.create_payment,
    "legacy.get_agencias": legacy_client.get_agencias,
    "legacy.get_pagos": legacy_client.get_pagos,
    "legacy.get_formas_pago": legacy_client.get_formas_pago,
    "legacy.get_creditos_seguros": legacy_client.get_creditos_seguros,
    "legacy.enqueue_aplicar_pago": legacy_client.enqueue_aplicar_pago,
    "legacy.enqueue_anular_pago": legacy_client.enqueue_anular_pago,
    "notif.notify": notifications_client.notify,
}


@pytest.fixture
def reales():
    return REALES


# ─────────────────────────────────────────────────────────────────────────────
# Base de datos
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def db():
    """Esquema limpio por test; la app usa esta misma sesión."""
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
    # Sin context manager a propósito: así no corre el lifespan (cache + scheduler).
    return TestClient(app)


@pytest.fixture
def h():
    """Headers que inyecta el gateway para el usuario 7."""
    return {"X-User-Id": "7", "X-Username": "operador"}


# ─────────────────────────────────────────────────────────────────────────────
# Dobles de los servicios externos
# ─────────────────────────────────────────────────────────────────────────────
class ServiciosExternos:
    """Estado configurable de los módulos vecinos + registro de lo que se les pidió."""

    def __init__(self):
        self.agencias: list[dict] = []
        self.transacciones: list[dict] = []
        self.cuenta_consolidacion: dict | None = None
        self.movimientos: list[dict] = []
        self.respuesta_pago: dict = {"id": 9001}
        self.error_pago: Exception | None = None
        # registros
        self.fechas_pedidas: list[str] = []
        self.movimientos_pedidos: list[tuple[str, dict]] = []
        self.pagos_ejecutados: list[tuple[str, float, str]] = []
        self.notificaciones: list[dict] = []
        self.error_notificacion: Exception | None = None


@pytest.fixture(autouse=True)
def servicios(monkeypatch):
    s = ServiciosExternos()

    async def _agencies():
        return [dict(a) for a in s.agencias]

    async def _transactions(date_str):
        s.fechas_pedidas.append(date_str)
        return [dict(t) for t in s.transacciones]

    async def _consolidation_account():
        return s.cuenta_consolidacion

    async def _movements(date_str, account):
        s.movimientos_pedidos.append((date_str, account))
        return [dict(m) for m in s.movimientos]

    async def _create_payment(cbu, monto, concepto):
        s.pagos_ejecutados.append((cbu, monto, concepto))
        if s.error_pago:
            raise s.error_pago
        return s.respuesta_pago

    def _notify(**kwargs):
        if s.error_notificacion:
            raise s.error_notificacion
        s.notificaciones.append(kwargs)

    monkeypatch.setattr(clientes_client, "get_agencies", _agencies)
    monkeypatch.setattr(interbanking_client, "get_transactions", _transactions)
    monkeypatch.setattr(interbanking_client, "get_consolidation_account", _consolidation_account)
    monkeypatch.setattr(interbanking_client, "get_movements", _movements)
    monkeypatch.setattr(interbanking_client, "create_payment", _create_payment)
    monkeypatch.setattr(notifications_client, "notify", _notify)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# httpx falso (para ejercitar los clientes HTTP reales sin red)
# ─────────────────────────────────────────────────────────────────────────────
class RespuestaFalsa:
    def __init__(self, data=None, status_code=200, url="http://test"):
        self._data = data
        self.status_code = status_code
        self._url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            pedido = httpx.Request("GET", self._url)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=pedido,
                response=httpx.Response(self.status_code, request=pedido),
            )

    def json(self):
        return self._data


class _ClienteFalso:
    def __init__(self, manejador, llamadas):
        self._manejador = manejador
        self._llamadas = llamadas

    def _llamar(self, metodo, url, kw):
        self._llamadas.append({"metodo": metodo, "url": url, **kw})
        return self._manejador(metodo, url, kw)


class _AsyncClienteFalso(_ClienteFalso):
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kw):
        return self._llamar("GET", url, kw)

    async def post(self, url, **kw):
        return self._llamar("POST", url, kw)


class _SyncClienteFalso(_ClienteFalso):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, **kw):
        return self._llamar("POST", url, kw)


@pytest.fixture
def http_falso(monkeypatch):
    """Instala un httpx falso; devuelve la lista de llamadas hechas.

    `manejador(metodo, url, kwargs)` devuelve una RespuestaFalsa o lanza (para
    simular el servicio caído).
    """
    llamadas: list[dict] = []

    def _instalar(manejador):
        monkeypatch.setattr(httpx, "AsyncClient",
                            lambda *a, **kw: _AsyncClienteFalso(manejador, llamadas))
        monkeypatch.setattr(httpx, "Client",
                            lambda *a, **kw: _SyncClienteFalso(manejador, llamadas))
        return llamadas

    return _instalar


def cae(*_args, **_kwargs):
    """Manejador que simula el servicio caído."""
    raise httpx.ConnectError("conexión rechazada")


# ─────────────────────────────────────────────────────────────────────────────
# Constructores de datos
# ─────────────────────────────────────────────────────────────────────────────
def num(valor):
    """Normaliza un importe del JSON.

    Los endpoints con `response_model=RecordResponse` devuelven los importes como
    string (Decimal de pydantic) y los que responden un dict crudo, como float.
    """
    return Decimal(str(valor))



def agencia(client_id, numero, cbu=None, *, legal_name=None, tax_id=None,
            cbus=None, cuenta_de_pago=False):
    return {
        "client_id": client_id,
        "agency_number": numero,
        "legal_name": legal_name or f"Agencia {numero} S.A.",
        "tax_id": tax_id,
        "cbus": cbus if cbus is not None else (
            [{"cbu": cbu, "is_payment_account": cuenta_de_pago}] if cbu else []
        ),
    }


def transferencia(tx_id, cbu, monto, *, tipo="transfer", concepto="PAGO QUINIELA",
                  fecha=FECHA):
    return {
        "id": tx_id, "type": tipo, "date": fecha.isoformat(), "cbu": cbu,
        "concepto": concepto, "amount": str(monto), "status_ib": "CONFIRMADA",
        "id_operacion_ib": f"OP-{tx_id}",
    }


def movimiento(tx_id, monto, *, cuit=None, cbu=None, concepto="DEPOSITO", fecha=FECHA):
    return {
        "id": tx_id, "type": "movement", "date": fecha.isoformat(), "cbu": cbu,
        "cuit": cuit, "concepto": concepto, "amount": str(monto),
        "status_ib": None, "id_operacion_ib": None,
    }


def crear_registro(db, *, client_id=1, fecha=FECHA, agency_number="A001",
                   adeudado="0", premios="0", depositado="0", status="A_VERIFICAR",
                   legal_name="Agencia A001 S.A.", tax_id="30-71234567-8"):
    r = ReconciliationRecord(
        reconciliation_date=fecha,
        client_id=client_id,
        agency_number=agency_number,
        agency_legal_name=legal_name,
        agency_tax_id=tax_id,
        importe_adeudado=Decimal(adeudado),
        importe_premios=Decimal(premios),
        importe_depositado=Decimal(depositado),
        status=status,
        created_by_user_id=1,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def payload_liquidaciones(*agencias, batch_id=77, fecha=FECHA, created_by=None):
    return {
        "batch_id": batch_id,
        "operation_date": fecha.isoformat(),
        "created_by": created_by,
        "agencies": list(agencias),
    }


def item_liquidacion(agency_number, *, adeudado="0", premios="0", fecha=FECHA,
                     recaudacion="0", comision="0", resumen="R-1", moneda="ARS",
                     batch_id=77):
    return {
        "agency_number": agency_number,
        "operation_date": fecha.isoformat(),
        "importe_adeudado": adeudado,
        "importe_premios": premios,
        "recaudacion_total": recaudacion,
        "comision_total": comision,
        "resumen_number": resumen,
        "moneda": moneda,
        "batch_id": batch_id,
        "batch_source": "DBF",
    }
