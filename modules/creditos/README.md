# CCyPP — Sistema nuevo (Ca.Pre.S.Ca.)

Reescritura del sistema de gestión de la **Caja de Prestaciones Sociales de
Catamarca** (originalmente en Visual FoxPro) sobre un stack moderno.

> **Estado (2026-08-04):** aplicación en producción con **47 pantallas** en 9
> módulos, **118 tests verdes**, corriendo sobre **PostgreSQL con el backup real
> cargado** (62,6M registros). Cobertura del inventario VFP: **111/377 formularios
> (29%)** — el alcance *efectivo* es mayor porque muchos pendientes son
> variantes/pickers consolidados. Foto por módulo en
> [`salida/checkpoint-menu.md`](salida/checkpoint-menu.md); plan y mejoras en
> [`salida/cobertura-migracion.md`](salida/cobertura-migracion.md); estado
> pantalla por pantalla en [`salida/estado-migracion.md`](salida/estado-migracion.md);
> hallazgos (H-001→H-024) en [`salida/hallazgos.md`](salida/hallazgos.md).

## Stack

| Capa | Tecnología |
|---|---|
| Backend / API | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic |
| Base de datos | PostgreSQL 16 |
| Frontend | React 18 + Vite + TypeScript |
| Orquestación | Docker + docker-compose |

## Integración con Portezuelo

Este sistema es el módulo **Créditos** de Portezuelo (sistema modular). Corre con el resto del stack
desde el `docker-compose.yml` de la raíz:

| Pieza | Servicio | Publicado en |
|---|---|---|
| API (FastAPI) | `creditos` (:8010) | `/api/creditos/*` **vía gateway** · `/api/creditos/portal/*` directo (portal) |
| Base de datos | `db_creditos` (Postgres 16) | — |
| Backoffice (React) | `creditos-web` | `/creditos/` |
| Portal ciudadano (React) | `creditos-portal` | `/portal-creditos/` |

**Seguridad.** No hay login propio en el backoffice: se entra por el login de Portezuelo y el Dashboard
muestra la tarjeta *Créditos* a quien tenga algún permiso del módulo. El gateway valida el JWT del sistema,
resuelve los permisos contra `security` y reenvía `X-User-Id` / `X-Username` / `X-User-Permissions`
(`app/core/gateway.py`). El `Usuario` local se crea en el primer acceso, vinculado por username, sólo para
auditoría y workflow.

**Permisos** (Seguridad de Portezuelo → módulo *Créditos*), por área:

| Permiso | Habilita |
|---|---|
| `<area>:read` / `<area>:write` | Ver / operar el área. Áreas: `clientes`, `creditos`, `caja`, `tesoreria`, `contabilidad`, `seguros`, `despacho`, `mesa`, `juegos`, `general`, `seguridad` |
| `aprobaciones:aprobar` | Rol **APROBAR** de los niveles del workflow (cuatro-ojos) |
| `aprobaciones:supervisar` | Rol **SUPERVISAR** (niveles de supervisión, N-ojos) |

El gateway exige `GET → <area>:read` y el resto de los métodos `<area>:write` según el prefijo de la API
(`proxy/app/routes/mapping.py`). Diseñar/editar créditos exige `creditos:write`; aprobar, un permiso de
aprobación. Configurar el workflow exige `seguridad:write`. Usuarios, perfiles y grupos del sistema VFP ya
no autorizan nada: sus pantallas se retiraron y sus endpoints no se publican en el gateway.

**Portal ciudadano.** Tiene su propio realm (SSO Mi Catamarca, tokens `scope=portal` firmados con
`CREDITOS_PORTAL_JWT_SECRET`) y nginx lo manda directo al módulo, sin gateway. Sin credenciales de Mi
Catamarca el login del portal responde 503, salvo `CREDITOS_PORTAL_MOCK_SSO=true` (sólo demo/QA).
Registrar en Mi Catamarca el callback `${CREDITOS_PUBLIC_URL}/api/creditos/portal/auth/callback`.

### Puesta en marcha

```bash
# 1) Variables en el .env de la raíz: CREDITOS_DB_USER/PASS/NAME, CREDITOS_PORTAL_JWT_SECRET,
#    CREDITOS_PUBLIC_URL, CREDITOS_BASES_HOST_PATH, MICATAMARCA_CLIENT_ID/SECRET (ver README raíz)
docker compose up -d --build creditos creditos-web creditos-portal proxy security nginx

# 2) Cargar los datos reales del backup VFP (una vez; CREDITOS_BASES_HOST_PATH montado en /bases)
docker compose exec creditos python3 -m app.etl.cargar_todo /bases

# 3) En Seguridad de Portezuelo, asignar los permisos del módulo Créditos a los roles que correspondan
#    (el rol admin los recibe todos al arrancar security).
```

El backend corre en modo `production`: crea el esquema al arrancar y no siembra datos demo.

### Tests

```bash
docker compose run --rm creditos python -m pytest -q
```

Los tests usan SQLite y `tests/gateway_emulado.py`, que reproduce el gateway: un login de prueba para los
usuarios sembrados por perfil y el middleware que inyecta los headers `X-User-*` con permisos por área.

## Estructura

