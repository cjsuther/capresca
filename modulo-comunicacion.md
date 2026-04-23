# Modulo de Comunicacion con el Cliente — Especificacion Tecnica

> Modulo que centraliza la comunicacion con clientes (agencias) via WhatsApp Business API.
> Permite chatear con los clientes desde el sistema, enviar mensajes programaticos
> desde otros modulos, y ofrecer un menu interactivo automatico cuando el cliente se contacta.

---

## 1. Concepto de Negocio

Portezuelo necesita un canal de comunicacion directa con sus agencias (clientes persona juridica).
Actualmente la comunicacion es por fuera del sistema. Este modulo:

- **Centraliza la comunicacion**: todas las conversaciones con clientes quedan registradas en el sistema
- **Habilita a otros modulos a notificar clientes**: por ejemplo, Conciliacion puede enviar la boleta por WhatsApp, o Liquidaciones puede avisar que se proceso un archivo
- **Ofrece autoservicio**: cuando una agencia escribe "hola", recibe un menu interactivo con opciones configurables que pueden disparar acciones en otros modulos (consultar saldo, estado de conciliacion, etc.)

---

## 2. Posicion en la Arquitectura

```
                WhatsApp Business API (Meta Cloud API)
                           |
                    Webhook entrante
                           |
                           v
                Modulo Comunicacion :8008
                     |          |
                     |          └── PostgreSQL db_comunicacion
                     |
          ┌──────────┼──────────────────────┐
          |          |                      |
     Mod. Clientes   Mod. Conciliacion    Mod. Liquidaciones
     (consulta       (otros modulos envian mensajes
      telefonos)      via POST /internal/comunicacion/send)
```

### Puerto: 8008
### Base de datos: db_comunicacion

---

## 3. Integracion con WhatsApp Business API

### 3.1 Requisitos previos

- Cuenta de **WhatsApp Business** verificada en Meta Business Suite
- **WhatsApp Business API** (Cloud API, hosteada por Meta — sin necesidad de servidor propio)
- Un **numero de telefono** registrado como remitente de WhatsApp Business
- **Access Token** permanente (System User Token) de Meta
- **Webhook** configurado para recibir mensajes entrantes

### 3.2 Flujo de mensajes

**Mensaje saliente (sistema -> cliente):**
```
1. Un usuario del sistema escribe un mensaje desde el frontend
   — O — un modulo llama POST /internal/comunicacion/send
2. El modulo Comunicacion consulta el numero de WhatsApp del cliente
   (campo phone de clients o contactos con contact_type = "whatsapp")
3. Se envia via POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
4. Se almacena el mensaje en la base de datos con status = SENT
5. Meta envia webhook de status (delivered, read) -> se actualiza el status
```

**Mensaje entrante (cliente o desconocido -> sistema):**
```
1. Meta envia POST al webhook del modulo: /webhook/whatsapp
2. Se identifica el remitente por su numero de telefono
3. Se busca el cliente en modulo Clientes por numero de telefono
4. Si se encuentra cliente:
   → Se crea/actualiza conversacion con client_id y client_name
5. Si NO se encuentra cliente (numero desconocido):
   → Se crea conversacion con client_id = NULL, client_name = NULL
   → El operador podra luego vincularla a un cliente existente o crear uno nuevo
6. Se almacena el mensaje en la base de datos
7. Si el mensaje es "hola" (o similar) y no hay conversacion activa:
   → Se envia el menu interactivo configurable (tanto a clientes como desconocidos)
8. Si el contacto selecciona una opcion del menu:
   → Si la opcion requiere client_id y la conversacion no tiene cliente vinculado:
     → Se responde con "Para usar esta opcion necesitamos verificar su identidad.
        Un operador se comunicara con usted."
   → Si tiene client_id o la opcion no lo requiere:
     → Se ejecuta la accion configurada
     → Se responde con el resultado
9. Se notifica en tiempo real al frontend via polling
```

### 3.3 Configuracion de la API de WhatsApp

Se almacena en la base de datos (configurable desde el frontend):

```
whatsapp_config (
  id                    SERIAL PRIMARY KEY,
  phone_number_id       VARCHAR(50) NOT NULL,    -- ID del numero en Meta
  business_account_id   VARCHAR(50) NOT NULL,    -- ID de la cuenta Business
  access_token          TEXT NOT NULL,            -- Token cifrado en reposo
  webhook_verify_token  VARCHAR(255) NOT NULL,    -- Token de verificacion del webhook
  display_phone_number  VARCHAR(20),             -- Numero visible (ej: +54 9 11 1234-5678)
  is_active             BOOLEAN DEFAULT TRUE,
  updated_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_by_user_id    INTEGER
)
```

