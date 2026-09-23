# Módulo Clientes

Padrón único de personas del sistema: personas físicas y jurídicas, contactos, notas, CBUs y
documentos. Los demás módulos (Créditos, Conciliación, Tesorería…) lo consultan por su API interna
en vez de tener su propia copia.

- API: `:8003`, prefijo `/api/clientes` (por el gateway) y `/internal/clientes/*` (por API key).
- Permisos: `clientes:clients:read|write`, `clientes:contacts:*`, `clientes:notes:*` y
  `clientes:padron:importar`.
- Tests: `docker compose run --rm clientes python -m pytest -q`.

## Importar el padrón del sistema anterior

Trae `maeclientes.dbf` (el maestro de clientes de CCyPP/VFP) desde la pantalla
**Clientes → Importar padrón**. Se sube el `.zip` o el `.dbf` suelto; el archivo queda en el volumen
`clientes_padron` y se procesa **en segundo plano**, porque son ~78.000 registros y ninguna respuesta
HTTP puede esperar eso. La pantalla consulta el avance cada 3 segundos.

**Unificación.** En el sistema viejo la misma persona aparece una vez por organismo: el `CIDCLIENTE`
es prefijo + CUIL (`ACA…`, `AGC…`, `AGJ…`, `ECA…`). Por eso el padrón se unifica por **CUIL** (y por
DNI cuando no hay CUIL): **una persona = un cliente**, y cada registro del DBF queda como
`client_legacy_ref` para no perder el vínculo con lo viejo. Con el archivo de septiembre de 2026:
78.300 registros → **72.100 clientes**, 78.055 referencias y 12 rechazos.

**Qué se pisa y qué no.** Identidad y contacto (nombre, nacimiento, sexo, domicilio, teléfono, email)
sólo se completan si están vacíos: el operador pudo haber corregido a mano algo que en el padrón
viejo está mal. Los datos de revista (organismo, categoría, sueldo, situación, baja) se actualizan
siempre, porque de eso el maestro viejo es la fuente de verdad. El CBU se agrega si el cliente no
tenía; nunca se pisa uno cargado. **Volver a subir el mismo archivo no duplica nada.**

**Cuando algo no entra.** El proceso va de a lotes dentro de un SAVEPOINT; si un registro falla
(un dato que no entra en su columna, por ejemplo), se rehace ese lote fila por fila y sólo la
culpable queda afuera, con su motivo. Los rechazos se descargan en CSV desde la misma pantalla.

**Si el módulo se reinicia** a mitad de una importación, ésta queda en `INTERRUMPIDA`: lo que
alcanzó a crear queda y se vuelve a subir el archivo para completar el resto.

Tablas: `client_padron` (datos de revista), `client_legacy_ref` (un registro del DBF),
`client_imports` y `client_import_rechazos`.
