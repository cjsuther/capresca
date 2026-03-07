# Módulo Interbanking Argentina — Especificación Técnica

> Addendum a la especificación general del sistema modular.
> Este documento describe exclusivamente el módulo `interbanking`, que se agrega como un servicio más dentro del mismo `docker-compose.yml`.

---

## 1. Visión General del Módulo

El módulo Interbanking actúa como **intermediario inteligente** entre el sistema interno y la API de Interbanking Argentina. Gestiona el token OAuth2 de Interbanking de forma transparente (con renovación automática), registra cada operación realizada con su resultado, y expone pantallas para que los usuarios operen cuentas, transferencias y pagos en lote.

Todo llamado a la API de Interbanking queda auditado: qué usuario del sistema lo ejecutó, qué datos envió, qué respondió Interbanking, y en qué momento.

---

## 2. Posición en la Arquitectura

```
Frontend (módulo interbanking)
        ↓
API Gateway (proxy)
        ↓
Módulo Interbanking  :8004
  ├── PostgreSQL db_interbanking
  └── API Interbanking Argentina (externa)
            POST /oauth/token
            GET  /cuentas
            GET  /cuentas/{id}/saldo
            POST /transferencias/validar
            POST /transferencias/iniciar
            GET  /transferencias/{id}/estado
            POST /pagos/lotes
            POST /pagos/lotes/{id}/procesar
            GET  /pagos/lotes/{id}/estado
```

---

## 3. Base de Datos (`db_interbanking`)

### 3.1 Configuración de Conexión a Interbanking

```sql
-- Credenciales OAuth2 de Interbanking (una por empresa/entidad)
interbanking_credentials (
  id              SERIAL PRIMARY KEY,
  name            VARCHAR(100),          -- nombre descriptivo, ej: "Empresa Principal"
  base_url        VARCHAR(255),          -- URL base de la API, configurable por entorno
  client_id       VARCHAR(255),          -- client_id de Interbanking
  client_secret   TEXT,                  -- encriptado en reposo (AES-256)
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ
)

-- Cache del token OAuth2 activo (se renueva automáticamente)
interbanking_tokens (
  id                  SERIAL PRIMARY KEY,
  credential_id       INTEGER REFERENCES interbanking_credentials,
  access_token        TEXT,
  token_type          VARCHAR(50),
  expires_at          TIMESTAMPTZ,        -- cuando vence, el módulo renueva solo
  obtained_at         TIMESTAMPTZ,
  is_active           BOOLEAN DEFAULT TRUE
)
```

### 3.2 Auditoría de Llamadas a la API

```sql
-- Registro central de CADA llamada realizada a Interbanking
api_audit_log (
  id                  BIGSERIAL PRIMARY KEY,
  user_id             INTEGER NOT NULL,     -- usuario del sistema que inició la acción
  username            VARCHAR(100),         -- snapshot del username en el momento
  credential_id       INTEGER REFERENCES interbanking_credentials,
  operation           VARCHAR(100) NOT NULL, -- ej: "LISTAR_CUENTAS", "INICIAR_TRANSFERENCIA"
  http_method         VARCHAR(10),           -- GET, POST, etc.
  endpoint            VARCHAR(255),          -- path llamado en Interbanking
  request_payload     JSONB,                 -- body enviado (sin datos sensibles: no incluye tokens)
  response_status     INTEGER,               -- HTTP status code recibido
  response_payload    JSONB,                 -- body recibido de Interbanking
  duration_ms         INTEGER,               -- tiempo de respuesta en milisegundos
  success             BOOLEAN,
  error_message       TEXT,                  -- si falló, descripción del error
  ip_address          VARCHAR(50),           -- IP del usuario que disparó la acción
  created_at          TIMESTAMPTZ DEFAULT NOW()
)
```

### 3.3 Transferencias Registradas

