# Sistema Modular Portezuelo

Sistema de gestión modular basado en microservicios para administración de agencias de juego, conciliación financiera y liquidaciones.

## Arquitectura

```
                         ┌──────────┐
        Puerto 80        │  Nginx   │
       ──────────────────►│ (reverse │
                         │  proxy)  │
                         └────┬─────┘
                              │
                 ┌────────────┼────────────┐
                 │                         │
            /api/*                    /internal/*
                 │                         │
           ┌─────▼─────┐           ┌───────▼────────┐
           │   Proxy    │           │ Liquidaciones  │
           │  Gateway   │           │   (directo)    │
           │  :8000     │           │   :8007        │
           └─────┬──────┘           └────────────────┘
                 │
    ┌──────┬─────┼──────┬──────┬───────┬──────┐
    │      │     │      │      │       │      │
 :8001  :8002 :8003  :8004  :8005  :8006   :8007
Security Cajeros Clientes IB  Notif. Concil. Liquid.
```

Cada módulo tiene su propia base de datos PostgreSQL independiente.

## Requisitos previos

- Docker y Docker Compose
- Puerto 80 disponible

## Instalacion y puesta en marcha

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd sistema-modular
```

### 2. Configurar variables de entorno

Crear un archivo `.env` en la raiz del proyecto:

```env
JWT_SECRET=cambiar_por_valor_seguro_aleatorio_en_produccion

SECURITY_DB_USER=security_user
SECURITY_DB_PASS=security_pass
SECURITY_DB_NAME=security_db

CAJEROS_DB_USER=cajeros_user
CAJEROS_DB_PASS=cajeros_pass
CAJEROS_DB_NAME=cajeros_db

CLIENTES_DB_USER=clientes_user
CLIENTES_DB_PASS=clientes_pass
CLIENTES_DB_NAME=clientes_db

INTERBANKING_DB_USER=ib_user
INTERBANKING_DB_PASS=ib_pass
INTERBANKING_DB_NAME=interbanking_db
INTERBANKING_BASE_URL=https://api.interbanking.com.ar
INTERBANKING_AUTH_URL=https://preauth.interbanking.com.ar
INTERBANKING_ENCRYPTION_KEY=cambiar_por_clave_aleatoria_segura_32chars

LIQUIDACIONES_DB_USER=liq_user
LIQUIDACIONES_DB_PASS=liq_pass
LIQUIDACIONES_DB_NAME=liquidaciones_db
LIQUIDACIONES_INTERNAL_API_KEY=cambiar_por_hash_seguro_aleatorio
```

> **Importante:** En produccion, generar valores seguros para `JWT_SECRET`, `INTERBANKING_ENCRYPTION_KEY` y `LIQUIDACIONES_INTERNAL_API_KEY`. Se puede usar `python3 -c "import secrets; print(secrets.token_hex(32))"` para generarlos.

### 3. Levantar los servicios

```bash
docker compose up -d --build
```

Esto levanta todos los servicios, ejecuta las migraciones de base de datos automaticamente y crea el usuario administrador por defecto.

### 4. Acceder al sistema

Abrir el navegador en `http://localhost` e iniciar sesion con las credenciales por defecto:

- **Usuario:** `admin`
- **Password:** `Admin1234!`

> Cambiar la contraseña del administrador luego del primer inicio de sesion.

## Modulos

| Modulo | Puerto | Descripcion |
|--------|--------|-------------|
| **Security** | 8001 | Autenticacion JWT, gestion de usuarios, roles y permisos |
| **Cajeros** | 8002 | Reglas de autorizacion y transacciones de cajeros |
| **Clientes** | 8003 | Gestion de clientes (personas fisicas y juridicas), CBUs |
| **Interbanking** | 8004 | Integracion con Interbanking: cuentas, transferencias, pagos |
| **Notificaciones** | 8005 | Servicio transversal de notificaciones (campanita en el menu) |
| **Conciliacion** | 8006 | Conciliacion de juego: cruza liquidaciones con transacciones IB por CBU |
| **Liquidaciones** | 8007 | Procesamiento de archivos ZIP con DBFs de liquidacion de juegos |
| **Legacy** | 8009 | Integracion apagable con el sistema legacy VFP9 (DBF). Ver [modules/legacy/README.md](modules/legacy/README.md) |

