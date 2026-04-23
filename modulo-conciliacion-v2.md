# Módulo Conciliación Juego — Especificación Técnica (v2)

> Reemplaza completamente la versión anterior.
> Cambio principal: la relación agencia↔transacción Interbanking
> se basa en CBU/cuenta, no en número de agencia.
> Los clientes persona jurídica (agencias) pueden tener múltiples CBUs registrados.

---

## 1. Concepto de Negocio

Cada agencia (cliente persona jurídica) tiene uno o más CBUs registrados.
Las transacciones de Interbanking contienen un CBU de origen o destino.
La conciliación cruza automáticamente las transacciones del día contra las agencias
buscando coincidencia de CBU. Las transacciones cuyo CBU no está registrado
en ninguna agencia quedan sin asignar y pueden vincularse manualmente.

```
Agencia "El Sol S.A."
  └── CBU: 0000003100079850010013   ←─┐
  └── CBU: 0110045220004510008682   ←─┤  match automático
                                      │
Transacción IB del día:               │
  CBU: 0000003100079850010013  ───────┘  → se asocia a "El Sol S.A."
```

---

## 2. Impacto en Módulos Existentes

### 2.1 Módulo Clientes — nueva tabla `client_cbus`

```sql
-- Modificaciones en db_clientes

-- 1. Campo de identificación interna de agencia (código de negocio, no relacionado con IB)
ALTER TABLE legal_clients ADD COLUMN agency_number VARCHAR(20) UNIQUE;
-- NULL  = cliente jurídico que no es una agencia de juego
-- Valor = código interno (ej: "0042")

-- 2. Nueva tabla: CBUs/cuentas asociados a un cliente
client_cbus (
  id              SERIAL PRIMARY KEY,
  client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  cbu             VARCHAR(22) NOT NULL,
  alias           VARCHAR(100),           -- alias del CBU si existe
  bank_name       VARCHAR(100),           -- banco (referencial, texto libre)
  account_type    VARCHAR(50),            -- 'CC' | 'CA' | 'OTRO'
  description     VARCHAR(255),           -- ej: "Cuenta cobros", "Cuenta principal"
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  created_by      INTEGER NOT NULL,       -- user_id

  UNIQUE (cbu)   -- un CBU solo puede pertenecer a un cliente
)

CREATE INDEX idx_client_cbus_active ON client_cbus(cbu) WHERE is_active = TRUE;
CREATE INDEX idx_client_cbus_client  ON client_cbus(client_id);
```

**Endpoints nuevos en el módulo Clientes:**

```
-- Via proxy (permisos normales de clientes)
GET    /api/clientes/{client_id}/cbus              → Listar CBUs del cliente
POST   /api/clientes/{client_id}/cbus              → Agregar CBU
PUT    /api/clientes/{client_id}/cbus/{cbu_id}     → Editar (alias, descripción, banco, tipo)
DELETE /api/clientes/{client_id}/cbus/{cbu_id}     → Desactivar (soft delete)

-- Internos (solo accesibles entre contenedores, nunca expuestos por el proxy)
GET    /internal/clientes/agencies
       → Agencias activas con sus CBUs
       → [{ client_id, agency_number, legal_name, tax_id,
            cbus: [{ id, cbu, alias, bank_name, account_type }] }]

GET    /internal/clientes/cbu/{cbu}
       → Busca la agencia dueña de un CBU específico
       → { client_id, agency_number, legal_name } | null
```

### 2.2 Módulo Interbanking — sin cambios de esquema

Los campos `agency_number`, `agency_assigned_by`, `agency_assigned_at` propuestos
en la versión anterior **no se agregan**. La relación agencia↔transacción
vive exclusivamente en `db_conciliacion`.

Interbanking solo expone sus transacciones con el CBU que ya contiene naturalmente:

```
GET /internal/interbanking/transactions?date=YYYY-MM-DD
    → Retorna transfers + payment_batch_items normalizados al formato unificado,
      cada uno con su campo cbu ya existente
```

---

## 3. Base de Datos del Módulo (`db_conciliacion`)

### 3.1 Registro de Conciliación por Fecha y Agencia