```sql
-- Registro de transferencias iniciadas desde este sistema
transfers (
  id                  BIGSERIAL PRIMARY KEY,
  audit_log_id        BIGINT REFERENCES api_audit_log,
  cuenta_origen       VARCHAR(100),
  cbu_destino         VARCHAR(22),
  monto               NUMERIC(15,2),
  concepto            VARCHAR(255),
  id_operacion_ib     VARCHAR(100),    -- ID devuelto por Interbanking
  status              VARCHAR(50),     -- INICIADA / PROCESANDO / ACREDITADA / RECHAZADA / ERROR
  initiated_by        INTEGER,         -- user_id
  initiated_at        TIMESTAMPTZ,
  last_status_check   TIMESTAMPTZ,
  last_status_payload JSONB
)
```

### 3.4 Lotes de Pago

```sql
-- Cabecera de lote
payment_batches (
  id                  BIGSERIAL PRIMARY KEY,
  audit_log_id        BIGINT REFERENCES api_audit_log,
  descripcion         VARCHAR(255),
  id_lote_ib          VARCHAR(100),    -- ID devuelto por Interbanking
  status              VARCHAR(50),     -- BORRADOR / ENVIADO / PROCESANDO / COMPLETADO / ERROR
  total_items         INTEGER,
  total_amount        NUMERIC(15,2),
  created_by          INTEGER,         -- user_id
  created_at          TIMESTAMPTZ,
  sent_at             TIMESTAMPTZ,
  last_status_check   TIMESTAMPTZ,
  last_status_payload JSONB
)

-- Ítems del lote
payment_batch_items (
  id              BIGSERIAL PRIMARY KEY,
  batch_id        BIGINT REFERENCES payment_batches,
  cbu             VARCHAR(22),
  monto           NUMERIC(15,2),
  detalle         VARCHAR(255),
  status_item     VARCHAR(50)    -- resultado individual tras procesamiento
)
```

---

## 4. Lógica de Gestión del Token OAuth2

El módulo maneja el token de Interbanking de forma **transparente y automática**:

```
Cada vez que se va a llamar a Interbanking:
  1. Buscar token activo en tabla interbanking_tokens
  2. Si existe y no vence en los próximos 5 minutos → usar ese token
  3. Si no existe o está por vencer:
     a. Llamar POST /oauth/token con client_id + client_secret
     b. Guardar nuevo token en interbanking_tokens
     c. Marcar token anterior como is_active=false
  4. Usar el token para la llamada real
```

Este proceso ocurre dentro del servicio Python, invisible al usuario.
La llamada a `/oauth/token` también se registra en `api_audit_log` con `operation="OBTENER_TOKEN"`, pero sin incluir el `client_secret` en `request_payload`.

---

## 5. Endpoints del Módulo (expuestos via proxy)

### Configuración

```
GET    /api/interbanking/config                         → Ver configuración activa (sin mostrar secret)
POST   /api/interbanking/config                         → Crear/actualizar credenciales
POST   /api/interbanking/config/test                    → Probar conexión (obtiene token y lo descarta)
```

### Cuentas

```
GET    /api/interbanking/cuentas                        → Listar cuentas
GET    /api/interbanking/cuentas/{id}/saldo             → Obtener saldo de una cuenta
```

### Transferencias

```
POST   /api/interbanking/transferencias/validar         → Validar CBU o Alias
POST   /api/interbanking/transferencias/iniciar         → Iniciar transferencia
GET    /api/interbanking/transferencias/{id}/estado     → Consultar estado de transferencia
GET    /api/interbanking/transferencias                 → Historial de transferencias del sistema
```

### Pagos en Lote (Batch)

```
POST   /api/interbanking/pagos/lotes                    → Crear lote de pagos
POST   /api/interbanking/pagos/lotes/{id}/procesar      → Enviar lote a procesar
GET    /api/interbanking/pagos/lotes/{id}/estado        → Consultar estado de lote
GET    /api/interbanking/pagos/lotes                    → Historial de lotes
GET    /api/interbanking/pagos/lotes/{id}/items         → Ver ítems de un lote
```

### Auditoría

```
GET    /api/interbanking/auditoria                      → Historial completo de llamadas
GET    /api/interbanking/auditoria/{id}                 → Detalle de una entrada del log
GET    /api/interbanking/auditoria/export               → Exportar log a CSV (con filtros)
```

---

## 6. Permisos del Módulo en el Sistema de Seguridad

