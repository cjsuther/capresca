# Prueba punta a punta — Liquidación, Conciliación e Interbanking

Recorrido completo desde el ZIP de liquidación del juego hasta la conciliación contra
los movimientos reales de Interbanking, con el punto de control a verificar en cada paso.
Pensado para ejecutarse de arriba hacia abajo en un ambiente de prueba.

| | |
|---|---|
| **Alcance** | Liquidaciones · Conciliación · Interbanking |
| **Fuera de alcance** | Cajeros, Comunicación, Legacy, Notificaciones |
| **Pasos** | 6 de preparación + 29 de prueba |
| **Duración estimada** | 2 a 3 horas |

> Versión navegable (misma información, con planilla imprimible):
> https://claude.ai/code/artifact/8ad686fe-aefa-4555-ae02-15c5bbc71bfa

---

## Bloque P — Preparación del ambiente

Sin estos seis pasos la prueba falla por datos, no por software. El más frágil es **P3**:
si el número de agencia no coincide carácter por carácter con el del archivo DBF, el lote
entero se rechaza.

### P1 · Levantar el stack completo

Todos los módulos tienen que estar arriba: la liquidación llama a Clientes y a Conciliación,
y Conciliación llama a Interbanking.

```bash
docker compose up -d
docker compose ps
```

**Punto de control**

- [ ] Los 9 servicios de aplicación y sus 8 bases figuran `Up`; las bases, `healthy`.
- [ ] `http://localhost` muestra la pantalla de login (nginx → frontend).
- [ ] En los logs de Conciliación aparece `Scheduler conciliación iniciado`, y en los de
      Liquidaciones `Scheduler liquidaciones iniciado`.

### P2 · Ingresar como administrador y verificar permisos

Usuario `admin`, contraseña `Admin1234!` (los del seed). Guardá también un token para los
controles por API.

