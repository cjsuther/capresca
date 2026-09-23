# CCyPP — Sistema nuevo (Ca.Pre.S.Ca.)

Reescritura del sistema de gestión de la **Caja de Prestaciones Sociales de
Catamarca** (originalmente en Visual FoxPro) sobre un stack moderno.

> **Estado (2026-09-22):** módulo **Créditos de Portezuelo** — sólo el circuito de créditos (30 pantallas
> en el frontend del sistema + portal ciudadano), **246 tests** de backend, sobre **PostgreSQL con el
> backup real cargado**. Las demás áreas de CCyPP se retiraron (H-210, H-211). Hallazgos en
> [`salida/hallazgos.md`](salida/hallazgos.md); el relevamiento histórico de la migración sigue en `salida/`.

## Stack

| Capa | Tecnología |
|---|---|
| Backend / API | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic |
| Base de datos | PostgreSQL 16 |
| Frontend | Backoffice: módulo del frontend de Portezuelo (React 18 + JSX + Tailwind) · Portal: React 18 + Vite + TypeScript |
| Orquestación | Docker + docker-compose |

## Integración con Portezuelo

Este sistema es el módulo **Créditos** de Portezuelo (sistema modular). Corre con el resto del stack
desde el `docker-compose.yml` de la raíz:

| Pieza | Servicio | Publicado en |
|---|---|---|
| API (FastAPI) | `creditos` (:8010) | `/api/creditos/*` **vía gateway** · `/api/creditos/portal/*` directo (portal) |
| Base de datos | `db_creditos` (Postgres 16) | — |
| Backoffice (React) | `frontend` de Portezuelo | `/modules/creditos/` (`frontend/src/modules/creditos/`) |
| Portal ciudadano (React) | `creditos-portal` | `/portal-creditos/` |

**Seguridad.** No hay login propio en el backoffice: se entra por el login de Portezuelo y el Dashboard
muestra la tarjeta *Créditos* a quien tenga algún permiso del módulo. El gateway valida el JWT del sistema,
resuelve los permisos contra `security` y reenvía `X-User-Id` / `X-Username` / `X-User-Permissions`
(`app/core/gateway.py`). El `Usuario` local se crea en el primer acceso, vinculado por username, sólo para
auditoría y workflow.

**Alcance.** El módulo es sólo el **circuito de créditos**. Las demás áreas de CCyPP (caja de ventanilla,
contabilidad, tesorería, seguros, despacho, mesa de entradas, juegos, tablas generales, seguridad) no se
migraron a Portezuelo: no tienen pantallas, endpoints ni permisos. Lo que el crédito necesita de ellas por
dentro sigue: asiento contable al originar/cobrar, póliza al otorgar, orden de pago del desembolso y recibo de
la cancelación anticipada.

**Permisos** (Seguridad de Portezuelo → módulo *Créditos*):

| Permiso | Habilita |
|---|---|
| `creditos:read` / `creditos:write` | Ver / operar el módulo |
| `aprobaciones:aprobar` | Rol **APROBAR** de los niveles del workflow (cuatro-ojos) |
| `aprobaciones:supervisar` | Rol **SUPERVISAR** (niveles de supervisión, N-ojos) |

El gateway exige `GET → creditos:read` y el resto de los métodos `creditos:write`
(`proxy/app/routes/mapping.py`); sólo reenvía los recursos del circuito de créditos. Diseñar/editar créditos
exige `creditos:write`; aprobar, un permiso de aprobación. Configurar el workflow se hace en Configuraciones
con su propio permiso (no alcanza con `creditos:write`: quien carga créditos no puede sacarse su propio
control). Usuarios, perfiles y grupos del sistema VFP ya no autorizan nada.

**Configuración compartida.** Impuestos, índices de referencia, feriados y las reglas del workflow de
aprobaciones se administran en el módulo **Configuraciones** (`modules/configuraciones`) y Créditos los
lee por su API interna. Tras levantarlo por primera vez, migrar lo que había en Créditos:
`docker compose exec creditos python -m app.etl.migrar_configuraciones` (idempotente).

**Portal ciudadano.** Tiene su propio realm (SSO Mi Catamarca, tokens `scope=portal` firmados con
`CREDITOS_PORTAL_JWT_SECRET`) y nginx lo manda directo al módulo, sin gateway. Sin credenciales de Mi
Catamarca el login del portal responde 503, salvo `CREDITOS_PORTAL_MOCK_SSO=true` (sólo demo/QA).