```sql
reconciliation_records (
  id                    BIGSERIAL PRIMARY KEY,
  reconciliation_date   DATE NOT NULL,
  client_id             INTEGER NOT NULL,        -- referencia lógica a clients.id en db_clientes
  agency_number         VARCHAR(20),             -- snapshot del código de agencia
  agency_legal_name     VARCHAR(255) NOT NULL,   -- snapshot razón social al momento de crear
  agency_tax_id         VARCHAR(30),             -- snapshot CUIT

  -- Importes
  importe_adeudado      NUMERIC(15,2) NOT NULL DEFAULT 0,
    -- Lo que la agencia debe pagar (ingresado/editado por el usuario)
  importe_premios       NUMERIC(15,2) NOT NULL DEFAULT 0,
    -- Premios pagados por la agencia (ingresado/editado por el usuario)
  importe_depositado    NUMERIC(15,2) NOT NULL DEFAULT 0,
    -- Recalculado como SUM de links activos; se persiste al consolidar
    -- para que la boleta siempre refleje el valor del momento
  importe_neto          NUMERIC(15,2) GENERATED ALWAYS AS
                          (importe_adeudado - importe_premios - importe_depositado) STORED,
    -- Calculado: adeudado - premios - depositado

  -- Estado
  status                VARCHAR(30) NOT NULL DEFAULT 'A_VERIFICAR',
    -- A_VERIFICAR | CONSOLIDADO | CONSOLIDADO_MANUAL

  -- Auditoría
  modified_by_user_id   INTEGER,
  modified_by_username  VARCHAR(100),
  modified_at           TIMESTAMPTZ,
  created_by_user_id    INTEGER NOT NULL,
  created_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (reconciliation_date, client_id)
)
```

### 3.2 Vínculos Conciliación ↔ Transacciones Interbanking

```sql
reconciliation_ib_links (
  id                        BIGSERIAL PRIMARY KEY,
  reconciliation_record_id  BIGINT NOT NULL REFERENCES reconciliation_records(id),
  ib_transaction_type       VARCHAR(20) NOT NULL,  -- 'transfer' | 'batch_item'
  ib_transaction_id         BIGINT NOT NULL,
  ib_amount                 NUMERIC(15,2) NOT NULL, -- snapshot del monto al momento de vincular
  ib_cbu                    VARCHAR(22) NOT NULL,   -- CBU de la transacción IB
  ib_concepto               VARCHAR(255),
  match_type                VARCHAR(20) NOT NULL,
    -- 'AUTO'  : CBU de la transacción está registrado en la agencia
    -- 'MANUAL': el usuario asignó la transacción a esta agencia manualmente
  linked_by_user_id         INTEGER NOT NULL,       -- 0 = sistema (match automático)
  linked_at                 TIMESTAMPTZ DEFAULT NOW(),

  -- Soft delete para conservar historial al desvincular
  unlinked_at               TIMESTAMPTZ,
  unlinked_by_user_id       INTEGER,

  UNIQUE (reconciliation_record_id, ib_transaction_type, ib_transaction_id)
)

-- Índice para encontrar rápidamente todos los links de una transacción IB
CREATE INDEX idx_ib_links_transaction
  ON reconciliation_ib_links(ib_transaction_type, ib_transaction_id)
  WHERE unlinked_at IS NULL;
```

### 3.3 Historial de Cambios de Estado e Importes

```sql
-- Log inmutable. Solo INSERT, nunca UPDATE ni DELETE.
reconciliation_status_history (
  id                          BIGSERIAL PRIMARY KEY,
  reconciliation_record_id    BIGINT NOT NULL REFERENCES reconciliation_records(id),
  previous_status             VARCHAR(30),
  new_status                  VARCHAR(30) NOT NULL,
  previous_importe_adeudado   NUMERIC(15,2),
  previous_importe_premios    NUMERIC(15,2),
  previous_importe_depositado NUMERIC(15,2),
  new_importe_adeudado        NUMERIC(15,2),
  new_importe_premios         NUMERIC(15,2),
  new_importe_depositado      NUMERIC(15,2),
  changed_by_user_id          INTEGER NOT NULL,
  changed_by_username         VARCHAR(100),
  changed_at                  TIMESTAMPTZ DEFAULT NOW(),
  notes                       TEXT
)
```

### 3.4 Cache CBU → Agencia