---

## 4. Base de Datos (`db_comunicacion`)

### 4.1 Conversaciones

```sql
conversations (
  id              BIGSERIAL PRIMARY KEY,
  client_id       INTEGER,                    -- referencia logica a clients.id en db_clientes
                                              -- NULL = numero desconocido, no vinculado a cliente
  client_name     VARCHAR(255),               -- snapshot del nombre del cliente (NULL si desconocido)
  client_phone    VARCHAR(20) NOT NULL,       -- numero de WhatsApp del contacto
  status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    -- ACTIVE | CLOSED
  last_message_at TIMESTAMPTZ,
  last_message_preview VARCHAR(255),          -- preview del ultimo mensaje (para la lista)
  unread_count    INTEGER DEFAULT 0,          -- mensajes del contacto sin leer por el operador
  assigned_to_user_id  INTEGER,               -- operador asignado (opcional, futuro)
  created_at      TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (client_phone)                       -- una conversacion por numero de telefono
)

CREATE INDEX idx_conversations_last_msg ON conversations(last_message_at DESC);
CREATE INDEX idx_conversations_unread ON conversations(unread_count) WHERE unread_count > 0;
CREATE INDEX idx_conversations_unlinked ON conversations(client_id) WHERE client_id IS NULL;
```

### 4.2 Mensajes

```sql
messages (
  id                  BIGSERIAL PRIMARY KEY,
  conversation_id     BIGINT NOT NULL REFERENCES conversations(id),
  direction           VARCHAR(10) NOT NULL,    -- 'INBOUND' | 'OUTBOUND'
  message_type        VARCHAR(20) NOT NULL,    -- 'TEXT' | 'IMAGE' | 'DOCUMENT' | 'AUDIO' | 'VIDEO' | 'INTERACTIVE' | 'TEMPLATE'
  content             TEXT,                    -- texto del mensaje
  media_url           VARCHAR(1000),           -- URL del archivo (si aplica)
  media_mime_type     VARCHAR(100),
  media_filename      VARCHAR(255),            -- nombre original del archivo
  media_local_path    VARCHAR(500),            -- path local donde se descargo/almaceno

  -- Metadata de WhatsApp
  wa_message_id       VARCHAR(100) UNIQUE,     -- ID del mensaje en WhatsApp
  wa_status           VARCHAR(20),             -- 'SENT' | 'DELIVERED' | 'READ' | 'FAILED'
  wa_error_code       VARCHAR(20),
  wa_error_message    TEXT,

  -- Quien envio (para mensajes salientes)
  sent_by_user_id     INTEGER,                 -- usuario del sistema que envio
  sent_by_username    VARCHAR(100),
  sent_by_module      VARCHAR(100),            -- si fue enviado por otro modulo (ej: "conciliacion")

  created_at          TIMESTAMPTZ DEFAULT NOW(),

  -- Para mensajes interactivos (respuestas al menu)
  interactive_reply_id    VARCHAR(100),        -- ID de la opcion seleccionada
  interactive_reply_title VARCHAR(255)         -- titulo de la opcion seleccionada
)

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_wa_id ON messages(wa_message_id);
```

### 4.3 Menu Interactivo Configurable

```sql
-- Menu que se muestra cuando el cliente dice "hola"
interactive_menu_config (
  id              SERIAL PRIMARY KEY,
  greeting_text   TEXT NOT NULL DEFAULT 'Hola! Bienvenido a Portezuelo. Seleccione una opcion:',
  is_active       BOOLEAN DEFAULT TRUE,
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_by      INTEGER
)

interactive_menu_options (
  id              SERIAL PRIMARY KEY,
  menu_id         INTEGER NOT NULL REFERENCES interactive_menu_config(id),
  option_id       VARCHAR(50) NOT NULL,       -- identificador unico (ej: "consultar_saldo")
  title           VARCHAR(60) NOT NULL,       -- texto visible (max 60 chars por limitacion WA)
  description     VARCHAR(200),               -- descripcion opcional bajo el titulo
  sort_order      INTEGER NOT NULL DEFAULT 0,

  -- Accion a ejecutar
  action_type     VARCHAR(30) NOT NULL,
    -- 'REPLY_TEXT'   : responde con un texto fijo
    -- 'CALL_MODULE'  : llama a un endpoint interno de otro modulo y responde con el resultado
  action_payload  JSONB NOT NULL,
    -- REPLY_TEXT:  { "text": "Texto de respuesta fijo" }
    -- CALL_MODULE: {
    --   "module": "conciliacion",
    --   "method": "GET",
    --   "url_template": "http://conciliacion:8006/internal/conciliacion/client-summary?client_id={client_id}&date={today}",
    --   "response_template": "Estado de conciliacion al {date}:\nAdeudado: ${importe_adeudado}\nDepositado: ${importe_depositado}\nNeto: ${importe_neto}"
    -- }

  requires_client BOOLEAN DEFAULT TRUE,       -- si es TRUE y la conversacion no tiene client_id,
                                              -- se responde pidiendo que un operador lo vincule primero
  is_active       BOOLEAN DEFAULT TRUE,

  UNIQUE (menu_id, option_id)
)

CREATE INDEX idx_menu_options_order ON interactive_menu_options(menu_id, sort_order);
```

