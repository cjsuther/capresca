# Plan de diseño — Solicitudes de crédito (nueva opción)

> Estado: **propuesta para revisión** (no codeado aún). Decisiones tomadas con el usuario:
> cliente no registrado = **ambos según permiso**; modelo = **tabla nueva `pp_solicitud`**; entregar plan escrito primero.
> Contexto: es el paso 1 del roadmap → 2) originar/otorgar/desembolsar (ya verificado contra dato real,
> solicitud 188512) → 3) persistencia total del plan de cuotas + situaciones de pago → 4) nueva Caja.

---

## 1. Objetivo y alcance

Una pantalla **Créditos → Solicitudes** para cargar, evaluar y aprobar solicitudes de crédito de la
línea nueva (product builder `pp_`), tanto para **clientes registrados** (maestro real de clientes) como
**no registrados** (alta express), y que una solicitud **APROBADA** alimente la originación existente
(wizard Originar → otorgar → desembolsar).

**Fuera de alcance de este paso** (van después, en su orden): persistencia total del plan de cuotas,
situaciones de pago futuras, y la nueva Caja. Este plan deja los ganchos para conectarlos.

---

## 2. Modelo de datos — `pp_solicitud` (tabla nueva)

Namespace `pp_` (uuid string como el resto del product builder). Portable PG + SQLite.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | str(36) PK | uuid |
| `numero` | str(20) | legible: `SOL-2026-00001` (secuencial por año) |
| `estado` | str(20) | BORRADOR · EN_EVALUACION · APROBADA · RECHAZADA · ORIGINADA · ANULADA |
| `solicitante_tipo` | str(15) | REGISTRADO · NO_REGISTRADO |
| `cliente_id` | int FK→clientes | nullable; sólo si REGISTRADO (maestro real) |
| `cliente_datos` | JSON | sólo si NO_REGISTRADO: `{cuil, apellido_nombre, dni, nacimiento}` |
| `producto_id` | str(36) FK→pp_producto | línea solicitada |
| `monto_solicitado` | Numeric(14,2) | |
| `plazo_solicitado` | int | |
| `segmento`, `canal` | str | perfil para elegibilidad (Fase E) |
| `edad`, `antiguedad_meses` | int | perfil |
| `relacion` | str | ESTANDAR/PREFERENCIAL/PREMIUM (relationship pricing) |
| `datos_adicionales` | JSON | destino, cbu, observaciones (prellenan el wizard) |
| `origen` | str(15) | SUCURSAL · PORTAL · CONVENIO (canal de captación) |
| `evaluacion` | JSON | `{elegible, motivos[], score?, tna_ofrecida, cuota_estimada}` |
| `contrato_id` | str(36) FK→pp_contrato | nullable; se setea al ORIGINAR |
| `creado_por`, `creado_en` | | auditoría |
| `enviada_por`, `aprobada_por`, `rechazada_por` | | cuatro-ojos |
| `motivo_rechazo` | str | |

**Relación con lo legacy:** `pp_solicitud` es **nueva** y convive con la tabla legacy real
`solicitudes_credito` (30 aprobadas hoy). La originación seguirá aceptando **ambos** orígenes:
`solicitud_id` (legacy, ya funciona) y el nuevo `solicitud_pp_id`. **Opcional (fase posterior):** un
importador que traiga solicitudes legacy pendientes a `pp_solicitud`. No hay migrador de DBF acá porque es
un concepto nuevo (no se migra una tabla VFP; se referencia la existente).

**Regla de migradores:** al ser tabla nueva sin DBF fuente, no aplica migrador; sí se documenta en
**Controles de Versión** (modelo de datos + APIs + DER) y en `USOS_MENU` (opción nueva de menú).

---

## 3. Workflow de estados (con cuatro-ojos)

```
BORRADOR ──enviar──▶ EN_EVALUACION ──aprobar*──▶ APROBADA ──originar──▶ ORIGINADA
                          │
                          └──rechazar*──▶ RECHAZADA
(cualquiera menos ORIGINADA) ──anular──▶ ANULADA
```
`*` **cuatro-ojos**: quien envía a evaluación no puede aprobar/rechazar (separación de funciones, como en
el workflow de líneas `pp_producto`). Perfiles: carga = ADMG/XCR; aprueba = ADMG (revisamos el perfil real).
- **APROBADA** es requisito para originar. Al originar se setea `estado=ORIGINADA` + `contrato_id`, y la
  solicitud desaparece de la bandeja de pendientes (idempotente, no se origina dos veces → 409).

---

## 4. Cliente registrado vs no registrado (ambos según permiso)

Un permiso nuevo (p. ej. `alta_express_solicitud`) habilita el alta express. En la pantalla de nueva solicitud:

- **Registrado (default):** buscador contra el maestro real de clientes (`/clientes?q=`), setea `cliente_id`.
- **No registrado (si tiene permiso):** captura mínima `{cuil, apellido_nombre, dni, nacimiento}` en
  `cliente_datos`. Validación de CUIL. Al **aprobar**, opción de **promover** ese cliente al maestro real
  (crea el registro y reemplaza `cliente_datos`→`cliente_id`), o dejarlo como no registrado hasta el desembolso.
