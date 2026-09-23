# Módulo Auditoría (:8013)

Registro central de **qué hace cada usuario con la información del sistema**: qué registros agrega,
modifica o elimina, en qué módulo, cuándo y desde dónde. Sólo se consulta: no hay forma de editar ni
borrar un evento desde ninguna pantalla ni API.

## De dónde salen los eventos

| Origen | Quién lo manda | Qué aporta |
|---|---|---|
| `GATEWAY` | el proxy, automáticamente | Toda operación que modifica datos (`POST/PUT/PATCH/DELETE`), el login y **los intentos rechazados** (403). Nadie se puede olvidar de auditar. |
| `MODULO` | cada módulo | El registro concreto: entidad, id y **qué campos cambiaron** (antes/después). |

Los dos lados se cruzan por `request_id`: el gateway genera uno por operación y lo manda en el header
`X-Request-Id`; el detalle del módulo viaja con el mismo. En la pantalla se ven juntos.

### Cómo audita cada módulo, sin tocar endpoint por endpoint
`app/services/auditoria_central.py` (una copia por módulo) instala:
- un **middleware** que guarda quién está haciendo la request (usuario, IP, `request_id`);
- un **listener de SQLAlchemy** que, en cada `flush`, anota las filas insertadas, modificadas y borradas.

Sólo registra lo que ocurre dentro de una request HTTP: los ETL, seeds y migraciones no generan ruido.
Nunca frena ni voltea la operación del usuario (cola en memoria + hilo aparte); si Auditoría no
responde, el evento se pierde y queda en el log del módulo.

Las acciones de negocio que no son un ABM (aprobar, enviar, publicar, retirar…) se registran a mano
con `central.registrar(...)`, para que queden con su nombre y no como "modificación de la tabla X".

## Datos sensibles

Antes de guardar: las claves y tokens **no se guardan** (`•••`) y CBU, CUIL, DNI y similares quedan
parciales (`•••5201`). Ver `app/services/enmascarar.py`.

## Retención

5 años (`RETENCION_DIAS=1825`). La purga corre al arrancar y todas las madrugadas.

## Permisos

`auditoria:eventos:read` (sólo lectura). Conviene dársela a un rol "Auditor" y no a todos.

## Tests

```bash
docker compose run --rm --no-deps -v "$PWD/modules/auditoria:/app" auditoria \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```