### 4.4 Archivos adjuntos (almacenamiento local)

Los archivos enviados y recibidos se almacenan en un volumen Docker:

```
/data/comunicacion/media/
  ├── inbound/      -- archivos recibidos de clientes
  │   └── {conversation_id}/{wa_message_id}_{filename}
  └── outbound/     -- archivos enviados a clientes
      └── {conversation_id}/{timestamp}_{filename}
```

---

## 5. Endpoints

### 5.1 Publicos (via proxy, autenticados con JWT)

```
-- Conversaciones
GET    /api/comunicacion/conversations
       Query: search, status (ACTIVE|CLOSED), linked (true|false|all, default all), page, per_page
       → Lista de conversaciones con preview del ultimo mensaje y contador de no leidos
       → linked=false filtra solo conversaciones sin cliente vinculado

GET    /api/comunicacion/conversations/{id}
       → Detalle de la conversacion con datos del cliente

GET    /api/comunicacion/conversations/{id}/messages
       Query: limit (default 50), before_id (para paginacion hacia atras)
       → Mensajes de la conversacion, ordenados cronologicamente

POST   /api/comunicacion/conversations/{id}/messages
       Body: { "content": "texto", "message_type": "TEXT" }
       → Envia un mensaje de texto al cliente

POST   /api/comunicacion/conversations/{id}/messages/media
       Multipart: file + caption (opcional)
       → Envia un archivo (imagen, documento, etc.) al cliente

PUT    /api/comunicacion/conversations/{id}/read
       → Marca todos los mensajes de la conversacion como leidos (reset unread_count)

-- Vincular conversacion a un cliente (para conversaciones de numeros desconocidos)
PUT    /api/comunicacion/conversations/{id}/link-client
       Body: { "client_id": 42 }
       → Vincula la conversacion a un cliente existente del modulo Clientes
       → Actualiza client_id y client_name en la conversacion
       → Opcionalmente agrega el telefono como contacto del cliente si no lo tiene

-- Iniciar conversacion nueva (buscar cliente y crear/reabrir conversacion)
POST   /api/comunicacion/conversations
       Body: { "client_id": 42, "phone": "+5491112345678" }
       → Crea o reabre una conversacion con el cliente en ese numero

-- Configuracion del menu interactivo
GET    /api/comunicacion/menu
       → Retorna la configuracion actual del menu y sus opciones

PUT    /api/comunicacion/menu
       Body: { "greeting_text": "...", "options": [...] }
       → Actualiza el menu interactivo completo

-- Configuracion de WhatsApp
GET    /api/comunicacion/whatsapp-config
       → Retorna la configuracion (sin el token completo, enmascarado)

PUT    /api/comunicacion/whatsapp-config
       Body: { "phone_number_id", "business_account_id", "access_token", ... }

-- Estadisticas
GET    /api/comunicacion/stats
       → { total_conversations, active_conversations, messages_today, unread_total }
```

### 5.2 Webhook (publico, sin JWT — verificado por token de Meta)

```
GET    /webhook/whatsapp
       → Verificacion del webhook (challenge de Meta)
       Query: hub.mode, hub.verify_token, hub.challenge

POST   /webhook/whatsapp
       → Recepcion de mensajes entrantes y actualizaciones de status
       Body: payload de Meta (mensajes, status updates, etc.)
```

### 5.3 Internos (solo accesibles entre contenedores)