#### SSO Mi Catamarca (OIDC)

Authorization Code + PKCE contra el proveedor de la Dirección Provincial de Sistema. El navegador nunca
ve el `code` ni el secreto: el callback es del backend (`app/api/portal.py`) y el proveedor vive en
`app/services/mi_catamarca.py`.

| Variable | Para qué |
|---|---|
| `MICATAMARCA_CLIENT_ID` / `MICATAMARCA_CLIENT_SECRET` | Credenciales del cliente (sólo por entorno, nunca en el repo) |
| `MICATAMARCA_ISSUER` | Entorno del proveedor. Producción `https://api-mi.catamarca.gob.ar/openid`; desarrollo `https://develop-api-mi.catamarca.gob.ar/openid`. Los endpoints (`/authorize`, `/token`, `/userinfo`, `/jwks`) se derivan de acá |
| `MICATAMARCA_SCOPES` | `openid profile email` (lo concedido a este cliente; pedir `phone` sin tenerlo otorgado hace fallar la autorización) |
| `MICATAMARCA_PKCE` | `true` por defecto; apagarlo sólo si el proveedor rechaza el `code_challenge` |
| `CREDITOS_PUBLIC_URL` | De acá sale el callback que hay que **registrar en Mi Catamarca**: `${CREDITOS_PUBLIC_URL}/api/creditos/portal/auth/callback` |

Del ID Token se verifican firma y claims (`iss`, `aud`, `exp`, `nonce`) y que el `sub` del `/userinfo`
sea el mismo. El proveedor está detrás de un WAF que desafía a los clientes que no son navegador: si el
`/jwks` no se puede traer, los claims se validan igual y queda el aviso en el log (el token llegó por el
canal trasero TLS de `/token`, la excepción de OIDC Core 3.1.3.7). Si el WAF también bloquea `/token`,
hay que pedirle a la Dirección de Sistema que habilite la IP del servidor.

### Puesta en marcha

```bash
# 1) Variables en el .env de la raíz: CREDITOS_DB_USER/PASS/NAME, CREDITOS_PORTAL_JWT_SECRET,
#    CREDITOS_PUBLIC_URL, CREDITOS_BASES_HOST_PATH, MICATAMARCA_CLIENT_ID/SECRET (ver README raíz)
docker compose up -d --build creditos creditos-portal frontend proxy security nginx

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

El backoffice no vive acá: es `frontend/src/modules/creditos/` en el frontend de Portezuelo (pantallas
en `pages/creditos/`, componentes compartidos en `components/`, cliente HTTP en
`frontend/src/api/creditos.js`). La SPA propia que se publicaba en `/creditos/` se retiró; nginx
redirige esa ruta a `/modules/creditos/`.

```
backend/
  app/
    domain/        # ← lógica de negocio portada del VFP (set_class.prg)
      cuotas.py    #   planes de amortización (francés/alemán/directo/tipo 5)
      mora.py      #   punitorios y resarcitorios
      margen.py    #   margen de afectación + validación de CUIL
      carteras.py  #   matriz de compatibilidad de carteras
    api/           # routers FastAPI del circuito de créditos (productos, solicitudes, contratos,
                   #   creditos, consultas, clientes-espejo, admin de líneas/parámetros, portal…)
    services/      # lógica; contabilidad/seguros/egresos/caja quedan sólo para lo que usa el crédito
    etl/           # loaders VFP-DBF → PostgreSQL (cargar_todo + por módulo)
    reports/       # PDF (reportlab) y Excel (openpyxl), con patrón write-only
    core/          # config, database, gateway (identidad de Portezuelo), permisos, pagination
    models.py      # modelos SQLAlchemy · schemas.py  Pydantic
    seed.py        # datos demo (reemplazado por el ETL en producción)
  tests/           # 118 tests (motor, equivalencia real, API por módulo)
  alembic/         # migraciones de esquema
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

## Pantallas

El backoffice (30 pantallas del circuito de créditos) vive en `frontend/src/modules/creditos/` del frontend
de Portezuelo; el detalle está en su `menu.js`. Las pantallas de Caja, Tesorería, Contabilidad, Seguros,
Despacho, Juegos, Mesa de Entradas y Tablas generales que tenía la SPA de CCyPP se retiraron (H-210, H-211);
el relevamiento histórico sigue en [`salida/estado-migracion.md`](salida/estado-migracion.md).

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
