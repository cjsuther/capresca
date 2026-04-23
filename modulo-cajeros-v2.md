# Módulo Cajeros — Especificación Técnica (v2)

> Reemplaza completamente la especificación anterior del módulo Cajeros.
> Se eliminan: Autorizaciones, Relaciones, Límites, Operaciones.
> Se agregan: Administración de Autorizaciones y Transacciones con flujo de aprobación.

---

## 1. Concepto de Negocio (revisado)

El módulo permite definir **reglas de autorización por cajero**: si un cajero registra una transacción que supera el monto configurado para una moneda (ya sea globalmente o por referencia), la transacción queda en estado "Pendiente de Autorización" y se notifica al autorizador designado. El autorizador puede aprobarla o rechazarla. Si no supera ningún límite, se procesa directamente.

---

## 2. Base de Datos (`db_cajeros`)

### 2.1 Reglas de Autorización

```sql
-- Define qué autorizador actúa para qué cajero, moneda y monto
authorization_rules (
  id                  SERIAL PRIMARY KEY,
  cajero_user_id      INTEGER NOT NULL,     -- referencia lógica al user_id de Security
  cajero_username     VARCHAR(100),         -- snapshot denormalizado
  authorizer_user_id  INTEGER NOT NULL,     -- referencia lógica al user_id de Security
  authorizer_username VARCHAR(100),         -- snapshot denormalizado
  currency            VARCHAR(10) NOT NULL, -- ARS, USD, EUR, etc.
  amount_limit        NUMERIC(15,2) NOT NULL,
  reference           VARCHAR(255),         -- NULL = aplica a la suma total de transacciones
                                            -- valor = aplica solo a transacciones con esa referencia
  is_active           BOOLEAN DEFAULT TRUE,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  created_by          INTEGER NOT NULL      -- user_id de quien creó la regla
)
```

**Lógica de evaluación al crear una transacción:**

```
Para cada transacción nueva del cajero con (moneda, monto, referencia):

1. Buscar reglas activas donde cajero_user_id = usuario_actual AND currency = moneda

2. Para cada regla encontrada:
   a. Si regla.reference IS NOT NULL:
      - Sumar monto de todas las transacciones NO eliminadas con misma referencia
        + el monto nuevo
      - Si suma > regla.amount_limit → requiere autorización
   b. Si regla.reference IS NULL:
      - Sumar monto de todas las transacciones NO eliminadas para esa moneda
        + el monto nuevo
      - Si suma > regla.amount_limit → requiere autorización

3. Si ninguna regla se dispara → estado = PROCESADA
4. Si al menos una regla se dispara → estado = PENDIENTE_AUTORIZACION
   - Asociar los autorizadores de todas las reglas disparadas
```

### 2.2 Transacciones

```sql
-- Transacciones registradas por cajeros
transactions (
  id                  BIGSERIAL PRIMARY KEY,
  cajero_user_id      INTEGER NOT NULL,
  cajero_username     VARCHAR(100),
  authorizer_user_id  INTEGER,             -- NULL si no requirió autorización
  authorizer_username VARCHAR(100),
  currency            VARCHAR(10) NOT NULL,
  amount              NUMERIC(15,2) NOT NULL,
  reference           VARCHAR(255),        -- referencia de la transacción
  description         TEXT,
  status              VARCHAR(50) NOT NULL,
    -- PROCESADA | PENDIENTE_AUTORIZACION | AUTORIZADA | RECHAZADA | ELIMINADA
  rejection_reason    TEXT,                -- motivo cuando status = RECHAZADA
  authorized_at       TIMESTAMPTZ,         -- fecha de autorización o rechazo
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),  -- se actualiza en cada cambio de estado
  created_by          INTEGER NOT NULL
)

-- Vínculo entre transacción y las reglas que la dispararon
transaction_rule_triggers (
  id              SERIAL PRIMARY KEY,
  transaction_id  BIGINT REFERENCES transactions,
  rule_id         INTEGER REFERENCES authorization_rules,
  authorizer_user_id INTEGER NOT NULL      -- snapshot del autorizador en el momento
)
```

---

## 3. Endpoints

### Reglas de Autorización

```
GET    /api/cajeros/rules                  → Listar reglas (con filtros: cajero, moneda)
POST   /api/cajeros/rules                  → Crear regla
DELETE /api/cajeros/rules/{id}             → Eliminar regla (soft delete: is_active=false)
```

### Transacciones