```
POST   /internal/comunicacion/send
       Body: {
         "client_id": 42,
         "phone": "+5491112345678",  -- opcional: si no se envia, usa el phone principal del cliente
         "message": "Su boleta de conciliacion esta lista.",
         "message_type": "TEXT",     -- TEXT | DOCUMENT | IMAGE
         "media_url": null,          -- URL del archivo a enviar (opcional)
         "media_filename": null,
         "sent_by_module": "conciliacion"
       }
       → Envia un mensaje al cliente en nombre de un modulo
       → Crea la conversacion si no existe
       → Retorna { "message_id": 123, "wa_message_id": "wamid.xxx", "status": "SENT" }

POST   /internal/comunicacion/send-file
       Multipart: client_id, phone (opcional), file, caption, sent_by_module
       → Envia un archivo al cliente (para modulos que generan PDFs, reportes, etc.)
```

---

## 6. Logica del Menu Interactivo

### 6.1 Deteccion de saludo

Cuando llega un mensaje entrante, se evalua:

```python
GREETING_PATTERNS = ["hola", "buenas", "buen dia", "buenos dias", "buenas tardes",
                     "buenas noches", "hi", "hello", "menu"]

def is_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in GREETING_PATTERNS or normalized.startswith("hola")
```

Si `is_greeting(message.text)` es `True` y la conversacion no tiene un menu pendiente de respuesta, se envia el menu interactivo.

### 6.2 Envio del menu via WhatsApp Interactive Message

Se usa el tipo `interactive` de la API de WhatsApp con `type: "list"`:

```json
{
  "messaging_product": "whatsapp",
  "to": "+5491112345678",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": { "type": "text", "text": "Portezuelo" },
    "body": { "text": "Hola! Bienvenido a Portezuelo. Seleccione una opcion:" },
    "action": {
      "button": "Ver opciones",
      "sections": [
        {
          "title": "Consultas",
          "rows": [
            { "id": "consultar_saldo", "title": "Consultar saldo", "description": "Ver estado de cuenta actual" },
            { "id": "estado_conciliacion", "title": "Estado conciliacion", "description": "Ver conciliacion del dia" },
            { "id": "hablar_operador", "title": "Hablar con operador", "description": "Contactar un operador" }
          ]
        }
      ]
    }
  }
}
```

### 6.3 Procesamiento de respuesta al menu

Cuando el cliente selecciona una opcion:

```python
async def process_menu_reply(conversation, reply_id: str):
    option = get_menu_option(reply_id)

    # Si la opcion requiere cliente y la conversacion no tiene uno vinculado
    if option.requires_client and conversation.client_id is None:
        await send_whatsapp_message(
            conversation.client_phone,
            "Para usar esta opcion necesitamos verificar su identidad. "
            "Un operador se comunicara con usted en breve."
        )
        return

    if option.action_type == "REPLY_TEXT":
        # Responde con texto fijo
        await send_whatsapp_message(conversation.client_phone, option.action_payload["text"])

    elif option.action_type == "CALL_MODULE":
        # Llama al endpoint interno del modulo y responde con el resultado formateado
        payload = option.action_payload
        url = payload["url_template"].format(
            client_id=conversation.client_id,
            today=date.today().isoformat()
        )
        response = await httpx.AsyncClient().request(payload["method"], url)
        data = response.json()
        text = payload["response_template"].format(**data)
        await send_whatsapp_message(conversation.client_phone, text)
```

---

## 7. Relacion con Modulo Clientes — Telefonos de WhatsApp

### 7.1 De donde se obtienen los numeros

Los clientes ya tienen:
- Campo `phone` en la tabla `clients` (telefono principal)
- Tabla `client_contacts` con `contact_type` que puede ser "phone", "whatsapp", "celular", etc.

**Convencion**: para enviar por WhatsApp, se buscan en este orden:
1. Contactos con `contact_type = "whatsapp"` (mas especifico)
2. Campo `phone` de la tabla `clients` (fallback)
3. Contactos con `contact_type = "celular"` (fallback secundario)

### 7.2 Formato de numeros

Los numeros se almacenan y procesan en formato E.164 (ej: `+5491112345678`).
El modulo normaliza automaticamente numeros que lleguen sin el prefijo internacional.

### 7.3 Endpoint interno necesario en Modulo Clientes

```
GET /internal/clientes/by-phone/{phone}
    → Busca un cliente por numero de telefono (en clients.phone o client_contacts)
    → { client_id, client_name, client_type, phone }
    → null si no se encuentra
```

Este endpoint es necesario para identificar al remitente cuando llega un mensaje entrante.

---

## 8. API Interna para otros Modulos — Cliente Reutilizable

