# Sistema Modular Portezuelo

Sistema de gestión modular basado en microservicios para administración de agencias de juego, conciliación financiera, liquidaciones y créditos.

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
    ┌──────┬─────┼──────┬──────┬───────┬──────┬──────┬──────┬──────┬──────┬──────┐
    │      │     │      │      │       │      │      │      │      │      │      │
 :8001  :8002 :8003  :8004  :8005  :8006  :8007  :8008  :8009  :8010  :8011  :8012  :8013  :8014
Security Cajeros Clientes IB  Notif. Concil. Liquid. Comunic. Legacy Créditos Config. Tesorería Auditoría Contab.
```

El backoffice de Créditos (CCyPP) es un módulo más del frontend (`/modules/creditos/`). Aparte trae
el portal ciudadano `/portal-creditos/`, servido por nginx en el mismo origen, con SSO Mi Catamarca;
su API `/api/creditos/portal/*` va directo al módulo, sin gateway.

Interacciones entre módulos (todas vía endpoints `/internal/*` con API key):

```
cajeros ───▶ notifications          (avisa al cajero: transacción autorizada/rechazada)
clientes ──▶ legacy                 (agencias / maeclientes desde el mirror)
comunicacion ▶ clientes             (identifica cliente por teléfono)
conciliacion ▶ clientes, interbanking, legacy
liquidaciones ▶ clientes, conciliacion, legacy
liquidaciones ▶ notifications       (avisa al que subió el lote: procesado/error)
interbanking ▶ notifications        (avisa al actor: transferencia registrada)
conciliacion ▶ notifications        (avisa al uploader: registros a verificar)
legacy ─────▶ notifications         (avisa al admin: drenado/sync)
creditos ───▶ clientes              (padrón único: espejo de la identidad del cliente)
creditos ───▶ configuraciones       (impuestos, índices, feriados y reglas del workflow)
creditos ───▶ tesoreria             (lote de desembolsos; el contrato se activa al acreditarse)
conciliacion ▶ tesoreria            (lote de pagos a agencias con saldo a favor)
tesoreria ──▶ interbanking          (envía las transferencias aprobadas y consulta su estado)
tesoreria ──▶ configuraciones       (regla del workflow LOTE_PAGO)
tesoreria ──▶ creditos, conciliacion (avisa el resultado de cada pago)
proxy ──────▶ auditoria             (registra TODA operación que modifica datos, y los rechazos)
módulos ────▶ auditoria             (qué registro se agregó / modificó / borró, y qué cambió)
creditos, tesoreria ▶ contabilidad  (la TRANSACCIÓN que ocurrió; el asiento lo arma contabilidad)
proxy ──────▶ security              (valida JWT y resuelve permisos por usuario)
```

El proxy inyecta en cada request autenticada `X-User-Id`, `X-Username` y `X-User-Permissions`
(`modulo:accion` separados por coma) y descarta cualquier `X-User*` que mande el cliente.

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

CREDITOS_DB_USER=creditos_user
CREDITOS_DB_PASS=creditos_pass
CREDITOS_DB_NAME=creditos_db
CREDITOS_PORTAL_JWT_SECRET=cambiar_distinto_de_JWT_SECRET   # firma los tokens del portal ciudadano
CREDITOS_PUBLIC_URL=http://localhost                       # base del callback OIDC y del portal
CREDITOS_BASES_HOST_PATH=./externalfiles/creditos_bases    # backup DBF del VFP para el ETL
CREDITOS_PORTAL_MOCK_SSO=false                             # true sólo en demo/QA
CREDITOS_PORTAL_VIDEOS_HOST_PATH=./externalfiles/portal_videos   # video1.mp4, video2.mp4, video3.mp4 del paso 4
MICATAMARCA_CLIENT_ID=
MICATAMARCA_CLIENT_SECRET=

# Módulo Configuraciones (impuestos, índices, feriados, workflow de aprobaciones)
CONFIGURACIONES_DB_USER=configuraciones_user
CONFIGURACIONES_DB_PASS=configuraciones_pass
CONFIGURACIONES_DB_NAME=configuraciones_db
CONFIGURACIONES_INTERNAL_API_KEY=cambiar_por_hash_seguro_aleatorio   # la usa Créditos para leer la configuración

# Módulo Tesorería (lotes de pagos: aprobación y envío por Interbanking)
TESORERIA_DB_USER=tesoreria_user
TESORERIA_DB_PASS=tesoreria_pass
TESORERIA_DB_NAME=tesoreria_db
TESORERIA_INTERNAL_API_KEY=cambiar_por_hash_seguro_aleatorio   # Créditos/Conciliación ↔ Tesorería (ida y aviso de vuelta)
TESORERIA_ENVIO_SIMULADO=true                                    # false = mueve dinero de verdad
CREDITOS_DESEMBOLSO_VIA_TESORERIA=true                           # false = desembolso en el acto (sin Tesorería)
CONCILIACION_PAYMENTS_VIA_TESORERIA=true                         # false = pagos a agencias directo al banco

# Módulo Auditoría (registro central de la actividad de los usuarios)
AUDITORIA_DB_USER=auditoria_user
AUDITORIA_DB_PASS=auditoria_pass
AUDITORIA_DB_NAME=auditoria_db
AUDITORIA_INTERNAL_API_KEY=cambiar_por_hash_seguro_aleatorio   # la usan el gateway y los módulos para registrar
AUDITORIA_RETENCION_DIAS=1825                                   # 5 años; la purga corre sola de madrugada

# Módulo Contabilidad (transacciones de los módulos → asientos)
CONTABILIDAD_DB_USER=contabilidad_user
CONTABILIDAD_DB_PASS=contabilidad_pass
CONTABILIDAD_DB_NAME=contabilidad_db
CONTABILIDAD_INTERNAL_API_KEY=cambiar_por_hash_seguro_aleatorio   # la usan los módulos para mandar transacciones

# Doble factor (TOTP) con TokenServer. Ver "Doble factor (2FA)" más abajo.
TOKENSERVER_ENABLED=false                          # false = todo como antes (login y operaciones sin código)
TOKENSERVER_URL=http://tokenserver-web:8080/v1     # en producción, por la red Docker compartida
TOKENSERVER_API_KEY=                               # tsk_... del tenant de Capresca: SÓLO acá, nunca en el repo
TOKENSERVER_OBLIGATORIO_ROLES=                     # vacío = opcional; "*" = todos; o roles: admin,tesoreria
TOKENSERVER_STEPUP_MINUTOS=5                       # cuánto dura la confirmación de una operación sensible
TOKENSERVER_STEPUP_SIN_2FA=bloquear                # operación sensible sin 2FA activo: bloquear | permitir
                                                   # (no rige para Seguridad: ahí sin 2FA siempre se bloquea)
```

> **Importante:** En produccion, generar valores seguros para `JWT_SECRET`, `INTERBANKING_ENCRYPTION_KEY`, `LIQUIDACIONES_INTERNAL_API_KEY` y `CONFIGURACIONES_INTERNAL_API_KEY`. Se puede usar `python3 -c "import secrets; print(secrets.token_hex(32))"` para generarlos.

### 3. Levantar los servicios

```bash
docker compose up -d --build
```

Esto levanta todos los servicios, ejecuta las migraciones de base de datos automaticamente y crea el usuario administrador por defecto.

### 4. Acceder al sistema

Abrir el navegador en `http://localhost` e iniciar sesion con el usuario `admin`. La clave inicial es la
de `ADMIN_INITIAL_PASSWORD` en el `.env`; si no se define, el seed genera una al azar y la muestra una sola
vez en el log de `security` (`docker compose logs security | grep "clave inicial"`).

> Cambiar la contraseña del administrador luego del primer inicio de sesion.

## Modulos

| Modulo | Puerto | Descripcion |
|--------|--------|-------------|
| **Security** | 8001 | Autenticacion JWT, gestion de usuarios, grupos, roles y permisos. Los roles se asignan a usuarios o a grupos (cada integrante hereda los del grupo) |
| **Cajeros** | 8002 | Reglas de autorizacion y transacciones de cajeros |
| **Clientes** | 8003 | Gestion de clientes (personas fisicas y juridicas), CBUs, documentos e importacion del padron del sistema anterior. Ver [modules/clientes/README.md](modules/clientes/README.md) |
| **Interbanking** | 8004 | Integracion con Interbanking: cuentas, transferencias, pagos |
| **Notificaciones** | 8005 | Servicio transversal de notificaciones (campanita en el menu) |
| **Conciliacion** | 8006 | Conciliacion de juego: cruza liquidaciones con transacciones IB por CBU |
| **Liquidaciones** | 8007 | Procesamiento de archivos ZIP con DBFs de liquidacion de juegos |
| **Legacy** | 8009 | Integracion apagable con el sistema legacy VFP9 (DBF). Ver [modules/legacy/README.md](modules/legacy/README.md) |
| **Creditos** | 8010 | CCyPP: circuito de creditos (productos, solicitudes, originacion, servicing, cartera) + portal ciudadano. Ver [modules/creditos/README.md](modules/creditos/README.md) |
| **Contabilidad** | 8014 | Recibe las transacciones de los modulos y genera los asientos segun su definicion (sin definicion, quedan pendientes). Plan de cuentas, ejercicios, libros (diario, mayor, sumas y saldos), estados contables y libro IVA. Ver [modules/contabilidad/README.md](modules/contabilidad/README.md) |
| **Auditoria** | 8013 | Registro central de lo que hace cada usuario con la informacion: altas, cambios y bajas por modulo, con el antes/despues. Solo lectura, retencion 5 anios. Ver [modules/auditoria/README.md](modules/auditoria/README.md) |
| **Tesoreria** | 8012 | Lotes de pagos (desembolsos de Créditos, pagos a agencias de Conciliación, carga manual): revisión, aprobación por workflow y envío por Interbanking. Ver [modules/tesoreria/README.md](modules/tesoreria/README.md) |
| **Configuraciones** | 8011 | Impuestos, indices de referencia, feriados y workflow de aprobaciones, compartidos por los modulos. Ver [modules/configuraciones/README.md](modules/configuraciones/README.md) |

## Doble factor (2FA)

Segundo factor TOTP (Google Authenticator / Microsoft Authenticator) sobre **TokenServer**, el servidor
2FA propio (`https://token.bluunit.com`). En producción TokenServer está en la misma red Docker
(`sistema-modular_app_network`, alias `tokenserver-web:8080`): Capresca lo llama por
`http://tokenserver-web:8080/v1` sin salir a internet.

**Arranca apagado** (`TOKENSERVER_ENABLED=false`): desplegar no cambia nada hasta prenderlo.

Quién hace qué:

- **security** es el único que habla con TokenServer y el único que tiene `TOKENSERVER_API_KEY`
  (el frontend y el gateway nunca la ven). El `user_id` en TokenServer es el **id interno** del usuario
  (no el mail ni el username, que pueden cambiar); la cuenta que se ve en la app es el username.
- **proxy** exige *step-up* en las operaciones sensibles listadas en `proxy/app/routes/stepup.py` y valida
  localmente el token de step-up (header `X-2FA-Token`, atado a la sesión, `TOKENSERVER_STEPUP_MINUTOS`).
- **frontend**: login en pasos, modal de step-up global y *menú del usuario → Doble factor*.

**Seguridad, step-up total.** En el módulo de Seguridad **toda escritura** (cualquier método que no sea
GET, HEAD u OPTIONS sobre `/api/security/...`: usuarios, roles, grupos, permisos, contraseñas, reset del
2FA de otro usuario y lo que se agregue en el futuro) exige step-up. Es **una sola regla general** en
`stepup.py` (`REGLA_SEGURIDAD`), no una lista ruta por ruta. Además tiene su propia marca
`sin_2fa="bloquear"`: a quien no tiene 2FA activo se le niega el cambio (403 `2fa_requerido`, *"Para hacer
cambios en Seguridad tenés que activar el doble factor."*, con el botón para activarlo) **aunque**
`TOKENSERVER_STEPUP_SIN_2FA=permitir`, que sigue rigiendo para el resto de los módulos.

- Excepciones: `/api/auth/*` (login, refresh, logout y todo lo del propio doble factor: enrolar, activar,
  códigos de recuperación, desactivar y pedir el step-up). Ninguna de esas rutas vive bajo `/api/security`.
- El cambio de la **propia contraseña** (`PUT /api/security/users/me/password`) también lo exige: no hay
  flujo de cambio de contraseña obligatorio que pueda dejar a alguien afuera.
- El **reset del 2FA de otro usuario** (`DELETE /api/security/users/{id}/2fa`) exige el token del admin
  que lo hace (un token de step-up de otro usuario o de otra sesión no sirve).
- Ojo al prenderlo: quien administre usuarios tiene que tener el 2FA activo antes, o no va a poder hacer
  cambios en Seguridad (puede activarlo él mismo desde el modal o desde su menú).

Login con 2FA: usuario y clave → `{"requires_2fa": true, "mfa_token": ...}` (token temporal de un solo uso,
5 min, que sólo sirve para `POST /api/auth/2fa/login`) → código de 6 dígitos o de recuperación → sesión.
Si el rol exige 2FA y el usuario no lo tiene, el login devuelve `requires_enrollment` y lo lleva a
enrolarse (QR, primer código, códigos de recuperación) antes de entrar.

**Falla cerrado:** si TokenServer no responde (timeouts de 2 s de conexión / 4 s totales), quien tiene 2FA
no entra (503 con mensaje) y las operaciones sensibles no se confirman. Un admin puede resetear el 2FA de un
usuario desde *Seguridad → Usuarios* (queda en Auditoría).

### Cómo prenderlo

1. En el panel de TokenServer: crear el tenant de Capresca (issuer `Capresca`) y una API key.
2. En el `.env` del servidor: `TOKENSERVER_API_KEY=tsk_...` y `TOKENSERVER_ENABLED=true`
   (opcional: `TOKENSERVER_OBLIGATORIO_ROLES`).
3. `docker compose up -d security proxy` (security aplica la migración `0004` sola al arrancar).
4. Verificar desde el contenedor: `docker compose exec security python -c "import httpx;print(httpx.get('http://tokenserver-web:8080/healthz').text)"`.

Para apagarlo, `TOKENSERVER_ENABLED=false` y reiniciar `security` y `proxy`: el login vuelve a ser sólo con
clave (las marcas de 2FA quedan guardadas para cuando se vuelva a prender).

Pruebas: los tests de `modules/security` (`tests/test_doble_factor.py`) y `proxy` (`tests/test_stepup.py`, `tests/test_stepup_seguridad.py`, que recorre todos los routers de
escritura de security)
usan un TokenServer simulado. El e2e `modules/security/scripts/e2e_doble_factor.py` corre contra un
TokenServer **local** real con un tenant de prueba (ver el encabezado del script; se niega a correr contra
hosts que no sean locales).

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

## HTTPS

En desarrollo el sitio va por HTTP y no hace falta nada. En un servidor con dominio propio:

1. `NGINX_CONF=nginx.ssl.conf` y `CREDITOS_PUBLIC_URL=https://<dominio>` en el `.env`.
2. El dominio tiene que resolver a la IP del servidor y el puerto 80 quedar abierto: por ahí viaja
   el desafío de Let's Encrypt (`nginx/acme.conf`), que es lo único que no se redirige a HTTPS.
3. Emitir el certificado, una sola vez:

```bash
docker run --rm -v sistema-modular_certbot_conf:/etc/letsencrypt \
  -v sistema-modular_certbot_www:/var/www/certbot certbot/certbot certonly \
  --webroot -w /var/www/certbot -d <dominio> --email <mail> --agree-tos --no-eff-email -n
docker compose up -d nginx
```

4. Renovación: `/opt/renovar-certificado.sh` en cron, dos veces por día. Certbot renueva recién
   cuando faltan menos de 30 días de los 90 que dura, y nginx se recarga sólo si cambió.

Los certificados viven en los volúmenes `certbot_conf` y `certbot_www`, **no** en el árbol del
código: el deploy hace `rsync --delete` y se los llevaría puestos. El dominio está escrito en
`nginx/nginx.ssl.conf`; si cambia, se cambia ahí y se vuelve a emitir.

En el servidor de desarrollo esto ya está hecho: **https://dev.ccypp.gob.ar**.

## Acceso remoto (túnel ngrok)

Por defecto el sistema solo escucha en el puerto 80 del host (accesible desde la
misma red LAN en `http://<IP-del-host>`). Para exponerlo remotamente con una URL
pública HTTPS se incluye un override opt-in de ngrok.

```bash
# 1) Cargar el authtoken de ngrok en .env (cuenta gratuita):
#    https://dashboard.ngrok.com/get-started/your-authtoken
#    NGROK_AUTHTOKEN=xxxxxxxx

# 2) Levantar el stack + túnel:
docker compose -f docker-compose.yml -f docker-compose.ngrok.yml up -d

# 3) Ver la URL pública:
curl -s http://localhost:4040/api/tunnels \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
#    o abrir el inspector en  http://localhost:4040

# Bajar el túnel:
docker compose -f docker-compose.yml -f docker-compose.ngrok.yml down
```

Un `docker compose up` sin el archivo `docker-compose.ngrok.yml` **no** levanta el
túnel: la exposición remota es siempre explícita.

### Notas de seguridad antes de exponer a internet

- **JWT_SECRET**: ya se rotó a un valor aleatorio fuerte en `.env` (reemplazó el
  placeholder de ejemplo). Si clonás el proyecto en otro entorno, generá uno nuevo:
  `openssl rand -hex 48`.
- **TLS**: ngrok termina HTTPS en su borde, así que la URL pública es cifrada aunque
  nginx internamente hable HTTP. Para un deploy propio (sin ngrok) hace falta
  configurar certificados en nginx.
- **Credenciales reales**: Interbanking sigue apuntando al sandbox. Cargar las
  credenciales de producción desde la UI de Configuración, no en el repo.
- **Aviso del navegador de ngrok**: el plan gratuito muestra una interstitial la
  primera vez en el navegador; para llamadas de API se puede saltear con el header
  `ngrok-skip-browser-warning`. Un dominio propio (plan pago) la elimina.

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
│   ├── legacy/            # :8009 (integracion VFP9, apagable)
│   ├── creditos/          # :8010 API + portal ciudadano (/portal-creditos/)
│   ├── configuraciones/   # :8011 impuestos, índices, feriados, workflow
│   ├── tesoreria/         # :8012 lotes de pagos, aprobación y envío por Interbanking
│   ├── auditoria/         # :8013 registro central de la actividad de los usuarios
│   └── contabilidad/      # :8014 transacciones → asientos, libros y estados contables
└── externalfiles/         # Archivos compartidos (montado en liquidaciones/legacy)
```