```sql
-- Cache local para el matching automático.
-- Evita llamar al módulo Clientes en cada transacción al cargar una fecha.
cbu_agency_cache (
  cbu             VARCHAR(22) PRIMARY KEY,
  client_id       INTEGER NOT NULL,
  agency_number   VARCHAR(20),
  legal_name      VARCHAR(255),
  cached_at       TIMESTAMPTZ DEFAULT NOW()
)
```

El cache se reconstruye:
- Al iniciar el módulo (startup event de FastAPI)
- Al recibir cualquier cambio de CBUs desde Clientes (POST /internal/conciliacion/refresh-cbu-cache)
- Como fallback, se invalida por TTL de 5 minutos

### 3.5 Template de Boleta PDF

```sql
receipt_template_config (
  id            SERIAL PRIMARY KEY,
  header_text   TEXT,
  footer_text   TEXT,
  logo_path     VARCHAR(500),
  is_active     BOOLEAN DEFAULT TRUE,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)
```

---

## 4. Lógica de Negocio

### 4.1 Carga de datos al consultar una fecha

```
GET /api/conciliacion?date=YYYY-MM-DD

Paso 1 — Refrescar cache CBU → agencia
  → Llamar GET /internal/clientes/agencies
  → Reconstruir cbu_agency_cache con todos los CBUs activos

Paso 2 — Obtener transacciones IB del día
  → Llamar GET /internal/interbanking/transactions?date=date

Paso 3 — Matching automático por CBU
  Para cada transacción IB con campo .cbu:
    → Buscar en cbu_agency_cache WHERE cbu = transaccion.cbu
    → Si match: transaction.resolved_client_id = client_id, match_type = 'AUTO'
    → Si no:    transaction.resolved_client_id = NULL

Paso 4 — Asegurar reconciliation_records para todas las agencias activas
  Para cada agencia del cache:
    → Si no existe record para (date, client_id): crear con importes = 0, status = A_VERIFICAR

Paso 5 — Sincronizar links automáticos
  Para cada transacción con resolved_client_id:
    → Buscar link activo para esta transacción (por ib_transaction_type + ib_transaction_id)
    → Si no existe: crear reconciliation_ib_links (match_type='AUTO', linked_by=0)
    → Si existe con distinto record (CBU re-asignado en Clientes):
       → Soft-delete del link anterior
       → Crear nuevo link

Paso 6 — Calcular importe_depositado de cada record
  SELECT SUM(ib_amount) FROM reconciliation_ib_links
  WHERE reconciliation_record_id = :id AND unlinked_at IS NULL

Paso 7 — Retornar
  {
    "reconciliation_records": [...],    // importes calculados, status, auditoría
    "interbanking_transactions": [...]  // con resolved_client_id, match_type, link_id
  }
```

### 4.2 Asignación manual de agencia desde la grilla IB

```
1. Usuario selecciona una transacción y elige una agencia del combo
2. Si la transacción ya tiene un link activo:
   → Soft-delete del link anterior (unlinked_at=NOW(), unlinked_by=user_id)
   → Recalcular importe_depositado del record anterior
3. Buscar o crear reconciliation_record para (date, nuevo client_id)
4. Insertar nuevo reconciliation_ib_links con match_type='MANUAL'
5. Recalcular importe_depositado del nuevo record
6. Retornar ambos records actualizados al frontend
```

### 4.3 Acción "Consolidar"

```
1. Usuario edita importe_adeudado, importe_premios
2. Usuario puede vincular manualmente transacciones IB adicionales (sin agencia)
3. Usuario puede desvincular links existentes (incluso los AUTO, si hay error)
4. Usuario elige status: CONSOLIDADO o CONSOLIDADO_MANUAL
5. Al guardar:
   a. Snapshot de valores anteriores para history
   b. Actualizar reconciliation_records
   c. Procesar ib_links_to_add:    INSERT reconciliation_ib_links (match_type='MANUAL')
   d. Procesar ib_links_to_remove: soft-delete (unlinked_at=NOW())
   e. Recalcular y persistir importe_depositado
   f. INSERT reconciliation_status_history (snapshot completo antes/después)
```

---

## 5. Endpoints del Módulo