```
POST   /api/cajeros/transactions           → Crear transacción (evalúa reglas automáticamente)
GET    /api/cajeros/transactions           → Listar transacciones (lógica de visibilidad por permiso)
GET    /api/cajeros/transactions/{id}      → Detalle de transacción
PUT    /api/cajeros/transactions/{id}/authorize   → Autorizar transacción (solo autorizador)
PUT    /api/cajeros/transactions/{id}/reject      → Rechazar transacción (solo autorizador, requiere motivo)
DELETE /api/cajeros/transactions/{id}      → Marcar como ELIMINADA (cajero dueño o admin)
```

**Lógica de visibilidad en GET /transactions:**
- Si tiene permiso `cajeros:transactions:read_all` → ve todas
- Si no → ve solo donde `cajero_user_id = yo` OR `authorizer_user_id = yo`
- Orden: primero PENDIENTE_AUTORIZACION, luego por `updated_at` DESC

**Al crear una transacción (POST):**
1. Evaluar reglas → determinar status
2. Guardar transacción
3. Si status = PENDIENTE_AUTORIZACION → disparar notificación al/los autorizadores via módulo de Notificaciones

**Al autorizar/rechazar:**
1. Validar que `request.user_id == transaction.authorizer_user_id`
2. Actualizar status, `authorized_at = NOW()`, `updated_at = NOW()`
3. Si rechazada: guardar `rejection_reason`

**Al eliminar:**
1. Validar que status == PENDIENTE_AUTORIZACION
2. Validar que `request.user_id == cajero_user_id` OR usuario tiene permiso admin
3. Cambiar status = ELIMINADA, `updated_at = NOW()`

---

## 4. Permisos del Módulo

```
cajeros:rules:read               → Ver reglas de autorización
cajeros:rules:write              → Crear/eliminar reglas
cajeros:transactions:read        → Ver transacciones propias (como cajero o autorizador)
cajeros:transactions:read_all    → Ver transacciones de todos los usuarios
cajeros:transactions:write       → Crear transacciones
cajeros:transactions:authorize   → Autorizar o rechazar transacciones
cajeros:transactions:delete      → Eliminar (marcar como ELIMINADA) transacciones propias
cajeros:transactions:admin       → Eliminar cualquier transacción + read_all
```

---

## 5. Integración con Módulo de Notificaciones

El módulo Cajeros llama al servicio de notificaciones en los siguientes eventos:

| Evento | Destinatario | Mensaje | Destino al hacer click |
|--------|-------------|---------|----------------------|
| Transacción supera límite | Autorizador(es) | "Nueva transacción pendiente de autorización de {cajero} por {monto} {moneda}" | `/modules/cajeros/transactions/{id}` |
| Transacción autorizada | Cajero | "Tu transacción #{id} fue autorizada por {autorizador}" | `/modules/cajeros/transactions/{id}` |
| Transacción rechazada | Cajero | "Tu transacción #{id} fue rechazada: {motivo}" | `/modules/cajeros/transactions/{id}` |

Llamada interna al servicio de notificaciones:
```python
await notifications_client.create(
    user_id=authorizer_user_id,
    title="Transacción pendiente de autorización",
    message=f"Nueva transacción de {cajero_username} por {amount} {currency}",
    module="cajeros",
    entity_type="transaction",
    entity_id=transaction.id,
    redirect_path=f"/modules/cajeros/transactions/{transaction.id}"
)
```

---

## 6. Frontend — Pantallas

### 6.1 Menú lateral

```javascript
export const cajerosMenu = [
  {
    label: "Transacciones",
    path: "/modules/cajeros/transactions",
    permission: "cajeros:transactions:read",
    icon: "Receipt"
  },
  {
    label: "Nueva Transacción",
    path: "/modules/cajeros/transactions/new",
    permission: "cajeros:transactions:write",
    icon: "PlusCircle"
  },
  {
    label: "Administración de Autorizaciones",
    path: "/modules/cajeros/rules",
    permission: "cajeros:rules:read",
    icon: "ShieldCheck"
  },
]
```

---

### 6.2 Pantalla: Administración de Autorizaciones (`/modules/cajeros/rules`)

**Formulario de alta (panel superior o modal):**

| Campo | Tipo | Detalle |
|-------|------|---------|
| Cajero | Combo | Lista de usuarios del sistema (GET /api/security/users) |
| Autorizador | Combo | Lista de usuarios del sistema |
| Moneda | Combo | ARS / USD / EUR / otras monedas configuradas |
| Monto | Numérico | Monto límite que dispara la regla |
| Referencia | Texto (opcional) | Si vacío: aplica a la suma total de la moneda. Si se carga: aplica solo a transacciones con esa referencia |

Tooltip en campo Referencia: *"Si no se ingresa referencia, la restricción se aplicará sobre la suma de todas las transacciones del cajero para esa moneda."*