```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin1234!"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

**Punto de control**

- [ ] En el menú lateral se ven **Liquidaciones**, **Conciliación** e **Interbanking**
      (Cuentas, Transferencias, Auditoría, Configuración).
- [ ] El rol admin tiene `liquidaciones:liq:read/write/download`,
      `conciliacion:read/write/download` y los cuatro de interbanking.
- [ ] Si algún ítem no aparece, corré el seed de Security: los permisos nuevos no se
      agregan solos a roles ya existentes.

### P3 · Dar de alta las agencias con su CBU

Para cada agencia del archivo de prueba: cliente *jurídico* activo, con `agency_number`
exactamente igual al campo `N_AGEN` del DBF, y al menos un CBU activo de 22 dígitos.
Marcá como cuenta de cobro (`is_payment_account`) el CBU al que se le pagaría a la agencia.

Pantalla: **Clientes → cliente jurídico → CBUs**

Para el archivo de ejemplo hacen falta dos agencias: `000001` y `000002`. Ojo con los ceros:
el sistema compara texto, no números — `000001` y `1` son distintos.

```bash
docker compose exec -T conciliacion python -c "import httpx,json; \
print(json.dumps(httpx.get('http://clientes:8003/internal/clientes/agencies').json(),indent=1,ensure_ascii=False))"
```

**Punto de control**

- [ ] El JSON devuelve las agencias con `agency_number`, `tax_id` y su lista de `cbus`.
- [ ] Cada agencia tiene al menos un CBU; si no, no puede haber cruce automático ni pago saliente.
- [ ] Un CBU no puede repetirse entre clientes: la base lo rechaza con UNIQUE.

### P4 · Configurar la credencial de Interbanking

Cargá la credencial activa con URL base, URL de auth, client_id, client_secret, *customer id*
y, si el ambiente lo pide, el header *service*. Después elegí la **cuenta de consolidación**
(de dónde salen los depósitos que se cruzan) y la **cuenta de pagos salientes**.

Pantalla: **Interbanking → Configuración**

**Punto de control**

- [ ] *Probar conexión* con scope `info-financiera` devuelve success y un `token_preview`.
- [ ] En la ficha aparecen *Cuenta consolidación* y *Cuenta pagos salientes* con número;
      si dicen «—», la conciliación no va a traer movimientos y el motor de pagos va a fallar.
- [ ] `GET /api/interbanking/config/token-status` muestra el token vigente con sus minutos restantes.

### P5 · Fijar los interruptores del ambiente

| Variable | Servicio | Default | Qué cambia |
|---|---|---|---|
| `AUTO_MATCH_ENABLED` | conciliacion | `true` | Corre el cruce automático cada 60 min y una vez al arrancar |
| `AUTO_MATCH_LOOKBACK_DAYS` | conciliacion | `1` | Además de hoy, reprocesa N días atrás (transferencias tardías) |
| `AUTO_PAYMENTS_ENABLED` | conciliacion | `false` | Kill-switch del motor de pagos salientes |
| `PAYMENTS_DRY_RUN` | conciliacion | `true` | Registra la intención de pago sin llamar al banco |
| `INTERBANKING_MOCK_TRANSFERS` | interbanking | `true` | Transferencias simuladas. No está en el compose: se toma el default |
| `INBOX_ENABLED` | liquidaciones | `true` | Escanea la carpeta de entrada al arrancar y todos los días a las 07:00 |
| `LIQUIDACIONES_INBOX_HOST_PATH` | host | `./externalfiles/liquidaciones_inbox` | Carpeta del host montada como inbox |

**Punto de control**

- [ ] Para la prueba completa arrancá con pagos apagados y en simulación; recién en C7 se habilitan.
- [ ] Si `AUTO_MATCH_ENABLED=true`, el scheduler puede cruzar solo mientras probás a mano:
      no confundas un link automático con uno tuyo.

### P6 · Preparar el archivo de prueba y sus valores esperados

Usá `externalfiles/liquidacion_ejemplo.zip`: 7 registros de detalle, 2 de resumen, 2 agencias,
fecha de operación **10/04/2026**, resumen `5001`. Es chico y verificable a mano.

| Agencia | Recaudación | Ing. brutos | Comisión | Débitos | Premios | Total | Adeudado enviado |
|---|---:|---:|---:|---:|---:|---:|---:|
| 000001 | 1.000,00 | 30,00 | 50,00 | — | 200,00 | 980,00 | **780,00** |
| 000002 | 2.000,00 | — | — | 100,00 | 300,00 | 2.100,00 | **1.800,00** |

`Adeudado enviado = total − premios`, coincide con el importe del R.dbf.
Total del lote: **2.580,00**.

**Punto de control**

- [ ] Los archivos más grandes (`0704.zip`: 79 agencias del 07/04/2026, `1404.zip`: 72 del
      14/04/2026) sirven para volumen, pero exigen tener las 79 agencias dadas de alta.
- [ ] nginx limita la subida a **10 MB**. Un ZIP más grande hay que procesarlo por ruta (A2)
      o por inbox (A8).

---

## Bloque A — Liquidación del juego

El módulo abre el ZIP, parsea los dos DBF, clasifica cada código de operación según la lógica
heredada de FoxPro, valida contra el archivo de resumen y —solo si todo cierra— envía los
importes a Conciliación. Cualquier corte en esa cadena deja el lote en un estado distinto.

### A1 · Procesar el ZIP subiéndolo desde la pantalla

Liquidaciones → *Procesar Liquidación* → *Seleccionar archivo ZIP* → `liquidacion_ejemplo.zip`.
(`POST /api/liquidaciones/upload`)

- [ ] El lote aparece con estado **ENVIADO_CONCILIACION**.
- [ ] Fecha Op. 10/04/2026, Resumen 5001, Registros 7, Agencias 2.
- [ ] Llega la notificación: «El lote se validó y envió a conciliación (2 agencias)».

### A2 · Procesar el mismo ZIP por ruta de archivo

Misma pantalla, opción de ruta: `/data/externalfiles/liquidacion_ejemplo.zip`.
(`POST /api/liquidaciones/process`; `externalfiles` está montada read-only en `/data/externalfiles`)

- [ ] Se crea un **segundo lote** con los mismos totales.
- [ ] En Conciliación, el adeudado de cada agencia para el 10/04/2026 quedó **duplicado**
      (1.560,00 y 3.600,00). Es el comportamiento actual — ver hallazgo **H2**.
- [ ] Anotá el resultado y limpiá los duplicados antes de seguir, o usá una fecha limpia.

### A3 · Revisar el detalle procesado

(`GET /api/liquidaciones/batches/{id}/detalle` y `/raw`)

- [ ] Agencia 000001: recaudación 1.000, ing. brutos 30, comisión 50, premios 200, **total 980**.
- [ ] Agencia 000002: recaudación 2.000, débitos 100, premios 300, **total 2.100**.
- [ ] Los premios **no** suman al total: se acumulan aparte. Es correcto.
- [ ] El crudo devuelve los 7 registros del DBF sin transformar.

### A4 · Verificar las tres validaciones

| Tipo | Qué compara | Esperado |
|---|---|---|
| `DETAIL_VS_SUMMARY` | Por agencia: total − premios contra el importe del R.dbf | 780 = 780 · 1.800 = 1.800 |
| `INTERNAL_CONSISTENCY` | Suma de todo el resumen contra la suma de todo lo procesado | 2.580 = 2.580 |
| `AGENCY_COUNT` | Agencias del resumen que no estén en el detalle | 2 y 2, ninguna faltante |

- [ ] Las tres marcan OK con diferencia 0,00.
- [ ] La tolerancia es de **1 centavo**: una diferencia de 0,02 ya reprueba.

### A5 · Descargar los archivos guardados del lote

(`GET /api/liquidaciones/batches/{id}/archivos`, requiere `liq:download`)

- [ ] Con `liquidacion_ejemplo.zip` hay **3 archivos**: ZIP, DBF_DETALLE, DBF_RESUMEN.
- [ ] Con `0704.zip` hay **5**: se suman PDF_MOVIMIENTOS y PDF_RESUMENES, clasificados por nombre.
- [ ] El ZIP descargado abre y su contenido coincide con el original.

### A6 · Camino de error: agencia no registrada

Desactivá o borrá la agencia `000002` en Clientes y volvé a procesar el ZIP.

- [ ] El lote queda en **ERROR**: «Agencia(s) no registrada(s) en el módulo Clientes: 000002».
- [ ] **No** se guardó nada del lote: ni detalle, ni validaciones, ni archivos. El rechazo es total.
- [ ] Conciliación no recibió nada para esa fecha.
- [ ] Volvé a activar la agencia antes de seguir.

### A7 · Camino de error: descuadre y reintento

Editá una copia del R.dbf para que una agencia no cierre (780 → 800), rearmá el ZIP y procesalo.

- [ ] El lote queda en **ERROR** con «1 validación(es) fallida(s)»; la validación muestra
      esperado, actual y diferencia.
- [ ] El detalle procesado **sí** quedó guardado (a diferencia de A6: acá el archivo se leyó bien).
- [ ] Reenviar a conciliación devuelve **400**: solo acepta lotes en estado **VALIDADO**.
      Un lote que falló validación no se puede forzar.
- [ ] Para probar el reintento en positivo: `docker compose stop conciliacion`, procesá un ZIP
      válido — queda en **VALIDADO** con el error de envío — levantá el servicio y usá
      *Reenviar a conciliación*: pasa a **ENVIADO_CONCILIACION**.

### A8 · Ingesta automática desde la carpeta de entrada

```bash
cp externalfiles/liquidacion_ejemplo.zip externalfiles/liquidaciones_inbox/
docker compose restart liquidaciones
docker compose logs --tail=40 liquidaciones
```

- [ ] En el log aparece `Procesado ... -> batch N (ENVIADO_CONCILIACION)`.
- [ ] El archivo se movió a `liquidaciones_inbox/processed/` (o a `error/` si falló).
- [ ] La carpeta de entrada queda vacía: el movimiento garantiza que no se reprocese.
- [ ] El lote figura creado por el usuario del sistema (id 0), no por vos.

---

## Bloque B — Conciliación y sus variantes

Conciliación cruza, por fecha, lo que la agencia debe (viene de la liquidación) contra lo que
efectivamente depositó (viene del banco). Hay **dos fuentes de depósito**, **dos formas de
vincular** y **cuatro formas de cerrar** un registro.

> **La fecha manda.** Los importes de la liquidación se aplican solo si la fecha que cargás en
> pantalla coincide con la fecha de operación del DBF. Para el archivo de ejemplo tenés que
> cargar **10/04/2026**, no la fecha de hoy.

### B1 · Confirmar la recepción de la liquidación

```bash
docker compose exec -T db_conciliacion psql -U concil_user -d conciliacion_db \
  -c "select agency_number, operation_date, importe_adeudado, importe_premios,
             liquidacion_batch_id, reconciliation_record_id
      from liquidacion_records order by id;"