```
-- Consulta principal
GET  /api/conciliacion?date=YYYY-MM-DD
     → { reconciliation_records: [...], interbanking_transactions: [...] }

-- Registros de conciliación
GET  /api/conciliacion/records/{id}
GET  /api/conciliacion/records/{id}/history
GET  /api/conciliacion/records/{id}/boleta           → stream PDF
PUT  /api/conciliacion/records/{id}
     Body: {
       importe_adeudado, importe_premios, status, notes,
       ib_links_to_add:    [{ ib_transaction_type, ib_transaction_id }],
       ib_links_to_remove: [link_id, ...]
     }

-- Asignación de agencia a transacción IB (flujo desde grilla IB)
PUT  /api/conciliacion/interbanking/{type}/{ib_id}/agency
     Body: { client_id }

-- Desvincular desde grilla IB
DELETE /api/conciliacion/links/{id}

-- Utilidades
GET  /api/conciliacion/agencies                      → proxy a Clientes (para combos frontend)
GET  /api/conciliacion/summary?date=YYYY-MM-DD       → totales por estado

-- Endpoint interno (llamado por módulo Clientes cuando cambian CBUs)
POST /internal/conciliacion/refresh-cbu-cache
```

---

## 6. Formato Unificado de Transacciones Interbanking

```json
{
  "id": 123,
  "type": "transfer",
  "date": "2026-03-07",
  "cbu": "0000003100079850010013",
  "concepto": "Deposito agencia",
  "amount": 75000.00,
  "status_ib": "ACREDITADA",
  "id_operacion_ib": "IB-20260307-00123",

  "resolved_client_id": 7,
  "resolved_agency_number": "0042",
  "resolved_legal_name": "Agencia El Sol S.A.",
  "match_type": "AUTO",
  "reconciliation_record_id": 15,
  "reconciliation_link_id": 88
}
```

Transacciones sin agencia:
```json
{
  "id": 124,
  "type": "batch_item",
  "cbu": "9999999999999999999999",
  "amount": 5000.00,
  "resolved_client_id": null,
  "resolved_agency_number": null,
  "resolved_legal_name": null,
  "match_type": null,
  "reconciliation_record_id": null,
  "reconciliation_link_id": null
}
```

---

## 7. Frontend — Pantallas

### 7.1 Sección CBUs en Detalle de Cliente (Módulo Clientes)

En la pantalla de detalle de un cliente persona jurídica, nueva sección al final del formulario:

```
┌──────────────────────────────────────────────────────┐
│ CBUs / Cuentas Bancarias                  [+ Agregar] │
├──────────────────────────────────────────────────────┤
│ CBU                     Alias       Banco    Tipo  Acciones │
│ 0000003100079850010013  —           Galicia  CC    ✏ 🗑 │
│ 0110045220004510008682  cta-cobros  BBVA     CA    ✏ 🗑 │
└──────────────────────────────────────────────────────┘
```

Modal "Agregar / Editar CBU":
- CBU (22 dígitos, validación numérica)
- Alias (opcional)
- Banco (texto libre, opcional)
- Tipo: `Cuenta Corriente` / `Caja de Ahorro` / `Otro`
- Descripción (opcional)

Validaciones:
- CBU de 22 dígitos exactos
- El CBU no puede estar ya registrado en otro cliente (error claro: "CBU ya registrado en [Nombre]")

### 7.2 Pantalla Principal de Conciliación (`/modules/conciliacion`)

**Header:**
```
Fecha: [ 07/03/2026 ▼ ]  [Buscar]
Resumen: ● A Verificar: 12  ● Consolidado: 8  ● Consolidado Manual: 3
Última actualización: 14:35  [↺ Actualizar]
```

---

**Grilla 1 — Conciliación de Agencias**

| # Agencia | Razón Social | CBUs | Imp. Adeudado | Imp. Premios | Imp. Depositado | Imp. Neto | Estado | Usuario Modifica | Fecha Modificación | Acciones |
|-----------|-------------|------|--------------|-------------|----------------|---------|--------|-----------------|-------------------|----------|

- Columna **CBUs**: badge con cantidad (ej: `2 CBUs`). Tooltip al hover lista los CBUs de la agencia
- **Imp. Neto**: rojo si > 0 (todavía adeuda), verde si ≤ 0 (cubierto o superado)
- Badges de estado: `A_VERIFICAR` naranja | `CONSOLIDADO` verde | `CONSOLIDADO_MANUAL` azul
- **Acciones:**
  - 📄 **Descargar Boleta** → GET /records/{id}/boleta
  - ✏️ **Consolidar** → abre panel lateral

