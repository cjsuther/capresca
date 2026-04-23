# Módulo de Notificaciones — Especificación Técnica

> Módulo transversal del sistema. No tiene pantalla propia dedicada,
> sino que se integra en el menú superior de la aplicación como una campanita
> y expone una API interna que cualquier otro módulo puede invocar para crear notificaciones.

---

## 1. Concepto

El módulo de Notificaciones es un **servicio compartido** que:
- Recibe llamadas internas desde otros módulos (Cajeros, Interbanking, etc.) para crear notificaciones destinadas a usuarios específicos
- Expone endpoints al frontend para consultar y marcar como leídas las notificaciones del usuario logueado
- Mantiene un historial persistente de todas las notificaciones
- Al hacer click sobre una notificación, redirige al módulo y registro correspondiente, y la marca como leída

---

## 2. Posición en la Arquitectura

```
Módulo Cajeros ──────────────────────┐
Módulo Interbanking ─────────────────┤  llamadas internas HTTP
Módulo Clientes (futuro) ────────────┤  POST /internal/notifications
Módulo Security (futuro) ────────────┘
                                      ↓
                          Módulo Notificaciones :8005
                               └── PostgreSQL db_notifications

                          ↑ (via proxy, con JWT del usuario)
Frontend campanita:
  GET  /api/notifications?limit=10&unread_only=false
  PUT  /api/notifications/{id}/read
  PUT  /api/notifications/read-all
  GET  /api/notifications/unread-count
```

---

## 3. Base de Datos (`db_notifications`)

```sql
-- Tabla principal de notificaciones
notifications (
  id              BIGSERIAL PRIMARY KEY,
  user_id         INTEGER NOT NULL,        -- destinatario
  title           VARCHAR(255) NOT NULL,
  message         TEXT NOT NULL,
  module          VARCHAR(100) NOT NULL,   -- "cajeros", "interbanking", "clientes", etc.
  entity_type     VARCHAR(100),            -- "transaction", "batch", "client", etc.
  entity_id       BIGINT,                  -- ID del registro al que refiere
  redirect_path   VARCHAR(500),            -- ruta frontend: "/modules/cajeros/transactions/42"
  is_read         BOOLEAN DEFAULT FALSE,
  read_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  created_by_module VARCHAR(100)           -- qué módulo generó la notificación
)

-- Índices recomendados
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_entity ON notifications(module, entity_type, entity_id);
```

---

## 4. Endpoints

### Públicos (via proxy, autenticados con JWT del usuario)

```
GET    /api/notifications                → Listar notificaciones del usuario logueado
                                           Query params: limit (default 10), offset, unread_only
GET    /api/notifications/unread-count   → Retorna { count: N } para el badge de la campanita
PUT    /api/notifications/{id}/read      → Marcar una notificación como leída
PUT    /api/notifications/read-all       → Marcar todas las notificaciones del usuario como leídas
```

**Respuesta de GET /notifications:**
```json
{
  "data": [
    {
      "id": 1,
      "title": "Transacción pendiente de autorización",
      "message": "Nueva transacción de Juan Pérez por $75.000 ARS",
      "module": "cajeros",
      "entity_type": "transaction",
      "entity_id": 42,
      "redirect_path": "/modules/cajeros/transactions/42",
      "is_read": false,
      "created_at": "2026-03-07T14:30:00Z"
    }
  ],
  "unread_count": 3,
  "total": 10
}
```

### Internos (solo accesibles desde otros módulos, NO expuestos por el proxy al exterior)

```
POST   /internal/notifications           → Crear una o múltiples notificaciones
```

**Body de POST /internal/notifications:**
```json
{
  "notifications": [
    {
      "user_id": 5,
      "title": "Transacción pendiente de autorización",
      "message": "Nueva transacción de Juan Pérez por $75.000 ARS",
      "module": "cajeros",
      "entity_type": "transaction",
      "entity_id": 42,
      "redirect_path": "/modules/cajeros/transactions/42",
      "created_by_module": "cajeros"
    }
  ]
}
```

Acepta un array para poder crear múltiples notificaciones en una sola llamada (útil cuando una transacción tiene más de un autorizador).

---

## 5. Estructura del Módulo Python

```
modules/notifications/
├── Dockerfile
├── requirements.txt          # fastapi, uvicorn, sqlalchemy, alembic, psycopg2
├── alembic/
└── app/
    ├── main.py
    ├── config.py
    ├── db/
    │   ├── base.py
    │   └── session.py
    ├── models/
    │   └── notification.py
    ├── schemas/
    │   └── notification.py
    ├── routers/
    │   ├── public.py           # endpoints para el frontend (GET, PUT)
    │   └── internal.py         # endpoint POST /internal/notifications
    └── services/
        └── notification_service.py
```