```python
# shared/comunicacion_client.py (copiado en cada modulo que lo necesite)

import httpx
from app.config import settings

class ComunicacionClient:
    def __init__(self):
        self.base_url = settings.COMUNICACION_SERVICE_URL  # http://comunicacion:8008

    async def send_message(self, client_id: int, message: str,
                           phone: str = None, sent_by_module: str = None) -> dict | None:
        """Envia un mensaje de texto a un cliente por WhatsApp."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.base_url}/internal/comunicacion/send",
                    json={
                        "client_id": client_id,
                        "phone": phone,
                        "message": message,
                        "message_type": "TEXT",
                        "sent_by_module": sent_by_module
                    },
                    timeout=10.0
                )
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    async def send_file(self, client_id: int, file_bytes: bytes,
                        filename: str, caption: str = None,
                        phone: str = None, sent_by_module: str = None) -> dict | None:
        """Envia un archivo a un cliente por WhatsApp."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.base_url}/internal/comunicacion/send-file",
                    data={
                        "client_id": str(client_id),
                        "phone": phone or "",
                        "caption": caption or "",
                        "sent_by_module": sent_by_module or ""
                    },
                    files={"file": (filename, file_bytes)},
                    timeout=30.0
                )
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None
```

**Ejemplo de uso desde Conciliacion:**
```python
comunicacion = ComunicacionClient()

# Enviar boleta PDF
await comunicacion.send_file(
    client_id=agencia.client_id,
    file_bytes=pdf_bytes,
    filename=f"boleta_{date}.pdf",
    caption=f"Boleta de conciliacion del {date}",
    sent_by_module="conciliacion"
)

# Enviar mensaje de texto
await comunicacion.send_message(
    client_id=agencia.client_id,
    message=f"Su conciliacion del {date} fue consolidada. Neto: ${neto}",
    sent_by_module="conciliacion"
)
```

---

## 9. Frontend — Pantallas

### 9.1 Lista de Conversaciones (`/modules/comunicacion`)

Layout tipo WhatsApp Web: panel izquierdo con lista de conversaciones, panel derecho con el chat.

```
┌─────────────────────────┬──────────────────────────────────────────────┐
│ Comunicacion             │                                              │
│ [Buscar cliente...]      │     Seleccione una conversacion              │
│ [+ Nueva conversacion]   │                                              │
│                          │                                              │
│ ● Agencia El Sol S.A.   │                                              │
│   Su boleta esta lista   │                                              │
│   Hace 5 min         (2) │                                              │
│                          │                                              │
│   Agencia La Luna SRL   │                                              │
│   Gracias por la info    │                                              │
│   Ayer                   │                                              │
│                          │                                              │
│ ⚠ +54 9 11 5555-0000    │                                              │
│   [Sin cliente] Hola...  │                                              │
│   Hace 20 min        (1) │                                              │
│                          │                                              │
│   Juan Perez             │                                              │
│   Ok, quedo confirmado   │                                              │
│   Lun                    │                                              │
└─────────────────────────┴──────────────────────────────────────────────┘
```

- Badge numerico azul = mensajes no leidos
- Punto verde = conversacion ACTIVE
- Busqueda filtra por nombre de cliente
- Ordenadas por `last_message_at` descendente

### 9.2 Panel de Chat

```
┌──────────────────────────────────────────────────┐
│ Agencia El Sol S.A.          +54 9 11 1234-5678  │
│ CBUs: 2 | Agencia #0042              [Ver cliente]│
│                                                  │
│ -- Si la conversacion NO tiene cliente vinculado: │
│ ⚠ +54 9 11 5555-0000       [Vincular a cliente] │
│ Numero no registrado en el sistema               │
├──────────────────────────────────────────────────┤
│                                                  │
│                          Hola! Necesito la boleta │
│                          14:20                    │
│                                                  │
│ Hola! Aqui tiene la boleta                       │
│ del dia de hoy.                                  │
│ ┌──────────────────────────┐                     │
│ │ 📄 boleta_2026-04-14.pdf │                     │
│ │ 125 KB                   │                     │
│ └──────────────────────────┘                     │
│ 14:22 ✓✓                                        │
│                                                  │
│              📋 [Menu interactivo enviado]        │
│              El cliente selecciono:               │
│              "Consultar saldo"                    │
│              14:25                                │
│                                                  │
│ Estado de conciliacion al 14/04/2026:            │
│ Adeudado: $100.000                               │
│ Depositado: $75.000                              │
│ Neto: $25.000                                    │
│ 14:25 ✓✓  [via conciliacion]                    │
│                                                  │
├──────────────────────────────────────────────────┤
│ [📎] [😊] Escriba un mensaje...        [Enviar] │
└──────────────────────────────────────────────────┘
```

