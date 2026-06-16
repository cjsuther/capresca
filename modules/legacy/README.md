# Módulo Legacy — Integración con el sistema VFP9 (DBF)

Capa **anti-corrupción** entre el sistema modular nuevo y el sistema legacy
(Visual FoxPro 9, tablas DBF en `\\192.168.0.7\agjs\`). Es la **única** pieza con
acceso a las DBF; el resto de los módulos hablan con él por HTTP interno. Está
diseñado para ser **apagable**: cuando el legacy se apague, se detiene este módulo
y el resto del sistema sigue funcionando con sus propios datos.

- Puerto: **8009** · Base de datos: **`db_legacy`** (Postgres propio)
- Stack: FastAPI + SQLAlchemy + Alembic + APScheduler + `dbfread`/`dbf`

---

## Arquitectura

```
                         ┌──────────────────────── módulo legacy (8009) ───────────────────────┐
  DBF legacy (SMB :ro)   │  dbf_reader ──► sync_service ──► mirror_* (Postgres)  ◄── lecturas    │
  caja/ juegos/ creditos │                     │                                     internas   │
  general/ contabilidad  │                     └─► interaction_log (IN)                          │
                         │                                                                      │
  otros módulos ──HTTP──►│  /internal/legacy/*  (lecturas del mirror + encolar escrituras)       │
                         │                                                                      │
  escrituras ───────────►│  outbox  ──► drain (dry_run | real-sandbox) ─► dbf_writer ─► OUT log  │
                         └──────────────────────────────────────────────────────────────────────┘
```

- **Mirror**: las tablas legacy se espejan en Postgres (`mirror_*`). Los
  consumidores leen del mirror (rápido y resiliente), no del DBF directo.
- **Outbox**: toda escritura se **encola** (202) y se aplica luego; nunca se
  escribe en caliente sobre las DBF.
- **interaction_log**: ledger de cada interacción IN (lectura) y OUT (escritura),
  consultable por fecha y base de datos desde el frontend.

---

## Puesta en producción ⚠️

El módulo está completo y verificado en desarrollo (con DBFs sintéticos). Para
operar contra el legacy real faltan **3 pasos** que dependen del entorno:

### 1. Confirmar los nombres reales de campos DBF
Los nombres de campo en `app/sync_spec.py` son **provisionales** (derivados de la
documentación, ≤10 caracteres por el límite de FoxPro). Con una muestra de las
DBF reales (o su estructura), ajustar **solo ese archivo**: cada tabla declara
`(atributo_mirror, "CAMPO_DBF", coerción)`. La lectura es case-insensitive.

> Tip para inspeccionar una DBF real:
> ```python
> from dbfread import DBF
> t = DBF("/data/agjs/caja/cajaliq.dbf", encoding="latin-1")
> print([(f.name, f.type, f.length) for f in t.fields])
> ```

### 2. Montar el share SMB/CIFS real
Montar `\\192.168.0.7\agjs` en el host (read-only para lectura) y apuntar la
variable `LEGACY_SHARE_HOST_PATH` a ese punto de montaje. El contenedor lo ve en
`/data/agjs` (bind-mount `:ro`). Verificar con `GET /api/legacy/status` (sección
`smb`: `mounted` y `tables_present`).

Ejemplo de montaje en el host (Linux):
```bash
sudo mount -t cifs //192.168.0.7/agjs /mnt/agjs -o ro,username=...,password=...,vers=3.0
# y en .env:  LEGACY_SHARE_HOST_PATH=/mnt/agjs
```

### 3. Definir el REINDEX en VFP antes de habilitar escritura productiva
La librería `dbf` (Python) **no mantiene los índices `.CDX`** de FoxPro. Escribir
en DBF vivas sin regenerar el `.CDX` los desincroniza y el legacy ve índices
corruptos. Como no hay host Windows con el driver VFP OLEDB, el **drenado real
productivo queda fuera de alcance** hasta resolver una de estas opciones:

- **(Recomendada)** un micro-agente en cualquier PC Windows de la LAN que aplique
  las operaciones vía VFP/OLEDB (mantiene índices nativamente), o
- un paso de **runbook** que ejecute `REINDEX` en VFP al inicio de jornada tras el
  drenado en ventana de mantenimiento.

Mientras tanto, el drenado real solo está permitido contra una **copia sandbox**
(ver más abajo) y el productivo devuelve `409`.

---

## Configuración (variables de entorno)

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | — | Postgres del módulo (`db_legacy`) |
| `SMB_MOUNT_ROOT` | `/data/agjs` | Raíz del share legacy dentro del contenedor (`:ro`) |
| `LEGACY_SHARE_HOST_PATH` | `./externalfiles` | Ruta del share en el HOST (montar el real en prod) |
| `INTEGRATION_ENABLED` | `true` | **Kill switch**. `false` → no se toca el legacy |
| `WRITE_MODE` | `outbox_only` | Modo de escritura (siempre vía outbox) |
| `ALLOW_REAL_DRAIN` | `false` | Habilita el drenado real **solo sandbox** (`true`) |
| `SANDBOX_WRITE_ROOT` | `/data/agjs_sandbox` | Copia escribible para el drenado real de prueba |
| `LEGACY_SANDBOX_HOST_PATH` | `./externalfiles/_sandbox` | Ruta del sandbox en el HOST |
| `INTERNAL_API_KEY` | — | API key para los endpoints `/internal/legacy/*` |
| `SYNC_ENABLED` | `true` | Activa el scheduler de sincronización |
| `SYNC_CAJA_MINUTES` | `10` | Cadencia de sync de caja |
| `SYNC_CREDITOS_MINUTES` | `60` | Cadencia de sync de créditos |
| `SYNC_MAESTROS_MINUTES` | `1440` | Cadencia de sync de maestros |

Los consumidores (`clientes`, `liquidaciones`, `conciliacion`) usan
`LEGACY_SERVICE_URL` y `LEGACY_INTERNAL_API_KEY`.

---

## Comportamiento "apagable"

- `INTEGRATION_ENABLED=false`:
  - lecturas internas siguen sirviendo **desde el mirror** (los datos ya viven en
    Postgres) → los consumidores no se enteran;
  - el scheduler de sync se detiene;
  - las escrituras (encolar / sync on-demand) devuelven **`410 Gone`**.
- Apagado total: `docker compose stop legacy db_legacy`. Cada consumidor tiene
  `legacy_client.py` con timeout + fallback, así que **degrada sin romper**.
- Apagado definitivo del legacy: con el outbox vacío y el último sync OK, los
  datos quedan en el mirror; el módulo se puede detener y eliminar.

---

## Endpoints

### Administración / diagnóstico — vía proxy `/api/legacy/*`
| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| GET | `/interactions` | `legacy:interactions:read` | Ledger IN/OUT (filtros: `date_from`,`date_to`,`database`,`direction`,`table`,`status`,`page`) |
| GET | `/interactions/{id}` | `legacy:interactions:read` | Detalle de una interacción |
| GET | `/status` | `legacy:interactions:read` | Kill switch, salud SMB, sync por tabla, outbox pendiente |
| GET | `/databases` | `legacy:interactions:read` | Bases lógicas (caja/juegos/creditos/general/contabilidad) |
| GET | `/outbox` | `legacy:admin:read` | Cola de escrituras |
| POST | `/sync/{tabla}` | `legacy:admin:write` | Sync on-demand de una tabla |
| POST | `/outbox/drain?mode=dry_run\|real` | `legacy:admin:write` | Drenado (real requiere `ALLOW_REAL_DRAIN`) |

### Internos (contenedor-a-contenedor) — `/internal/legacy/*` (header `X-Api-Key`)
- Lecturas (sirven del mirror): `GET /agencias`, `/juegos`, `/maeclientes`,
  `/cajaliq`, `/pagos`, `/formas-pago`, `/creditos-seguros`.
- Escrituras (encolan en el outbox → 202): `POST /pagos`,
  `POST /pagos/{no_recibo}/anular`, `POST /creditos/consolidar`.
- Estado: `GET /outbox/{id}`, `GET /ping`.

---

## Frontend

Módulo `legacy` en el frontend (`frontend/src/modules/legacy/`):
- **Interacciones**: tabla del ledger con filtros por **fecha** y **base de datos**
  (+ dirección/tabla/estado), filas expandibles con payload y errores.
- **Estado**: salud SMB por base de datos, sync por tabla, outbox pendiente.

Permisos (módulo `legacy`): `interactions:read`, `admin:read`, `admin:write`.

---

## Operación

```bash
# Sync on-demand de una tabla
curl -X POST http://<host>/api/legacy/sync/maeagencias -H "Authorization: Bearer <jwt>"

# Drenado en seco (no toca DBF; registra qué haría)
curl -X POST "http://<host>/api/legacy/outbox/drain?mode=dry_run" -H "Authorization: Bearer <jwt>"

# Drenado real — SOLO sandbox; requiere ALLOW_REAL_DRAIN=true
curl -X POST "http://<host>/api/legacy/outbox/drain?mode=real" -H "Authorization: Bearer <jwt>"
```

---

## Desarrollo y pruebas

Sin DBFs reales, se prueba con DBFs sintéticos (en `externalfiles/`, que está en
`.gitignore`):
- `externalfiles/_gen_fake.py` → DBFs de lectura en `externalfiles/{juegos,caja}/`.
- `externalfiles/_gen_sandbox.py` → DBFs escribibles en `externalfiles/_sandbox/`.

Generarlos con la imagen del módulo (trae la librería `dbf`):
```bash
docker compose run --rm --no-deps legacy python /data/agjs/_gen_fake.py
docker compose run --rm --no-deps legacy python /data/agjs/_gen_sandbox.py
```

> Nota: en producción NO usar `externalfiles` como share; montar el SMB real
> (paso 2) y, si se habilita escritura, resolver el REINDEX en VFP (paso 3).