---

**Panel lateral de Consolidación:**

```
┌────────────────────────────────────────────────────┐
│ Agencia 0042 — Agencia El Sol S.A.                 │
│ CBUs: 0000003100079850010013                       │
│       0110045220004510008682                       │
│ Fecha: 07/03/2026                                  │
├────────────────────────────────────────────────────┤
│ Importe Adeudado:    [ 100.000,00 ]  ← editable    │
│ Importe Premios:     [  20.000,00 ]  ← editable    │
│ Importe Depositado:  [  75.000,00 ]  ← solo lectura│
│                       (suma de transacciones vinc.)│
│ Importe Neto:        [   5.000,00 ]  ← solo lectura│
├────────────────────────────────────────────────────┤
│ Estado:                                            │
│   ○ A Verificar                                    │
│   ○ Consolidado                                    │
│   ● Consolidado Manual                             │
├────────────────────────────────────────────────────┤
│ Observaciones: [________________________________]  │
├────────────────────────────────────────────────────┤
│ TRANSACCIONES VINCULADAS                           │
│                                                    │
│  ┌ Automáticas (match por CBU) ─────────────────┐ │
│  │ ✅AUTO IB-001 │ CBU:000000... │ $75.000 [🔗]  │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌ Agregar manualmente ─────────────────────────┐ │
│  │ ☐ IB-004 │ CBU:999999... │ $5.000            │ │
│  │ ☐ IB-005 │ CBU:888888... │ $3.000            │ │
│  │ (solo transacciones aún sin agencia)          │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  El ícono [🔗] desvincula una transacción AUTO     │
│  El checkbox marca/desmarca vínculos manuales      │
│  Imp. Depositado se recalcula en tiempo real       │
├────────────────────────────────────────────────────┤
│            [Cancelar]    [Guardar cambios]         │
└────────────────────────────────────────────────────┘
```

---

**Grilla 2 — Transacciones Interbanking del Día**

| Tipo | ID Operación IB | CBU | Concepto | Importe | Estado IB | Agencia Asignada | Match | Acciones |
|------|----------------|-----|---------|---------|----------|-----------------|-------|---------|

- **Agencia Asignada**: `"0042 — El Sol S.A."` o badge gris `"Sin agencia"`
- **Match**: badge `AUTO` verde | `MANUAL` azul | `—` si sin agencia
- **Acciones:**
  - Sin agencia: 🏢 **Asignar Agencia**
  - Con agencia: 🔄 **Cambiar** | 🔗 **Desvincular**
- **Filtros:** Todas | Sin agencia | Automáticas | Manuales

**Modal "Asignar / Cambiar Agencia":**

```
┌──────────────────────────────────────────┐
│ Asignar agencia a transacción            │
├──────────────────────────────────────────┤
│ Transacción: IB-20260307-00124           │
│ CBU:         9999999999999999999999      │
│ Importe:     $5.000,00                   │
├──────────────────────────────────────────┤
│ Agencia: [ buscar por nro, nombre... ▼ ] │
│                                          │
│ ⚠ El CBU de esta transacción no está    │
│   registrado en la agencia seleccionada. │
│   El vínculo se marcará como MANUAL.     │
├──────────────────────────────────────────┤
│         [Cancelar]    [Asignar]          │
└──────────────────────────────────────────┘
```

El aviso de advertencia desaparece si el CBU sí está registrado en la agencia elegida
(en ese caso el vínculo se crea como AUTO, aunque fue seleccionado manualmente —
indica que el match automático debería haberlo encontrado, posible dato faltante en Clientes).

---

## 8. Estructura del Módulo Python