## API interna de Liquidaciones

El modulo de Liquidaciones expone un endpoint interno para recibir archivos ZIP desde sistemas externos, sin necesidad de autenticacion JWT. La autenticacion se realiza mediante una API key fija enviada en el header `X-Api-Key`.

### Endpoint

```
POST /internal/liquidaciones/upload
```

### Headers requeridos

| Header | Descripcion |
|--------|-------------|
| `X-Api-Key` | API key configurada en `LIQUIDACIONES_INTERNAL_API_KEY` |

### Ejemplo con curl

```bash
curl -X POST http://<IP-DEL-SERVIDOR>/internal/liquidaciones/upload \
  -H "X-Api-Key: <LIQUIDACIONES_INTERNAL_API_KEY>" \
  -F "file=@/ruta/al/archivo.zip"
```

### Ejemplo con Python

```python
import requests

response = requests.post(
    "http://<IP-DEL-SERVIDOR>/internal/liquidaciones/upload",
    headers={"X-Api-Key": "<LIQUIDACIONES_INTERNAL_API_KEY>"},
    files={"file": open("/ruta/al/archivo.zip", "rb")},
)
print(response.json())
```

### Respuesta exitosa

```json
{
  "id": 1,
  "status": "ENVIADO_CONCILIACION",
  "error_message": null,
  "total_detail_records": 5432,
  "total_agencies": 105
}
```

Los estados posibles del batch son:

| Estado | Descripcion |
|--------|-------------|
| `PROCESANDO` | El archivo se esta procesando |
| `VALIDADO` | Procesado y validado correctamente |
| `ERROR` | Hubo un error en el procesamiento o la validacion |
| `ENVIADO_CONCILIACION` | Validado y enviado exitosamente al modulo de conciliacion |

### Codigos de respuesta

| Codigo | Descripcion |
|--------|-------------|
| 200 | Archivo procesado (ver campo `status` para el resultado) |
| 400 | El archivo no es un ZIP |
| 401 | API key invalida |
| 422 | Falta el header `X-Api-Key` o el archivo |
| 503 | API key no configurada en el servidor |

## Comandos utiles

```bash
# Levantar todos los servicios
docker compose up -d --build

# Ver estado de los servicios
docker compose ps

# Ver logs de un servicio
docker compose logs -f liquidaciones

# Reiniciar un servicio
docker compose restart liquidaciones

# Rebuild de un servicio especifico
docker compose up -d --build liquidaciones

# Detener todo
docker compose down

# Detener y borrar volumenes (elimina las bases de datos)
docker compose down -v
```

## Estructura del proyecto

```
sistema-modular/
├── docker-compose.yml
├── .env
├── nginx/
│   └── nginx.conf
├── frontend/              # React + Vite
│   └── src/
│       ├── modules/       # UI por modulo
│       ├── api/           # Clientes HTTP
│       └── pages/         # Login, Dashboard
├── proxy/                 # API Gateway (FastAPI)
│   └── app/
│       └── routes/
│           └── mapping.py # Mapeo de rutas y permisos
├── modules/
│   ├── security/          # :8001
│   ├── cajeros/           # :8002
│   ├── clientes/          # :8003
│   ├── interbanking/      # :8004
│   ├── notifications/     # :8005
│   ├── conciliacion/      # :8006
│   ├── liquidaciones/     # :8007
│   └── legacy/            # :8009 (integracion VFP9, apagable)
└── externalfiles/         # Archivos compartidos (montado en liquidaciones/legacy)
```