Los siguientes permisos atómicos deben agregarse al módulo de Seguridad:

```
interbanking:config:read           → Ver configuración de credenciales
interbanking:config:write          → Crear/editar credenciales
interbanking:cuentas:read          → Consultar cuentas y saldos
interbanking:transferencias:read   → Ver historial de transferencias
interbanking:transferencias:write  → Iniciar transferencias y validar CBU
interbanking:pagos:read            → Ver lotes de pago
interbanking:pagos:write           → Crear y procesar lotes
interbanking:auditoria:read        → Ver log de auditoría
```

Roles sugeridos:
- **Operador Interbanking:** cuentas:read, transferencias:read/write, pagos:read/write
- **Auditor Interbanking:** cuentas:read, transferencias:read, pagos:read, auditoria:read
- **Admin Interbanking:** todos los permisos anteriores + config:read/write

---

## 7. Estructura del Módulo Python

```
modules/interbanking/
├── Dockerfile
├── requirements.txt       # fastapi, uvicorn, sqlalchemy, alembic, psycopg2,
│                          # httpx, cryptography, python-dotenv
├── alembic.ini
├── alembic/versions/
└── app/
    ├── main.py
    ├── config.py           # INTERBANKING_BASE_URL, DATABASE_URL, ENCRYPTION_KEY
    ├── db/
    │   ├── base.py
    │   └── session.py
    ├── models/
    │   ├── credentials.py
    │   ├── tokens.py
    │   ├── audit_log.py
    │   ├── transfers.py
    │   └── payment_batches.py
    ├── schemas/
    │   ├── credentials.py
    │   ├── transfers.py
    │   ├── payment_batches.py
    │   └── audit_log.py
    ├── routers/
    │   ├── config.py
    │   ├── cuentas.py
    │   ├── transferencias.py
    │   ├── pagos.py
    │   └── auditoria.py
    ├── services/
    │   ├── interbanking_client.py   # cliente HTTP a Interbanking, maneja token
    │   ├── token_manager.py         # lógica de renovación automática del token
    │   ├── audit_service.py         # escritura en api_audit_log
    │   ├── transfer_service.py
    │   └── batch_service.py
    └── dependencies/
        └── auth.py                  # extrae user_id del header X-User-ID (enviado por proxy)
```

### Patrón de uso del cliente HTTP

Cada router llama al `interbanking_client`, que internamente:
1. Obtiene token vigente via `token_manager`
2. Realiza la llamada HTTP a Interbanking
3. Invoca a `audit_service.log(...)` con request + response + user_id
4. Retorna el resultado al router

```python
# Pseudocódigo — services/interbanking_client.py

class InterbankingClient:
    async def call(self, user_id, operation, method, path, payload=None):
        token = await self.token_manager.get_valid_token()
        start = time.time()
        try:
            response = await httpx.request(method, f"{BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=payload)
            await self.audit.log(user_id, operation, method, path,
                payload, response.status_code, response.json(),
                int((time.time()-start)*1000), success=True)
            return response.json()
        except Exception as e:
            await self.audit.log(user_id, operation, method, path,
                payload, None, None,
                int((time.time()-start)*1000), success=False, error=str(e))
            raise
```

---

## 8. Frontend — Pantallas del Módulo

### 8.1 Menú lateral del módulo

```javascript
export const interbankingMenu = [
  { label: "Cuentas",          path: "/modules/interbanking/cuentas",       permission: "interbanking:cuentas:read",        icon: "CreditCard" },
  { label: "Transferencias",   path: "/modules/interbanking/transferencias", permission: "interbanking:transferencias:read", icon: "ArrowLeftRight" },
  { label: "Pagos en Lote",    path: "/modules/interbanking/pagos",          permission: "interbanking:pagos:read",          icon: "Layers" },
  { label: "Auditoría",        path: "/modules/interbanking/auditoria",      permission: "interbanking:auditoria:read",      icon: "ClipboardList" },
  { label: "Configuración",    path: "/modules/interbanking/config",         permission: "interbanking:config:read",         icon: "Settings" },
]
```

### 8.2 Pantalla: Cuentas (`/modules/interbanking/cuentas`)