```

- [ ] Una fila por agencia con `operation_date = 2026-04-10`, adeudado 780,00 y 1.800,00.
- [ ] `reconciliation_record_id` todavía en `null`: se completa al cargar la fecha en pantalla.

### B2 · Cargar la fecha y ver los registros armados

Conciliación → 10/04/2026 → *Cargar*. Este paso hace todo: refresca el cache de CBUs, trae
transferencias y movimientos del banco, cruza, aplica la liquidación, recalcula y auto-consolida.
(`GET /api/conciliacion?date=2026-04-10`)

- [ ] Hay un registro por cada agencia dada de alta en Clientes, aunque no tenga movimiento.
- [ ] Las dos agencias del archivo muestran la insignia **LIQ** y el cartel «Importes cargados
      automáticamente desde el módulo de Liquidaciones».
- [ ] Adeudado 780,00 y 1.800,00; premios 200,00 y 300,00; depositado 0,00.
- [ ] La barra de totales suma 2.580,00 de adeudado.
- [ ] El Neto muestra 580,00 y 1.500,00 — **no** 780 y 1.800. Ver hallazgo **H1**.

### B3 · Variante 1 — Cruce automático por CBU

Fuente: las *transferencias* registradas en Interbanking para esa fecha. Cada una trae el CBU
de destino y se cruza contra el cache de CBUs de agencias.

Generá una: Interbanking → Transferencias → hacia el CBU de la agencia 000001 por **580,00**.
Volvé a Conciliación y recargá la fecha.

- [ ] La transacción aparece en la grilla derecha con la agencia resuelta y etiqueta **AUTO**.
- [ ] El depositado subió a 580,00 y el neto quedó en **0,00**.
- [ ] La transacción figura en el panel bajo *Transacciones vinculadas*.
- [ ] Una transacción con CBU no registrado queda **Sin asignar** — así tiene que ser.

### B4 · Variante 2 — Consolidación bancaria por movimientos de la cuenta

Fuente: los *movimientos reales* de la cuenta de consolidación elegida en P4. Es la fuente que
importa en producción. Como el movimiento bancario no trae el CBU de la contraparte, el sistema
lo identifica por **CUIT del depositante** y lo resuelve al primer CBU de esa agencia.
(`conciliacion → GET /internal/interbanking/movements → API Interbanking`)

- [ ] Cargá una fecha con movimientos conocidos (dentro de los últimos 6 meses, ver **H6**)
      y verificá que aparecen con tipo `movement`.
- [ ] Solo entran los **créditos**. Los débitos se descartan y no deben figurar.
- [ ] Un depósito con CUIT de agencia registrada queda asignado; uno de CUIT desconocido queda
      **Sin asignar**.
- [ ] Si la cuenta de consolidación no está configurada, la grilla solo muestra transferencias:
      comprobalo dejándola vacía un momento.
- [ ] El cruce es **por CUIT, no por importe**: dos depósitos de la misma agencia el mismo día
      se suman los dos.

### B5 · Variante 3 — Auto-consolidación con saldo cero

- [ ] La agencia de B3 pasó a **CONSOLIDADO** sin que nadie la tocara.
- [ ] El historial tiene una entrada con usuario `auto` y la nota «Auto-consolidado: saldo 0».
- [ ] Un registro vacío (adeudado 0 y depositado 0) **no** se auto-consolida: sigue en A_VERIFICAR.
- [ ] Un registro ya consolidado a mano no se pisa.

### B6 · Variante 4 — Asignación manual de una transacción

Tomá una transacción *Sin asignar*, abrila y elegí una agencia en *Asignar Agencia*.
(`PUT /api/conciliacion/interbanking/{tipo}/{id}/agency`)

- [ ] Sale «Agencia asignada correctamente» y la transacción muestra etiqueta **MANUAL**.
- [ ] El depositado de esa agencia subió por el importe de la transacción.
- [ ] Si el CBU *sí* pertenece a la agencia elegida, el vínculo se marca **AUTO**. Es correcto.

### B7 · Variante 5 — Reasignar a otra agencia

- [ ] El depositado de la primera agencia bajó y el de la segunda subió, en el mismo importe.
- [ ] El vínculo anterior no se borra: queda con fecha de desvinculación.
- [ ] Si la primera había quedado en CONSOLIDADO por saldo 0, revisá en qué estado quedó:
      la auto-consolidación no se revierte sola.

```bash
docker compose exec -T db_conciliacion psql -U concil_user -d conciliacion_db \
  -c "select id, reconciliation_record_id, ib_transaction_id, ib_amount,
             match_type, linked_at, unlinked_at
      from reconciliation_ib_links order by id;"