```
modules/conciliacion/
├── Dockerfile
├── requirements.txt        # fastapi, uvicorn, sqlalchemy, alembic, psycopg2,
│                           # httpx, reportlab
├── alembic/
└── app/
    ├── main.py             # startup: reconstruir cbu_agency_cache
    ├── config.py
    ├── db/
    ├── models/
    │   ├── reconciliation_record.py
    │   ├── reconciliation_ib_link.py
    │   ├── reconciliation_status_history.py
    │   └── cbu_agency_cache.py
    ├── schemas/
    │   ├── reconciliation.py
    │   └── ib_transaction.py
    ├── routers/
    │   ├── conciliacion.py
    │   ├── links.py
    │   ├── boleta.py
    │   └── internal.py            # POST /internal/conciliacion/refresh-cbu-cache
    ├── services/
    │   ├── reconciliation_service.py
    │   ├── matching_service.py    # lógica CBU → agencia + sync de links
    │   ├── link_service.py
    │   ├── cbu_cache_service.py   # construcción y consulta del cache
    │   ├── clientes_client.py
    │   ├── interbanking_client.py
    │   └── pdf_service.py
    └── dependencies/
        └── auth.py
```

---

## 9. Docker Compose — Agregados

```yaml
  conciliacion:
    build: ./modules/conciliacion
    environment:
      - DATABASE_URL=postgresql://concil_user:concil_pass@db_conciliacion:5432/conciliacion_db
      - CLIENTES_SERVICE_URL=http://clientes:8003
      - INTERBANKING_SERVICE_URL=http://interbanking:8004
    depends_on: [db_conciliacion, clientes, interbanking]
    networks: [app_network]

  db_conciliacion:
    image: postgres:15
    volumes: [conciliacion_data:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=conciliacion_db
      - POSTGRES_USER=concil_user
      - POSTGRES_PASSWORD=concil_pass
    networks: [app_network]

volumes:
  conciliacion_data:
```

---

## 10. Rutas a agregar en el Proxy

```python
"GET /api/conciliacion":                                "conciliacion:read",
"GET /api/conciliacion/records/{id}":                   "conciliacion:read",
"GET /api/conciliacion/records/{id}/history":           "conciliacion:read",
"GET /api/conciliacion/records/{id}/boleta":            "conciliacion:download",
"PUT /api/conciliacion/records/{id}":                   "conciliacion:write",
"PUT /api/conciliacion/interbanking/{type}/{id}/agency":"conciliacion:write",
"DELETE /api/conciliacion/links/{id}":                  "conciliacion:write",
"GET /api/conciliacion/agencies":                       "conciliacion:read",
"GET /api/conciliacion/summary":                        "conciliacion:read",

# Endpoints de CBUs en módulo Clientes (nuevos)
"GET /api/clientes/{id}/cbus":                          "clientes:clients:read",
"POST /api/clientes/{id}/cbus":                         "clientes:clients:write",
"PUT /api/clientes/{id}/cbus/{cbu_id}":                 "clientes:clients:write",
"DELETE /api/clientes/{id}/cbus/{cbu_id}":              "clientes:clients:write",

# /internal/* nunca se expone por el proxy
```

---

## 11. Resumen de Tablas

### `db_conciliacion` (módulo nuevo)

| Tabla | Descripción | Clave |
|-------|-------------|-------|
| `reconciliation_records` | Un registro por (fecha, agencia). Importes y estado. | UNIQUE (date, client_id) |
| `reconciliation_ib_links` | Vínculo record↔transacción IB. AUTO o MANUAL. Soft delete. | UNIQUE (record, type, ib_id) |
| `reconciliation_status_history` | Log inmutable de cambios. Solo INSERT. | — |
| `cbu_agency_cache` | Cache CBU→agencia para matching rápido. | PK: cbu |
| `receipt_template_config` | Template de boleta PDF. | — |

### Modificaciones en módulos existentes

| Módulo | Tabla | Cambio |
|--------|-------|--------|
| Clientes | `legal_clients` | + `agency_number VARCHAR(20) UNIQUE` |
| Clientes | `client_cbus` | **Nueva tabla** — CBUs por cliente |
| Interbanking | `transfers` | Sin cambios |
| Interbanking | `payment_batch_items` | Sin cambios |

---

## 12. Resumen General del Sistema

| Módulo | Puerto | Base de Datos |
|--------|--------|--------------|
| Security | :8001 | db_security |
| Cajeros | :8002 | db_cajeros |
| Clientes | :8003 | db_clientes |
| Interbanking | :8004 | db_interbanking |
| Notifications | :8005 | db_notifications |
| Conciliación | :8006 | db_conciliacion |