**Sección superior — Lista de cuentas:**
- Botón "Actualizar" → llama GET /api/interbanking/cuentas
- Tabla con columnas: ID Cuenta | Denominación | Tipo | CBU | Moneda
- Cada fila tiene botón "Ver Saldo" → llama GET /api/interbanking/cuentas/{id}/saldo
- El saldo se muestra en un panel lateral o modal con: monto disponible, fecha de consulta
- Badge de estado de la última sincronización (hora + éxito/error)

### 8.3 Pantalla: Transferencias (`/modules/interbanking/transferencias`)

**Panel de nueva transferencia (si tiene permiso `transferencias:write`):**

Formulario en dos pasos:

*Paso 1 — Validar destino:*
- Campo: CBU o Alias del destinatario
- Botón "Validar" → POST /transferencias/validar
- Si válido: muestra nombre del titular, banco, tipo de cuenta
- Si inválido: mensaje de error visible

*Paso 2 — Datos de la transferencia (se habilita tras validar):*
- Selector: Cuenta origen (dropdown con las cuentas disponibles)
- Campo: Monto (numérico, con formato)
- Campo: Concepto (texto libre)
- Botón "Iniciar Transferencia" → POST /transferencias/iniciar
- Modal de confirmación antes de enviar
- Tras enviar: muestra ID de operación + botón "Consultar Estado"

**Historial de transferencias:**
- Tabla con filtros: fecha desde/hasta, estado, cuenta origen
- Columnas: Fecha | ID Operación | Origen | Destino CBU | Monto | Concepto | Estado
- Badge de estado con colores: ACREDITADA (verde), PROCESANDO (amarillo), RECHAZADA (rojo), ERROR (gris)
- Click en fila → panel de detalle con último payload de estado
- Botón "Refrescar Estado" en cada fila con estado PROCESANDO

### 8.4 Pantalla: Pagos en Lote (`/modules/interbanking/pagos`)

**Listado de lotes:**
- Tabla: Fecha | Descripción | ID Lote IB | Items | Total ($) | Estado | Acciones
- Botón "Nuevo Lote" (requiere permiso `pagos:write`)
- Click en lote → ver detalle con sus ítems

**Formulario de nuevo lote:**
- Campo: Descripción del lote
- Tabla editable de ítems (se pueden agregar/quitar filas):
  - CBU destino | Monto | Detalle/Referencia
- Fila de totales al pie: cantidad de ítems + suma total
- Botón "Guardar Borrador" → POST /pagos/lotes (crea el lote)
- Botón "Crear y Procesar" → crea el lote y luego llama /procesar en un solo flujo
- Opción de importar ítems desde CSV (parsing en el frontend)

**Detalle de lote:**
- Header: descripción, estado, totales, fecha de creación, usuario creador
- Botón "Enviar a Procesar" (si estado = BORRADOR/ENVIADO)
- Botón "Consultar Estado" → GET /pagos/lotes/{id}/estado
- Tabla de ítems con estado individual por ítem (si disponible en la respuesta)

### 8.5 Pantalla: Auditoría (`/modules/interbanking/auditoria`)

**Filtros (barra superior):**
- Filtro por usuario (selector)
- Filtro por operación (selector: LISTAR_CUENTAS, INICIAR_TRANSFERENCIA, etc.)
- Filtro por fecha (rango desde/hasta)
- Filtro por resultado (Éxito / Error)

**Tabla de registros:**
- Columnas: Fecha/Hora | Usuario | Operación | Endpoint | Status HTTP | Duración (ms) | Resultado
- Badges de resultado: verde (éxito) / rojo (error)
- Click en fila → Modal de detalle completo:
  - Request Payload (JSON formateado con syntax highlight)
  - Response Payload (JSON formateado con syntax highlight)
  - IP de origen
  - Mensaje de error (si aplica)

**Exportar:**
- Botón "Exportar CSV" → GET /api/interbanking/auditoria/export con los filtros activos

### 8.6 Pantalla: Configuración (`/modules/interbanking/config`)

- Formulario con campos:
  - Nombre de la configuración
  - URL Base de la API
  - Client ID
  - Client Secret (campo enmascarado, con botón de mostrar/ocultar)