```
backend/
  app/
    domain/        # ← lógica de negocio portada del VFP (set_class.prg)
      cuotas.py    #   planes de amortización (francés/alemán/directo/tipo 5)
      mora.py      #   punitorios y resarcitorios
      margen.py    #   margen de afectación + validación de CUIL
      carteras.py  #   matriz de compatibilidad de carteras
    api/           # routers FastAPI (auth, clientes, creditos, caja, seguros,
                   #   contabilidad, egresos, admin, despacho, mesa, juegos, consultas)
    etl/           # loaders VFP-DBF → PostgreSQL (cargar_todo + por módulo)
    reports/       # PDF (reportlab) y Excel (openpyxl), con patrón write-only
    core/          # config, database, gateway (identidad de Portezuelo), permisos por área, pagination
    models.py      # modelos SQLAlchemy · schemas.py  Pydantic
    seed.py        # datos demo (reemplazado por el ETL en producción)
  tests/           # 118 tests (motor, equivalencia real, API por módulo)
  alembic/         # migraciones de esquema
frontend/
  src/pages/       # 53 pantallas en subcarpetas por módulo (creditos/, caja/,
  src/components/  #   seguros/, mesa/, general/…); DataTable, Sidebar
portal/            # portal público del ciudadano (React/Vite/TS)
salida/            # análisis de la migración, hallazgos (log vivo), estado por pantalla
```

## Pruebas

Ver [Tests](#tests). Las pruebas del motor fijan invariantes financieras. Los **valores de referencia
definitivos** deben provenir de créditos reales corridos en el VFP actual
(pruebas de equivalencia al centavo).

## Módulo destacado: motor de cálculo

El endpoint `POST /api/creditos/simular` es la vitrina del motor portado
(equivale al *F11 - Simulación de crédito* del sistema original). Calcula el plan
de cuotas con los 7 conceptos (capital, interés, IVA interés, seguro, IVA seguro,
gastos adm, IVA gastos), evalúa el **margen de afectación** y aplica reglas de
**cartera**. Detalle en `salida/motor_calculo.md`.

## Seguridad

Todos los secretos se leen de variables de entorno (`.env`, ver `.env.example`).
El VFP tenía el *ClientSecret* de la API de Catamarca en texto plano: **debe
rotarse** antes de reutilizar la integración.

## Estado por módulo (47 pantallas)

| Módulo | Pantallas construidas |
|---|---|
| **Créditos** | Solicitudes, Simulador, Situación del cliente, Estadísticas de cartera, Créditos por cartera (+PDF), Turnos otorgados, Listado (+Excel), Cuotas en mora, Sin débito automático, Pagos en caja (+Excel), Cuenta corriente, Pendientes de cobro, Envíos/padrón (+Excel), Jubilados Ley 5094, Líneas de crédito |
| **Caja** | Cobranza (mora + recibo), Control de caja |
| **Tesorería** | Órdenes de pago, Reporte de OP, Chequeras |
| **Contabilidad** | Libro diario (+PDF), Balance de sumas y saldos (+PDF), IVA por período (+PDF), Cierre de caja (+PDF) |
| **Seguros** | Pólizas y liquidación, Regímenes especiales (Malvinas/Excombatientes/Subsidio), Seguro de vida adicional, Informes |
| **Despacho** | Resoluciones y disposiciones (+Word), Expedientes y pases |
| **Juegos/Quiniela** | Maestro de juegos, Control de sorteos, Agencias y liquidaciones, Ingresos por juego |
| **Mesa de Entradas** | Turnos, Consulta de trámites, Trámites ingresados, Historial de pases |
| **General / Tablas** | Clientes/Agentes, Usuarios, Perfiles, Organismos, Oficinas, Compañías, Proveedores, Parámetros, Auditoría |

Detalle pantalla por pantalla en [`salida/estado-migracion.md`](salida/estado-migracion.md)
y reconciliación contra el menú real en [`salida/checkpoint-menu.md`](salida/checkpoint-menu.md).

## Datos reales cargados (PostgreSQL)

Backup completo de 9 módulos (216 tablas, 62,6M registros). Volúmenes principales:

| Dato | Cantidad |
|---|---:|
| Clientes / agentes | 78.055 |
| Créditos activos | 3.559 |
| Cuotas (77.567 pagadas) | 202.140 |
| Movimientos de cta. corriente | 7.088 |
| Turnos de crédito | 38.548 |
| Liquidaciones de juegos | 60.000 |
| Sorteos / jugadas | 3.143 |
| Resoluciones | 41.269 |
| Órdenes de pago | 3.078 |
| Seguros del agente (adicional) | 32.356 |
| Trámites de Mesa | 82.218 |
| Pases de trámites | 428.051 |
| Auditoría | 50.011 |
| Oficinas · Perfiles · Juegos | 151 · 19 · 47 |

## Pendiente (depende del organismo)

Lo que resta de mayor peso **no es programación**, sino insumos externos que no
están en el backup y hay que **relevar con Ca.Pre.S.Ca.**:
- **Imports AFIP** (comisiones de agencias, ingresos brutos de juegos).
- **Control previsional AGAP** (archivo de la provincia).
- **Layouts de banco** para acreditaciones/diskette y cancelaciones (Patagonia).

El resto de pendientes son variantes/pickers a consolidar y reportes de nicho
(ver la clasificación 🟢/🟠/🔵/⚪ en `checkpoint-menu.md`).

### Sobre `tmpdev.DBF` (1,2 GB en `prgs/`)
No es un backup del sistema, sino un **volcado desnormalizado de cuotas +
solicitud + cliente** (2,65M filas hasta 2020). Sirvió para calibrar el motor y
como banco de pruebas de equivalencia. El backup real de los DBC sigue siendo
necesario para el ETL de producción.

Ver el plan completo por fases en `salida/Analisis-CCyPP-Migracion.md`.