```

### B8 · Variante 6 — Desvincular una transacción

(`DELETE /api/conciliacion/links/{id}`)

- [ ] El depositado se recalcula al instante y el neto vuelve a moverse.
- [ ] La transacción reaparece como **Sin asignar**.
- [ ] Volver a desvincular el mismo vínculo devuelve **400** «El link ya está desvinculado».
- [ ] Ojo: si el CBU está registrado para la agencia, el próximo *Cargar* la vuelve a vincular
      automáticamente.

### B9 · Variante 7 — Editar importes a mano

- [ ] Los importes cambian y el neto se recalcula.
- [ ] En el historial queda el valor anterior y el nuevo, con tu usuario y fecha/hora.
- [ ] El próximo *Cargar* **vuelve a pisar** adeudado y premios con los valores de la liquidación.
      La edición manual no sobrevive si hay liquidación cargada — importante para el operador.

### B10 · Variante 8 — Ajuste manual con justificación

El ajuste suma al depositado, así que corrige el saldo sin tocar la liquidación.

- [ ] Guardar sin justificación devuelve **400** «El ajuste requiere una justificación».
- [ ] Un ajuste positivo **reduce** el neto (acredita a la agencia); uno negativo lo aumenta.
- [ ] Si deja el saldo en 0, el registro se auto-consolida en el acto.
- [ ] El ajuste queda listado con importe, motivo, usuario y fecha, y **sobrevive** al próximo
      *Cargar* — a diferencia de B9. Esta es la forma correcta de corregir un saldo.

### B11 · Variante 9 — Consolidación manual

Cerrar un registro que *no* llega a saldo cero, dejando constancia. Hoy no hay control en la
pantalla: se prueba por API.

```bash
curl -X PUT http://localhost/api/conciliacion/records/{id} \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"CONSOLIDADO_MANUAL","notes":"Diferencia aceptada por tesorería"}'
```

- [ ] Queda en **CONSOLIDADO_MANUAL** con insignia azul y suma en ese contador del resumen.
- [ ] El historial guarda estado anterior, nuevo y la nota.
- [ ] El próximo *Cargar* **no** lo vuelve a A_VERIFICAR.
- [ ] Registrá que la pantalla no ofrece esta acción — hallazgo **H3**.

### B12 · Boleta de conciliación en PDF

(`GET /api/conciliacion/records/{id}/boleta`, requiere `conciliacion:download`)

- [ ] El PDF trae fecha, agencia, CUIT, estado y los cuatro importes.
- [ ] Los importes coinciden con los de la pantalla.
- [ ] Con el registro en A_VERIFICAR el botón no se muestra: la boleta es solo de registros cerrados.

### B13 · Agencia que solo existe en la liquidación

Caso borde: la agencia llega en el archivo pero no está en el cache de CBUs.

- [ ] Aparece un registro «Agencia {número}» con sus importes de liquidación.
- [ ] En la base ese registro tiene `client_id` **negativo** (−1, −2, …).
- [ ] Ese registro **no** puede recibir pagos salientes: no tiene CBU de cobro. Confirmalo en C7.

### B14 · Cruce automático por scheduler

```bash
docker compose restart conciliacion
docker compose logs -f conciliacion | grep -i "cruce\|pagos"
```

- [ ] Al arrancar corre una vez: `Cruce automático OK para {fecha}` por cada día del rango.
- [ ] Los registros y vínculos del día quedan creados sin intervención.
- [ ] Si una fecha falla, el log la marca y **sigue** con las demás.

---

## Bloque C — Interacción con Interbanking

Dos scopes con dos flujos de autenticación: consultas con `info-financiera` (client_credentials)
y transferencias con `transferencias-confeccion` (usuario y contraseña). Todo lo que sale hacia
el banco queda registrado en auditoría, incluso lo que falla.

### C1 · Token por scope

- [ ] `info-financiera` devuelve success con el client_secret guardado.
- [ ] `transferencias-confeccion` exige usuario y contraseña: sin ellos devuelve
      «Faltan usuario/contraseña», no un error de red.
- [ ] El estado de tokens muestra una fila por scope con los minutos restantes.
- [ ] El token se renueva cuando faltan menos de 5 minutos; los anteriores del mismo scope
      quedan desactivados.

### C2 · Cuentas y saldos

(`GET /api/interbanking/cuentas` y `/saldos`)

- [ ] Se listan las cuentas del customer id configurado, con banco, CBU, CUIT, tipo y moneda.
- [ ] Los saldos responden para una o varias cuentas.
- [ ] Si borrás el customer id, la respuesta es **400** «customer_id no configurado», no un 500.

### C3 · Movimientos de una cuenta

(`GET /api/interbanking/cuentas/{cuenta}/movimientos?date-since=&date-until=`)

- [ ] La respuesta trae `general_data` con `total_rows` y el detalle.
- [ ] Cada movimiento tiene fecha, importe, tipo débito/crédito, CUIT del depositante y
      descripción. **No trae el CBU de la contraparte** — por eso B4 cruza por CUIT.
- [ ] Los débitos vienen en **negativo**.
- [ ] Un rango de más de 6 meses atrás devuelve `total_rows: 0` **sin error**. Ver **H6**.

### C4 · Cuentas configuradas que consume Conciliación

```bash
docker compose exec -T conciliacion python -c "import httpx,json; \
b='http://interbanking:8004/internal/interbanking'; \
print('consolidacion:',httpx.get(b+'/consolidation-account').json()); \
print('pagos:',httpx.get(b+'/payment-account').json())"
```

- [ ] Ambos devuelven número de cuenta, tipo, banco y moneda.
- [ ] Si alguno devuelve `null`, volvé a P4: sin cuenta de consolidación no hay depósitos, y sin
      cuenta de pagos el motor de pagos devuelve 400.

### C5 · Validar CBU y emitir una transferencia (modo simulado)

Con `INTERBANKING_MOCK_TRANSFERS` en su default, la transferencia no sale al banco: se registra
local y sirve para alimentar el cruce de B3.

- [ ] La validación de CBU responde con la marca `_mock: true`.
- [ ] La transferencia queda guardada con su estado y aparece en el listado local.
- [ ] Esa transferencia figura en Conciliación para su fecha, con su CBU de destino.

### C6 · Transferencia real ⚠️ mueve fondos

Solo con autorización expresa, contra un ambiente que no sea producción o por un importe testigo.
Poné `INTERBANKING_MOCK_TRANSFERS=false` y reiniciá el servicio.

- [ ] La transferencia devuelve un id de operación de Interbanking real.
- [ ] La consulta de estado refleja el estado que informa el banco.
- [ ] En Auditoría queda la llamada con endpoint, payload, código de respuesta y duración.
- [ ] Volvé a dejar el flag en `true` al terminar.

### C7 · Pagos salientes a agencias con saldo a favor

Cuando una agencia depositó de más (neto negativo), el motor le transfiere la diferencia.

**Etapa 1 — simulación.** `AUTO_PAYMENTS_ENABLED=true` y `PAYMENTS_DRY_RUN=true`. Reiniciá Conciliación.

- [ ] Se registra un pago en estado **DRY_RUN** con importe y CBU de cobro, y **no** se llamó al banco.
- [ ] El registro pasó a estado **A_PAGAR**.
- [ ] Una agencia sin CBU de cobro queda en **SIN_CBU** con el motivo cargado (usá la de B13).
- [ ] Volver a correr el ciclo **no** duplica el pago: hay un pago por registro.

**Etapa 2 — pago real.** ⚠️ mueve fondos. `PAYMENTS_DRY_RUN=false`, solo con autorización.

- [ ] El pago queda en **ENVIADO** con el id de transferencia, y el registro en **PAGADO**.
- [ ] Un pago ya ENVIADO **nunca** se repite. Verificalo corriendo el ciclo dos veces.
- [ ] Si el banco rechaza, el pago queda en **ERROR** con el mensaje y el registro **no** pasa a PAGADO.
- [ ] En el resumen, A_PAGAR y PAGADO no se cuentan en ningún contador — hallazgo **H4**.

### C8 · Auditoría de todo lo que salió al banco

- [ ] Están registradas las operaciones de toda la prueba: `OBTENER_TOKEN[scope]`,
      `LISTAR_CUENTAS`, `LISTAR_MOVIMIENTOS`, `LISTAR_MOVIMIENTOS[conciliacion]` y las transferencias.
- [ ] Las llamadas que **fallaron** también están, con código y mensaje. Provocá una a propósito
      con un customer id inválido.
- [ ] Cada registro tiene duración en ms, usuario e IP.
- [ ] La exportación a CSV abre bien y trae las mismas filas que la pantalla.
- [ ] El log de token **no** guarda el access_token, solo el tipo. Es un requisito de seguridad.

---

## Hallazgos a definir antes de dar la prueba por buena

Salieron de leer el código mientras se armaba este protocolo, no de ejecutarlo. Los pasos de
arriba están escritos para que cada uno se confirme o se descarte con números a la vista.

### H1 · Los premios se descuentan dos veces — **Alto**

Liquidaciones envía `importe_adeudado = total − premios` (agencia 000001: 980 − 200 = **780**,
justo el importe del R.dbf). Conciliación después calcula `neto = adeudado − premios − depositado`,
o sea 780 − 200 = **580**.

Consecuencia: la agencia que deposita los 780 que dice su resumen queda con neto −200 y el sistema
la marca con saldo a favor; la que deposita 580 queda en cero y se auto-consolida. Con pagos
automáticos habilitados, esto genera un pago de 200 que no corresponde.

Verificar en **B2** y **B5**. Definir con negocio si «adeudado» debe llegar bruto o neto de premios.

### H2 · Reprocesar el mismo archivo duplica los importes — **Alto**

`POST /internal/conciliacion/liquidaciones` inserta una fila por agencia sin verificar si ese lote
ya se recibió, y `_apply_liquidacion_data` suma *todas* las filas de esa fecha. Procesar dos veces
el mismo ZIP deja el adeudado al doble.

La ingesta por carpeta está protegida porque mueve el archivo a `processed/`; la carga manual y la
carga por ruta no tienen esa protección.

Verificar en **A2**. Falta idempotencia por `liquidacion_batch_id`.

### H3 · La consolidación manual no tiene control en la pantalla — **Medio**

`handleUpdateRecord` solo manda `importe_adeudado` e `importe_premios`; nunca manda el estado.
No hay forma desde la interfaz de pasar un registro a CONSOLIDADO_MANUAL, aunque el back lo soporta
y el resumen tiene un contador para ese estado.

Verificar en **B11**. Falta un selector de estado en el panel del registro.

### H4 · Los estados de pago quedan fuera del resumen — **Medio**

El motor de pagos usa `A_PAGAR` y `PAGADO`, pero `get_summary` solo cuenta A_VERIFICAR, CONSOLIDADO
y CONSOLIDADO_MANUAL, y `StatusBadge` no tiene color para ellos. Un registro pagado desaparece de los
tres contadores sin que se note.

Verificar en **C7**.

### H5 · El CUIT nunca se muestra en el panel — **Bajo**

La API devuelve el campo como `agency_tax_id` y `ConciliacionPage.jsx` lee `selectedRecord.tax_id`:
el detalle siempre muestra «—» en CUIT/RUT, aunque el dato esté cargado. En la boleta PDF sí sale bien.

Verificar en **B2** y **B12**.

### H6 · Interbanking solo guarda ~6 meses de movimientos — **Informativo**

Consultar un rango anterior a ~190 días devuelve `200 OK` con lista vacía, no un error. Es
indistinguible de una cuenta sin movimientos, así que una conciliación retroactiva de fechas viejas
va a dar «sin depósitos» y consolidar mal.

Verificar en **C3**. Para historia vieja, ir al home banking o al sistema legacy.

---

## Planilla de resultados

| Paso | Qué prueba | Resultado | Evidencia | Observaciones |
|---|---|---|---|---|
| P1 | Stack arriba | | | |
| P2 | Login y permisos | | | |
| P3 | Agencias con CBU | | | |
| P4 | Credencial y cuentas IB | | | |
| P5 | Flags del ambiente | | | |
| P6 | Archivo y valores esperados | | | |
| A1 | Carga por pantalla | | | |
| A2 | Carga por ruta · idempotencia | | | |
| A3 | Detalle procesado | | | |
| A4 | Tres validaciones | | | |
| A5 | Archivos guardados | | | |
| A6 | Error: agencia no registrada | | | |
| A7 | Error: descuadre y reintento | | | |
| A8 | Ingesta por carpeta | | | |
| B1 | Recepción en conciliación | | | |
| B2 | Armado de registros del día | | | |
| B3 | Cruce automático por CBU | | | |
| B4 | Consolidación bancaria por CUIT | | | |
| B5 | Auto-consolidación saldo 0 | | | |
| B6 | Asignación manual | | | |
| B7 | Reasignación | | | |
| B8 | Desvinculación | | | |
| B9 | Edición manual de importes | | | |
| B10 | Ajuste con justificación | | | |
| B11 | Consolidación manual | | | |
| B12 | Boleta PDF | | | |
| B13 | Agencia solo en liquidación | | | |
| B14 | Cruce por scheduler | | | |
| C1 | Token por scope | | | |
| C2 | Cuentas y saldos | | | |
| C3 | Movimientos | | | |
| C4 | Cuentas internas configuradas | | | |
| C5 | Transferencia simulada | | | |
| C6 | Transferencia real | | | |
| C7 | Pagos salientes | | | |
| C8 | Auditoría | | | |