- Botón "Guardar"
- Botón "Probar Conexión" → POST /config/test
  - Muestra resultado: éxito con el token obtenido (parcial) o error con descripción
- Panel informativo: estado del token actual (vence en X minutos / vencido)
- Solo visible para usuarios con permiso `interbanking:config:read/write`

---

## 9. Agregados al docker-compose.yml

```yaml
  # Módulo Interbanking
  interbanking:
    build: ./modules/interbanking
    environment:
      - DATABASE_URL=postgresql://ib_user:ib_pass@db_interbanking:5432/interbanking_db
      - INTERBANKING_BASE_URL=${INTERBANKING_BASE_URL}
      - ENCRYPTION_KEY=${INTERBANKING_ENCRYPTION_KEY}   # para encriptar client_secret en DB
      - SECURITY_SERVICE_URL=http://security:8001
    depends_on: [db_interbanking]
    networks: [app_network]

  db_interbanking:
    image: postgres:15
    volumes: [interbanking_data:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=interbanking_db
      - POSTGRES_USER=ib_user
      - POSTGRES_PASSWORD=ib_pass
    networks: [app_network]

volumes:
  interbanking_data:
```

### Variables de entorno a agregar en `.env`

```env
INTERBANKING_BASE_URL=https://api.interbanking.com.ar   # o URL de sandbox
INTERBANKING_ENCRYPTION_KEY=clave_aleatoria_32_bytes
INTERBANKING_DB_USER=ib_user
INTERBANKING_DB_PASS=ib_pass
```

### Agregar al proxy — nuevas rutas y permisos

```python
# En la tabla ROUTE_PERMISSIONS del proxy:
"GET /api/interbanking/config":                         "interbanking:config:read",
"POST /api/interbanking/config":                        "interbanking:config:write",
"POST /api/interbanking/config/test":                   "interbanking:config:write",
"GET /api/interbanking/cuentas":                        "interbanking:cuentas:read",
"GET /api/interbanking/cuentas/{id}/saldo":             "interbanking:cuentas:read",
"POST /api/interbanking/transferencias/validar":        "interbanking:transferencias:write",
"POST /api/interbanking/transferencias/iniciar":        "interbanking:transferencias:write",
"GET /api/interbanking/transferencias/{id}/estado":     "interbanking:transferencias:read",
"GET /api/interbanking/transferencias":                 "interbanking:transferencias:read",
"POST /api/interbanking/pagos/lotes":                   "interbanking:pagos:write",
"POST /api/interbanking/pagos/lotes/{id}/procesar":     "interbanking:pagos:write",
"GET /api/interbanking/pagos/lotes/{id}/estado":        "interbanking:pagos:read",
"GET /api/interbanking/pagos/lotes":                    "interbanking:pagos:read",
"GET /api/interbanking/auditoria":                      "interbanking:auditoria:read",
"GET /api/interbanking/auditoria/{id}":                 "interbanking:auditoria:read",
"GET /api/interbanking/auditoria/export":               "interbanking:auditoria:read",
```

---

## 10. Orden de Implementación

1. Modelos de base de datos + migraciones Alembic
2. `token_manager.py` + `audit_service.py` (infraestructura interna)
3. `interbanking_client.py` (cliente HTTP con logging automático)
4. Routers de cuentas, transferencias y pagos
5. Router de auditoría
6. Router de configuración (con encriptación del secret)
7. Agregar al docker-compose y al proxy
8. Agregar permisos en el seed del módulo Security
9. Frontend: pantallas en el orden del menú

---

## 11. Consideraciones de Seguridad

- El `client_secret` de Interbanking **nunca viaja al frontend** ni aparece en logs de auditoría
- El token OAuth2 de Interbanking tampoco se incluye en `request_payload` del audit log
- El `client_secret` se almacena encriptado en la base de datos (AES-256 via librería `cryptography`)
- La clave de encriptación vive únicamente en variable de entorno (`INTERBANKING_ENCRYPTION_KEY`)
- Los `api_audit_log` son de solo inserción; ningún endpoint permite borrar o modificar entradas
