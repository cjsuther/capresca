"""Punto de entrada de la API CCyPP (FastAPI)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import Base, engine, SessionLocal
from app.api import (clientes, creditos, caja, consultas, admin, productos, contratos,
                     impuestos, indices, sistema_calculos, solicitudes, aprobaciones, portal,
                     tesoreria_interna)
from app.core.configuraciones import ConfiguracionNoDisponible
from app import models_productos  # noqa: F401  (registra tablas pp_* en Base.metadata)
from app.seed import seed, seed_perfiles
from app.seed_productos import seed_productos

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En desarrollo creamos el esquema y sembramos datos demo.
    # En producción usar Alembic (alembic upgrade head) y el ETL.
    Base.metadata.create_all(bind=engine)
    _migrar_iam()
    if settings.environment == "development":
        with SessionLocal() as db:
            seed(db)
    # El catálogo de Configurar Créditos todavía no tiene ETL: se siembra siempre
    # (idempotente, con guard propio) para que la pantalla tenga datos de ejemplo.
    with SessionLocal() as db:
        seed_perfiles(db)
        seed_productos(db)
        from app.services.contabilidad import seed_imputaciones, seed_diarios, seed_centros, seed_parametros_contables
        seed_imputaciones(db)
        seed_diarios(db)
        seed_centros(db)
        seed_parametros_contables(db)
        from app.api.productos import seed_canales_parametros
        seed_canales_parametros(db)
    # Los asientos migrados (ETL) traen ids explícitos: resincronizamos la secuencia para que
    # los asientos generados por la app (originación/servicing de contratos) no colisionen.
    _resync_secuencia_asientos()
    yield


def _migrar_iam() -> None:
    """Agrega columnas de vigencia a usuario_perfil en Postgres (create_all no altera tablas existentes).
    En SQLite (tests) la tabla se crea completa, así que se omite."""
    from sqlalchemy import text
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for col in ("vigente_desde", "vigente_hasta"):
            conn.execute(text(f"ALTER TABLE usuario_perfil ADD COLUMN IF NOT EXISTS {col} DATE"))
        # El código de rol es el identificador del RBAC: unicidad garantizada por la DB
        # (create_all no altera tablas existentes). Idempotente; no falla si ya existe.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_perfiles_codigo ON perfiles (codigo)"))
        # Un nivel de la cadena de aprobación se aprueba una sola vez: la DB frena la carrera de dos
        # aprobadores concurrentes en el mismo nivel (bypass de cuatro-ojos/N-ojos).
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_wf_aprobacion_nivel "
                          "ON pp_workflow_aprobacion (objeto, objeto_id, nivel_orden)"))
        # Nºs de negocio únicos (la DB es árbitro): sin esto, dos procesos concurrentes emiten el mismo
        # número sin error (dinero con identidad duplicada). Data verificada sin duplicados. Ver H-108.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_recibos_numero ON recibos (numero)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ordenes_pago_numero ON ordenes_pago (numero)"))
        # Nºs con alcance compuesto (verificados sin duplicados en la data migrada). H-108.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_polizas_numero ON polizas (numero)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_pp_version_producto_numero ON pp_producto_version (producto_id, numero_version)"))
        # Una actividad se reversa una sola vez: la DB frena dos reversar concurrentes (doble contra-asiento). H-110.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_pp_actividad_reversa_de ON pp_actividad (reversa_de)"))
        # El balance de la app filtra origen != 'legacy'; índice para no escanear 1M asientos. H-113.
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asientos_origen ON asientos (origen)"))
        # El CUIL del cliente es único (la DB es árbitro): sin esto, dos altas concurrentes con el mismo
        # CUIL crean un duplicado (check-then-insert no alcanza). H-154. Si hubiera duplicados previos, se
        # loguea y se sigue (no tumba el arranque); en la data limpia no los hay.
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_clientes_cuil ON clientes (cuil)"))
        except Exception as e:  # pragma: no cover
            print(f"[migrar] no se pudo crear uq_clientes_cuil (¿CUIL duplicado?): {e}")
        # Padrón único de clientes: la tabla `clientes` pasa a ser ESPEJO del módulo Clientes y su `id`
        # es el del padrón (ya no una secuencia local). Se agrega la marca de sincronización y se saca
        # el default de la secuencia para que un INSERT sin id falle en vez de inventar un id local.
        conn.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS sincronizado_en TIMESTAMPTZ"))
        try:
            conn.execute(text("ALTER TABLE clientes ALTER COLUMN id DROP DEFAULT"))
        except Exception as e:  # pragma: no cover
            print(f"[migrar] no se pudo soltar el default de clientes.id: {e}")

        # La solicitud guarda la FECHA DE NACIMIENTO y la edad se calcula (H-219). Idempotente.
        conn.execute(text("ALTER TABLE pp_solicitud ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE"))

        # Plan de cuentas: campos de la pantalla moderna (H-174). Idempotente.
        for col, ddl in (("descripcion", "TEXT DEFAULT ''"), ("alias", "VARCHAR(40) DEFAULT ''"),
                         ("moneda", "VARCHAR(3) DEFAULT 'ARS'"), ("clasificacion", "VARCHAR(30) DEFAULT 'Sin clasificar'"),
                         ("saldo_normal", "VARCHAR(10) DEFAULT 'deudor'"), ("imputable", "BOOLEAN DEFAULT TRUE"),
                         ("manual", "BOOLEAN DEFAULT FALSE"), ("entidades", "JSONB DEFAULT '[]'::jsonb")):
            conn.execute(text(f"ALTER TABLE cuentas_contables ADD COLUMN IF NOT EXISTS {col} {ddl}"))
        # Asientos manuales (H-176): correlativo, reversa y auditoría. Idempotente.
        for col, ddl in (("numero", "INTEGER"), ("reversado", "BOOLEAN DEFAULT FALSE"),
                         ("reversa_de", "INTEGER"), ("usuario", "VARCHAR(30) DEFAULT ''"),
                         ("estado", "VARCHAR(12) DEFAULT 'publicado'"), ("diario_codigo", "VARCHAR(12) DEFAULT ''")):
            conn.execute(text(f"ALTER TABLE asientos ADD COLUMN IF NOT EXISTS {col} {ddl}"))
        conn.execute(text("ALTER TABLE asientos_lineas ADD COLUMN IF NOT EXISTS centro_codigo VARCHAR(12) DEFAULT ''"))
        # H-188: contabilidad por EMPRESA (multi-plan). Se agrega empresa_id a cuentas y asientos,
        # se garantiza una empresa predeterminada, se backfillean los datos existentes a ella, y el código
        # de cuenta pasa a ser único POR empresa (antes único global).
        conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS cuit VARCHAR(13) DEFAULT ''"))
        emp = conn.execute(text("SELECT id FROM empresas WHERE predeterminada = TRUE ORDER BY id LIMIT 1")).first()
        if not emp:
            emp = conn.execute(text("SELECT id FROM empresas ORDER BY id LIMIT 1")).first()
            if emp:
                conn.execute(text("UPDATE empresas SET predeterminada = TRUE WHERE id = :i"), {"i": emp[0]})
            else:
                emp = conn.execute(text("INSERT INTO empresas (codigo, nombre, cuit, predeterminada, activa, creada_en) "
                                        "VALUES ('GRAL', 'Ca.Pre.S.Ca. (general)', '', TRUE, TRUE, now()) RETURNING id")).first()
        emp_id = emp[0]
        for tabla in ("cuentas_contables", "asientos"):
            conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id)"))
            conn.execute(text(f"UPDATE {tabla} SET empresa_id = :i WHERE empresa_id IS NULL"), {"i": emp_id})
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{tabla}_empresa ON {tabla} (empresa_id)"))
        # código de cuenta único POR empresa: se baja la unique global y se sube la compuesta.
        conn.execute(text("ALTER TABLE cuentas_contables DROP CONSTRAINT IF EXISTS cuentas_contables_codigo_key"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_cuenta_empresa_codigo ON cuentas_contables (empresa_id, codigo)"))
        # H-190: trazabilidad de "préstamo duplicado" (de qué producto salió la copia).
        conn.execute(text("ALTER TABLE pp_producto ADD COLUMN IF NOT EXISTS copiado_de VARCHAR(36)"))
        # H-197: los parámetros se separan por ÁMBITO (general|creditos|contabilidad). Backfill de los actuales.
        conn.execute(text("ALTER TABLE parametros ADD COLUMN IF NOT EXISTS ambito VARCHAR(20) DEFAULT 'general'"))
        conn.execute(text("UPDATE parametros SET ambito='creditos' WHERE clave IN ('CANALES','CANAL_PORTAL','CANAL_BACKOFFICE','DECIMALES_CALCULO','DECIMALES_MOSTRAR')"))
        conn.execute(text("UPDATE parametros SET ambito='contabilidad' WHERE clave IN ('CUENTAS_EFECTIVO')"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_parametros_ambito ON parametros (ambito)"))


def _resync_secuencia_asientos() -> None:
    from sqlalchemy import text
    try:
        with engine.begin() as c:
            for t in ("asientos", "asientos_lineas"):
                c.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{t}','id'), "
                    f"COALESCE((SELECT MAX(id) FROM {t}),0)+1, false)"))
    except Exception:
        pass  # SQLite (tests) u otros backends sin secuencias: no aplica


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API del módulo Créditos (CCyPP · Ca.Pre.S.Ca.) de Portezuelo.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ConfiguracionNoDisponible)
async def _configuraciones_caido(_request: Request, exc: ConfiguracionNoDisponible):
    """Sin impuestos/índices/feriados/reglas no se calcula ni se aprueba nada: 503, nunca un valor inventado."""
    return JSONResponse(status_code=503, content={
        "detail": "El módulo Configuraciones no está disponible; reintentá en unos segundos."})


# Impuestos, índices, feriados y reglas del workflow los administra el módulo Configuraciones.
# Sólo el circuito de créditos: las áreas de CCyPP que no se migraron a Portezuelo (caja,
# contabilidad, tesorería, seguros, despacho, mesa, juegos, controles, migradores) no se publican.
# Sus servicios que el crédito usa por dentro (asientos, pólizas, órdenes de pago, recibos) siguen.
app.include_router(clientes.router)
app.include_router(creditos.router)
app.include_router(consultas.router)
app.include_router(caja.router)
app.include_router(admin.router)
app.include_router(productos.router)
app.include_router(contratos.router)
app.include_router(impuestos.router)
app.include_router(indices.router)
app.include_router(sistema_calculos.router)
app.include_router(solicitudes.router)
app.include_router(aprobaciones.router)
app.include_router(portal.router)
app.include_router(tesoreria_interna.router)


@app.get("/api/creditos/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name}