---

## 6. Cliente Reutilizable para otros Módulos

Cada módulo que necesite enviar notificaciones instancia el siguiente cliente:

```python
# shared/notifications_client.py (copiado en cada módulo que lo necesite)

import httpx
from app.config import settings

class NotificationsClient:
    def __init__(self):
        self.base_url = settings.NOTIFICATIONS_SERVICE_URL  # http://notifications:8005

    async def notify(self, user_id: int, title: str, message: str,
                     module: str, entity_type: str, entity_id: int,
                     redirect_path: str) -> None:
        """Envía una notificación a un usuario. Fire-and-forget: no bloquea si falla."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/internal/notifications",
                    json={
                        "notifications": [{
                            "user_id": user_id,
                            "title": title,
                            "message": message,
                            "module": module,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "redirect_path": redirect_path,
                            "created_by_module": module
                        }]
                    },
                    timeout=3.0
                )
        except Exception:
            # Las notificaciones no deben interrumpir el flujo principal
            pass

    async def notify_many(self, notifications: list[dict]) -> None:
        """Envía múltiples notificaciones en una sola llamada."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/internal/notifications",
                    json={"notifications": notifications},
                    timeout=3.0
                )
        except Exception:
            pass
```

**Patrón de uso desde el módulo Cajeros:**

```python
notifications = NotificationsClient()

# Al crear una transacción que supera un límite:
await notifications.notify(
    user_id=authorizer_user_id,
    title="Transacción pendiente de autorización",
    message=f"Nueva transacción de {cajero_username} por {amount} {currency}",
    module="cajeros",
    entity_type="transaction",
    entity_id=transaction.id,
    redirect_path=f"/modules/cajeros/transactions/{transaction.id}"
)

# Si hay múltiples autorizadores:
await notifications.notify_many([
    {
        "user_id": auth_id,
        "title": "...",
        "message": "...",
        "module": "cajeros",
        "entity_type": "transaction",
        "entity_id": transaction.id,
        "redirect_path": f"/modules/cajeros/transactions/{transaction.id}",
        "created_by_module": "cajeros"
    }
    for auth_id in authorizer_ids
])
```

---

## 7. Eventos que Generan Notificaciones (por módulo)

### Módulo Cajeros

| Trigger | Destinatario | Título | Mensaje |
|---------|-------------|--------|---------|
| Transacción supera límite (creación) | Autorizador(es) | "Transacción pendiente de autorización" | "Nueva transacción de {cajero} por {monto} {moneda}" |
| Transacción autorizada | Cajero | "Transacción autorizada" | "Tu transacción #{id} por {monto} {moneda} fue autorizada por {autorizador}" |
| Transacción rechazada | Cajero | "Transacción rechazada" | "Tu transacción #{id} fue rechazada por {autorizador}: {motivo}" |

### Módulo Interbanking (a futuro)

| Trigger | Destinatario | Título |
|---------|-------------|--------|
| Error al procesar lote | Usuario que lo creó | "Error en lote de pagos #{id}" |
| Lote completado | Usuario que lo creó | "Lote de pagos #{id} procesado" |
| Error de token OAuth2 | Admins de Interbanking | "Error de autenticación con Interbanking" |

---

## 8. Frontend — Campanita en el Menú Superior

### 8.1 Componente `NotificationBell`

Ubicación: barra de navegación superior, a la derecha (junto al nombre de usuario y logout).

**Comportamiento:**
- Al cargar la app: `GET /api/notifications/unread-count` → muestra badge rojo con el número
- Polling automático cada **30 segundos** para refrescar el contador
- Al hacer click en la campanita: abre un dropdown con las últimas 10 notificaciones
  (`GET /api/notifications?limit=10`)
- El dropdown permanece abierto hasta que el usuario hace click fuera

### 8.2 Dropdown de Notificaciones

```
┌─────────────────────────────────────────────┐
│  🔔 Notificaciones              [Marcar todas como leídas] │
├─────────────────────────────────────────────┤
│ ● [Cajeros] Transacción pendiente           │  ← no leída (fondo levemente resaltado)
│   Nueva transacción de Juan P. por $75.000  │
│   Hace 5 minutos                            │
├─────────────────────────────────────────────┤
│   [Cajeros] Transacción autorizada          │  ← ya leída
│   Tu transacción #38 fue autorizada         │
│   Hace 2 horas                              │
├─────────────────────────────────────────────┤
│              Ver todas las notificaciones   │
└─────────────────────────────────────────────┘
```