- Mensajes salientes alineados a la izquierda (color distinto)
- Mensajes entrantes alineados a la derecha
- Status de entrega: ✓ enviado, ✓✓ entregado, ✓✓ azul leido
- Archivos adjuntos clickeables para descargar
- Tag `[via modulo]` para mensajes enviados programaticamente
- Mensajes interactivos (menu) se renderizan con estilo especial
- Selector de emojis integrado
- Boton de adjuntar archivo (imagen, documento)

### 9.3 Modal "Nueva Conversacion"

```
┌────────────────────────────────────────┐
│ Nueva conversacion                     │
├────────────────────────────────────────┤
│ Cliente: [ Buscar por nombre...    ▼ ] │
│                                        │
│ Numero de WhatsApp:                    │
│   ○ +54 9 11 1234-5678 (principal)     │
│   ○ +54 9 11 8765-4321 (whatsapp)     │
│                                        │
│ Mensaje inicial (opcional):            │
│ [________________________________]     │
│                                        │
│         [Cancelar]    [Iniciar chat]   │
└────────────────────────────────────────┘
```

- Al seleccionar un cliente, se listan sus numeros de telefono disponibles
- Si ya existe una conversacion con ese cliente+telefono, se reabre

### 9.4 Modal "Vincular a Cliente"

Se abre desde el boton `[Vincular a cliente]` en conversaciones sin cliente asociado.

```
┌────────────────────────────────────────────┐
│ Vincular conversacion a un cliente         │
├────────────────────────────────────────────┤
│ Numero: +54 9 11 5555-0000                 │
│                                            │
│ Buscar cliente:                            │
│ [ Buscar por nombre, CUIT, codigo...   ▼ ] │
│                                            │
│ ☐ Agregar este numero como contacto        │
│   del cliente (tipo: whatsapp)             │
│                                            │
│ — o —                                      │
│                                            │
│ [Crear nuevo cliente con este numero]      │
│ (redirige al modulo Clientes con el        │
│  telefono pre-cargado, al volver se        │
│  vincula automaticamente)                  │
│                                            │
│         [Cancelar]    [Vincular]           │
└────────────────────────────────────────────┘
```

- Al vincular, se actualiza `client_id` y `client_name` de la conversacion
- Si se marca el checkbox, se agrega el telefono como contacto del cliente con `contact_type = "whatsapp"`
- "Crear nuevo cliente" navega a `/modules/clientes/nuevo?phone=+5491155550000&return=/modules/comunicacion`

### 9.5 Pantalla de Configuracion del Menu (`/modules/comunicacion/config`)

```
┌────────────────────────────────────────────────────────┐
│ Configuracion del Menu Interactivo                     │
├────────────────────────────────────────────────────────┤
│ Texto de bienvenida:                                   │
│ [Hola! Bienvenido a Portezuelo. Seleccione una opcion]│
├────────────────────────────────────────────────────────┤
│ Opciones del menu:                              [+ Agregar] │
│                                                        │
│ ↕ 1. Consultar saldo                          [✏] [🗑]│
│      Tipo: Llamar modulo                               │
│      Modulo: conciliacion                              │
│                                                        │
│ ↕ 2. Estado conciliacion                       [✏] [🗑]│
│      Tipo: Llamar modulo                               │
│      Modulo: conciliacion                              │
│                                                        │
│ ↕ 3. Hablar con operador                       [✏] [🗑]│
│      Tipo: Respuesta fija                              │
│      Texto: "Un operador se comunicara con usted..."   │
│                                                        │
├────────────────────────────────────────────────────────┤
│                              [Cancelar] [Guardar]      │
└────────────────────────────────────────────────────────┘
```

- Opciones reordenables con drag & drop
- Modal de edicion por opcion:
  - Titulo (max 60 chars)
  - Descripcion (max 200 chars)
  - Tipo de accion: "Respuesta fija" o "Llamar modulo"
  - Configuracion segun tipo (texto fijo o URL + template de respuesta)

---

## 10. Estructura del Modulo Python