Botón "Agregar Regla" → POST /api/cajeros/rules

**Grilla de reglas activas:**

| Cajero | Autorizador | Moneda | Monto | Referencia | Fecha Creación | Acciones |
|--------|-------------|--------|-------|-----------|----------------|----------|
| Juan P. | María G. | ARS | $50.000 | — | 01/03/2026 | 🗑 Eliminar |

- Columna Referencia muestra "—" si es NULL (aplica a total)
- Botón Eliminar con confirmación: "¿Confirmar eliminación de esta regla?"
- Filtros: por cajero, por moneda

---

### 6.3 Pantalla: Nueva Transacción (`/modules/cajeros/transactions/new`)

**Formulario:**

| Campo | Tipo | Detalle |
|-------|------|---------|
| Moneda | Combo | ARS / USD / EUR / etc. |
| Monto | Numérico | Monto de la transacción |
| Referencia | Texto (opcional) | Referencia de la operación |
| Descripción | Texto largo (opcional) | Descripción libre |

Botón "Registrar Transacción"

**Comportamiento tras submit:**
- Si `status = PROCESADA`: toast verde "Transacción procesada correctamente"
- Si `status = PENDIENTE_AUTORIZACION`: toast amarillo "Transacción registrada. Queda pendiente de autorización por {autorizador}. Se ha enviado una notificación."
- En ambos casos, redirigir a la grilla de transacciones con la nueva fila resaltada

---

### 6.4 Pantalla: Grilla de Transacciones (`/modules/cajeros/transactions`)

**Filtros:**
- Estado (multiselect: PROCESADA, PENDIENTE_AUTORIZACION, AUTORIZADA, RECHAZADA, ELIMINADA)
- Moneda
- Fecha desde / hasta
- Cajero (solo visible si tiene permiso `read_all`)

**Grilla:**

| Cajero | Autorizador | Moneda | Monto | Referencia | Estado | Fecha Modif. | Fecha Autorización | Acciones |
|--------|-------------|--------|-------|-----------|--------|-------------|-------------------|----------|

- **Orden por defecto:** PENDIENTE_AUTORIZACION primero, luego por `updated_at` DESC
- **Badge de estado con colores:**
  - PENDIENTE_AUTORIZACION → amarillo/naranja
  - PROCESADA → azul
  - AUTORIZADA → verde
  - RECHAZADA → rojo
  - ELIMINADA → gris tachado

**Acciones por fila según rol y estado:**

| Estado | Cajero dueño | Autorizador | Admin |
|--------|-------------|-------------|-------|
| PENDIENTE_AUTORIZACION | Puede eliminar | Puede autorizar/rechazar | Puede eliminar |
| Otros | — | — | — |

- Botón "Autorizar" y "Rechazar" visibles solo para el autorizador asignado
- Rechazar abre modal con campo "Motivo de rechazo" (obligatorio)
- Eliminar abre confirmación

**Panel de detalle (al hacer click en una fila):**
Drawer lateral o modal con todos los campos de la transacción, historial de estado, y motivo de rechazo si aplica.

---

## 7. Estructura del Módulo Python (revisada)

```
modules/cajeros/
├── Dockerfile
├── requirements.txt
├── alembic/
└── app/
    ├── main.py
    ├── config.py
    ├── db/
    ├── models/
    │   ├── authorization_rules.py
    │   ├── transactions.py
    │   └── transaction_rule_triggers.py
    ├── schemas/
    │   ├── rules.py
    │   └── transactions.py
    ├── routers/
    │   ├── rules.py
    │   └── transactions.py
    ├── services/
    │   ├── rule_evaluator.py       # evalúa si una transacción supera algún límite
    │   ├── transaction_service.py
    │   └── notifications_client.py # llama al módulo de notificaciones
    └── dependencies/
        └── auth.py
```

---

## 8. Agregados al proxy — nuevas rutas

```python
"GET /api/cajeros/rules":                               "cajeros:rules:read",
"POST /api/cajeros/rules":                              "cajeros:rules:write",
"DELETE /api/cajeros/rules/{id}":                       "cajeros:rules:write",
"POST /api/cajeros/transactions":                       "cajeros:transactions:write",
"GET /api/cajeros/transactions":                        "cajeros:transactions:read",
"GET /api/cajeros/transactions/{id}":                   "cajeros:transactions:read",
"PUT /api/cajeros/transactions/{id}/authorize":         "cajeros:transactions:authorize",
"PUT /api/cajeros/transactions/{id}/reject":            "cajeros:transactions:authorize",
"DELETE /api/cajeros/transactions/{id}":                "cajeros:transactions:delete",
```