- Sin permiso: el no registrado se **deriva** a "dar de alta en el maestro primero" (link al ABM de clientes).

Este es el punto elegido "ambos según permiso": el operador ve las dos vías; el permiso decide si el express
está habilitado.

---

## 5. Elegibilidad y pricing en la solicitud (reusar lo existente)

Al cargar/evaluar, se reutiliza lo ya construido y probado:
- **Disponibilidad/segmentación (Fase E):** `_disponibilidad`/`_elegibilidad` valida el perfil (segmento,
  canal, edad, antigüedad) contra la línea y muestra `elegible` + `motivos` (los mismos que probamos).
- **Preview del cronograma:** `POST /productos/preview` calcula cuota estimada / TNA efectiva / CFT para
  mostrar en la solicitud (única fuente de verdad, ya unificada).
- **Relationship pricing + banda:** la `relacion` se guarda y se aplica al originar (con el piso duro ya
  corregido, H-081). Relación inválida → 422 (H-087).
La `evaluacion` (JSON) congela `{elegible, motivos, tna_ofrecida, cuota_estimada}` al enviar a evaluación.

---

## 6. APIs (`/api/solicitudes`)

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/solicitudes?estado=&q=&producto_id=` | bandeja con filtros + paginación/orden |
| POST | `/api/solicitudes` | crear (registrado o no registrado) |
| GET | `/api/solicitudes/{id}` | detalle + elegibilidad + preview |
| PUT | `/api/solicitudes/{id}` | editar (sólo BORRADOR) |
| POST | `/api/solicitudes/{id}/estado` | `{accion: enviar\|aprobar\|rechazar\|anular, motivo?}` (cuatro-ojos) |
| POST | `/api/solicitudes/{id}/promover-cliente` | alta express → maestro real (con permiso) |

**Originación:** se extiende el `originar` existente para aceptar `solicitud_pp_id` (además del `solicitud_id`
legacy). Al originar desde una `pp_solicitud` APROBADA: valida estado, crea el contrato, setea
`ORIGINADA`+`contrato_id`. El wizard Originar gana una fuente "🗂️ Desde solicitud (nueva)".

---

## 7. Pantallas (frontend)

1. **Créditos → Solicitudes** (badge `new`): bandeja con tabla ordenable (número, cliente, línea, monto,
   estado, fecha), filtros por estado, buscador. Chips de estado con color.
2. **Nueva solicitud** (wizard corto): Cliente (registrado/express) → Línea + monto/plazo → Perfil
   (segmento/canal/edad/antigüedad/relación) con **elegibilidad y cuota estimada en vivo** → Enviar a evaluación.
3. **Detalle**: datos + evaluación + acciones (aprobar/rechazar/anular con cuatro-ojos) + botón **Originar**
   (cuando APROBADA) que abre el wizard de originación prellenado.

---

## 8. Tests (siempre) + Controles de Versión

- Backend `test_solicitudes.py`: crear registrado/no-registrado, permiso de express, workflow + cuatro-ojos,
  elegibilidad gating, originar desde APROBADA (setea ORIGINADA + contrato), no re-originar (409), anular.
- Registrar casos en **Controles de Versión** (pantalla "Solicitudes") y sumar la tabla `pp_solicitud` al
  modelo de datos + las rutas + el changelog. Badge `new` en el menú.

---

## 9. Orden de construcción propuesto

1. Modelo `PPSolicitud` + recreación de tablas `pp_` + seed opcional de ejemplo.
2. API `/api/solicitudes` (CRUD + estado + cuatro-ojos) + extensión de `originar` con `solicitud_pp_id`.
3. Tests backend + casos en Controles de Versión.
4. Frontend: bandeja + wizard nueva solicitud + detalle + entrada de menú (badge new).
5. Verificación en navegador end-to-end (incl. originar desde una solicitud nueva).

---

## 10. Ganchos para los pasos siguientes del roadmap

- **Persistencia del plan de cuotas / pagos futuros (paso 3):** el contrato ya persiste `pp_cuota_contrato`;
  la solicitud no agrega deuda ahí. Cuando definamos "situaciones de pago futuras" (mora, prepago real,
  refinanciación), se enganchan al servicing ya existente (`_recompute`, actividades event-sourced).
- **Nueva Caja (paso 4):** la cobranza de los contratos `pp_` hoy pasa por `actividad PAYMENT` (con mora ya
  aplicada, H-086). La nueva Caja sería la UI de cobro dedicada; este plan no la toca, pero deja el servicing
  listo para que la Caja sólo orqueste el cobro.

---

**Pregunta abierta para confirmar antes de codear:** ¿el perfil que aprueba solicitudes es **ADMG** (como
las líneas) o querés un perfil/permiso distinto para créditos (p. ej. un "analista de crédito")?