```
modules/comunicacion/
├── Dockerfile
├── requirements.txt          # fastapi, uvicorn, sqlalchemy, alembic, psycopg2,
│                             # httpx, python-multipart, cryptography
├── alembic/
└── app/
    ├── main.py
    ├── config.py
    ├── db/
    │   ├── base.py
    │   └── session.py
    ├── models/
    │   ├── conversation.py
    │   ├── message.py
    │   ├── whatsapp_config.py
    │   └── interactive_menu.py
    ├── schemas/
    │   ├── conversation.py
    │   ├── message.py
    │   ├── menu.py
    │   └── whatsapp.py
    ├── routers/
    │   ├── conversations.py      # CRUD de conversaciones y mensajes
    │   ├── webhook.py            # GET/POST /webhook/whatsapp
    │   ├── menu_config.py        # configuracion del menu interactivo
    │   ├── whatsapp_config.py    # configuracion de la API de WhatsApp
    │   ├── stats.py              # estadisticas
    │   └── internal.py           # POST /internal/comunicacion/send, send-file
    ├── services/
    │   ├── conversation_service.py
    │   ├── message_service.py
    │   ├── whatsapp_service.py   # integracion con Meta Cloud API
    │   ├── menu_service.py       # logica del menu interactivo
    │   ├── media_service.py      # descarga/almacenamiento de archivos
    │   └── clientes_client.py    # cliente HTTP hacia modulo Clientes
    └── dependencies/
        └── auth.py
```

---

## 11. Docker Compose — Agregados

```yaml
  # Modulo Comunicacion
  comunicacion:
    build: ./modules/comunicacion
    environment:
      - DATABASE_URL=postgresql://${COMUNICACION_DB_USER}:${COMUNICACION_DB_PASS}@db_comunicacion:5432/${COMUNICACION_DB_NAME}
      - CLIENTES_SERVICE_URL=http://clientes:8003
      - WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID}
      - WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN}
      - WHATSAPP_WEBHOOK_VERIFY_TOKEN=${WHATSAPP_WEBHOOK_VERIFY_TOKEN}
      - WHATSAPP_BUSINESS_ACCOUNT_ID=${WHATSAPP_BUSINESS_ACCOUNT_ID}
      - MEDIA_STORAGE_PATH=/data/comunicacion/media
    volumes:
      - comunicacion_media:/data/comunicacion/media
    depends_on:
      db_comunicacion:
        condition: service_healthy
    networks:
      - app_network
    restart: unless-stopped

  db_comunicacion:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${COMUNICACION_DB_NAME}
      - POSTGRES_USER=${COMUNICACION_DB_USER}
      - POSTGRES_PASSWORD=${COMUNICACION_DB_PASS}
    volumes:
      - comunicacion_data:/var/lib/postgresql/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${COMUNICACION_DB_USER} -d ${COMUNICACION_DB_NAME}"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

volumes:
  comunicacion_data:
  comunicacion_media:
```

### Variables de entorno para modulos que envien mensajes

```env
COMUNICACION_SERVICE_URL=http://comunicacion:8008
```

Agregar en: `conciliacion`, `liquidaciones`, `cajeros`, y cualquier modulo que necesite enviar mensajes a clientes.

---

## 12. Rutas a agregar en el Proxy

```python
# proxy/app/config.py — agregar:
comunicacion_service_url: str = "http://comunicacion:8008"

# proxy/app/routes/mapping.py — agregar:

# ── Comunicacion ──────────────────────────────────────────────
("GET",    r"^/api/comunicacion/conversations$",                    settings.comunicacion_service_url, "comunicacion:read"),
("POST",   r"^/api/comunicacion/conversations$",                    settings.comunicacion_service_url, "comunicacion:write"),
("GET",    r"^/api/comunicacion/conversations/\d+$",                settings.comunicacion_service_url, "comunicacion:read"),
("PUT",    r"^/api/comunicacion/conversations/\d+/link-client$",   settings.comunicacion_service_url, "comunicacion:write"),
("GET",    r"^/api/comunicacion/conversations/\d+/messages$",       settings.comunicacion_service_url, "comunicacion:read"),
("POST",   r"^/api/comunicacion/conversations/\d+/messages$",       settings.comunicacion_service_url, "comunicacion:write"),
("POST",   r"^/api/comunicacion/conversations/\d+/messages/media$", settings.comunicacion_service_url, "comunicacion:write"),
("PUT",    r"^/api/comunicacion/conversations/\d+/read$",           settings.comunicacion_service_url, "comunicacion:read"),
("GET",    r"^/api/comunicacion/menu$",                             settings.comunicacion_service_url, "comunicacion:config:read"),
("PUT",    r"^/api/comunicacion/menu$",                             settings.comunicacion_service_url, "comunicacion:config:write"),
("GET",    r"^/api/comunicacion/whatsapp-config$",                  settings.comunicacion_service_url, "comunicacion:config:read"),
("PUT",    r"^/api/comunicacion/whatsapp-config$",                  settings.comunicacion_service_url, "comunicacion:config:write"),
("GET",    r"^/api/comunicacion/stats$",                            settings.comunicacion_service_url, "comunicacion:read"),
```