- Notificaciones no leídas: fondo sutilmente diferenciado + punto indicador
- Cada notificación muestra: título, mensaje (truncado a 2 líneas), tiempo relativo, módulo origen
- **Al hacer click en una notificación:**
  1. `PUT /api/notifications/{id}/read` (fire-and-forget)
  2. `navigate(notification.redirect_path)` → redirige al módulo correspondiente
  3. El módulo destino debe leer el parámetro de la URL y abrir el detalle del registro

### 8.3 Apertura automática del registro en el módulo destino

Cuando el frontend navega a `/modules/cajeros/transactions/42`, la pantalla de transacciones debe:
1. Detectar que hay un ID en la URL
2. Abrir automáticamente el panel de detalle / modal de esa transacción
3. Si el usuario es el autorizador y el estado es PENDIENTE_AUTORIZACION → mostrar los botones de Autorizar/Rechazar prominentemente

Esto se implementa en cada módulo leyendo los parámetros de ruta con `useParams()` de React Router.

### 8.4 Hook reutilizable `useNotifications`

```javascript
// hooks/useNotifications.js
export function useNotifications() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);

  // Polling cada 30s para el contador
  useEffect(() => {
    const fetchCount = () => api.get('/notifications/unread-count')
      .then(r => setUnreadCount(r.data.count));
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const openDropdown = async () => {
    const r = await api.get('/notifications?limit=10');
    setNotifications(r.data.data);
    setIsOpen(true);
  };

  const markAsRead = async (id, redirectPath) => {
    api.put(`/notifications/${id}/read`); // fire-and-forget
    setUnreadCount(prev => Math.max(0, prev - 1));
    navigate(redirectPath);
  };

  const markAllAsRead = async () => {
    await api.put('/notifications/read-all');
    setUnreadCount(0);
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  return { unreadCount, notifications, isOpen, openDropdown, markAsRead, markAllAsRead };
}
```

---

## 9. Docker Compose — Agregados

```yaml
  # Módulo Notificaciones
  notifications:
    build: ./modules/notifications
    environment:
      - DATABASE_URL=postgresql://notif_user:notif_pass@db_notifications:5432/notifications_db
      - SECURITY_SERVICE_URL=http://security:8001
    depends_on: [db_notifications]
    networks: [app_network]

  db_notifications:
    image: postgres:15
    volumes: [notifications_data:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=notifications_db
      - POSTGRES_USER=notif_user
      - POSTGRES_PASSWORD=notif_pass
    networks: [app_network]

volumes:
  notifications_data:
```

### Variables de entorno para cada módulo que envíe notificaciones

```env
NOTIFICATIONS_SERVICE_URL=http://notifications:8005
```

Agregar esta variable en el `docker-compose.yml` de: `cajeros`, `interbanking`, y cualquier módulo futuro.

---

## 10. Rutas a agregar en el Proxy

```python
# Públicas (requieren JWT del usuario logueado)
"GET /api/notifications":                   None,   # sin permiso especial, cualquier usuario
"GET /api/notifications/unread-count":      None,
"PUT /api/notifications/{id}/read":         None,
"PUT /api/notifications/read-all":          None,

# /internal/notifications NO se expone por el proxy (solo tráfico interno entre contenedores)
```

La ruta `/internal/notifications` del módulo de Notificaciones **no tiene entrada en el proxy** — es exclusivamente accesible desde la red interna Docker, no desde el exterior ni desde el frontend.

---

## 11. Permisos

El módulo de Notificaciones no requiere permisos especiales definidos en el módulo de Seguridad. Cualquier usuario autenticado puede ver y gestionar sus propias notificaciones. El filtrado por `user_id` se hace automáticamente en el backend usando el `user_id` del JWT.

---

## 12. Resumen de Módulos del Sistema (estado actualizado)

| Módulo | Puerto | Base de Datos | Estado |
|--------|--------|--------------|--------|
| Security | :8001 | db_security | Sin cambios |
| Cajeros | :8002 | db_cajeros | **Actualizado (v2)** |
| Clientes | :8003 | db_clientes | Sin cambios |
| Interbanking | :8004 | db_interbanking | Nuevo |
| Notifications | :8005 | db_notifications | **Nuevo (transversal)** |