**Webhook de WhatsApp** — El webhook debe ser accesible desde internet sin JWT. Se expone directamente via nginx:

```nginx
# nginx/nginx.conf — agregar:
location /webhook/whatsapp {
    proxy_pass http://comunicacion:8008;
}
```

**Endpoints internos** (`/internal/comunicacion/*`) no se exponen por el proxy ni por nginx.

---

## 13. Permisos a registrar en Modulo Security

```
Modulo: "comunicacion"
Permisos:
  - comunicacion:read          → Ver conversaciones y mensajes
  - comunicacion:write         → Enviar mensajes, crear conversaciones
  - comunicacion:config:read   → Ver configuracion del menu y WhatsApp
  - comunicacion:config:write  → Modificar configuracion del menu y WhatsApp
```

---

## 14. Consideraciones de Seguridad

- **Access Token de WhatsApp**: se almacena cifrado en la base de datos (AES-256). Solo se descifra en memoria al momento de usar la API
- **Webhook de WhatsApp**: se valida con el `X-Hub-Signature-256` header que Meta envia en cada request (HMAC SHA256 del body con el app secret)
- **Archivos**: se valida el tipo MIME y tamano maximo (16MB para documentos, 5MB para imagenes, segun limites de WhatsApp)
- **Rate limiting**: respetar los limites de la API de WhatsApp Business (80 mensajes/segundo para cuentas verificadas)
- **Ventana de 24 horas**: WhatsApp solo permite enviar mensajes libremente dentro de las 24 horas posteriores al ultimo mensaje del cliente. Fuera de esa ventana, solo se pueden enviar templates pre-aprobados por Meta

---

## 15. Limitaciones de la API de WhatsApp Business

| Concepto | Limite |
|----------|--------|
| Tamano de texto | 4096 caracteres |
| Tamano de documento | 100 MB |
| Tamano de imagen | 5 MB |
| Tamano de video | 16 MB |
| Tamano de audio | 16 MB |
| Opciones de lista interactiva | Max 10 opciones por seccion, max 10 secciones |
| Ventana de mensajeria | 24 horas desde el ultimo mensaje del cliente |
| Fuera de ventana | Solo mensajes tipo Template (pre-aprobados por Meta) |

---

## 16. Modificaciones necesarias en Modulo Clientes

Se necesita un nuevo endpoint interno para buscar clientes por telefono:

```python
# modules/clientes/app/routers/internal.py — agregar:

@router.get("/internal/clientes/by-phone/{phone}")
async def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    """Busca un cliente por numero de telefono (en clients.phone o client_contacts)."""
    # Buscar en campo phone de clients
    client = db.query(Client).filter(Client.phone == phone, Client.is_active == True).first()
    if not client:
        # Buscar en client_contacts
        contact = db.query(ClientContact).filter(
            ClientContact.value == phone,
            ClientContact.contact_type.in_(["whatsapp", "celular", "phone"])
        ).first()
        if contact:
            client = db.query(Client).filter(Client.id == contact.client_id, Client.is_active == True).first()

    if not client:
        return None

    name = client.phone  # fallback
    if client.client_type == ClientType.LEGAL and client.legal_profile:
        name = client.legal_profile.legal_name
    elif client.client_type == ClientType.HUMAN and client.human_profile:
        name = f"{client.human_profile.first_name} {client.human_profile.last_name}"

    return {
        "client_id": client.id,
        "client_name": name,
        "client_type": client.client_type.value,
        "phone": phone
    }
```

---

## 17. Resumen de Modulos del Sistema (estado actualizado)

| Modulo | Puerto | Base de Datos | Estado |
|--------|--------|--------------|--------|
| Security | :8001 | db_security | Sin cambios |
| Cajeros | :8002 | db_cajeros | Sin cambios |
| Clientes | :8003 | db_clientes | **Actualizado** (nuevo endpoint interno) |
| Interbanking | :8004 | db_interbanking | Sin cambios |
| Notifications | :8005 | db_notifications | Sin cambios |
| Conciliacion | :8006 | db_conciliacion | Sin cambios |
| Liquidaciones | :8007 | db_liquidaciones | Sin cambios |
| **Comunicacion** | **:8008** | **db_comunicacion** | **Nuevo** |
