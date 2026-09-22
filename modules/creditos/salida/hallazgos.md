# Hallazgos de la migración — CCyPP (log vivo)
### Descubrimientos técnicos y de negocio, para revisión

> Se agrega un hallazgo por cada descubrimiento relevante, con fecha, evidencia
> e impacto. Los más recientes arriba. Ref. cruzada con `estado-migracion.md`,
> `analisis-brechas.md` y `catalogo_real.md`.

---

## H-217 · Tesorería: elegir la cuenta de origen del pago, y botón "Inicio" en toda la plataforma
**Fecha:** 2026-09-22 · **Módulo:** Tesorería / Interbanking / UI común · **Alcance:** pedido del usuario
- Al enviar un lote, el tesorero **elige desde qué cuenta sale la transferencia**. Interbanking expone
  `/internal/interbanking/payment-accounts` (las cuentas del banco + la "cuenta de pagos" configurada,
  marcada como predeterminada) y `/internal/interbanking/payments` acepta `cuenta_origen`. La cuenta
  elegida se valida contra esa lista (no se envía a una cuenta arbitraria), queda guardada en el lote y
  se ve en el historial y en la pantalla. **Sin cuenta de origen no se envía, ni siquiera en simulación**
  (al principio se permitía para poder probar sin credenciales: era un permiso de más, lo marcó el
  usuario). Si el banco no responde, igual se puede pagar desde la cuenta configurada.
- **Botón "Inicio"** en la barra superior (salvo estando en el tablero) y arriba del menú lateral: hasta
  ahora sólo se volvía haciendo clic en el logo y los usuarios no lo descubrían.

## H-216 · Desembolsos por Tesorería: el contrato se activa cuando se acredita la transferencia
**Fecha:** 2026-09-22 · **Módulo:** Créditos / Tesorería (nuevo) · **Alcance:** pedido del usuario
- Nuevo módulo **Tesorería** (:8012): recibe lotes de pagos de Créditos, Conciliación o carga manual; el
  tesorero excluye pagos, aprueba según el workflow `tesoreria/LOTE_PAGO` (Configuraciones, cuatro ojos)
  y los envía por Interbanking. Arranca en **simulación** (no mueve dinero).
- **Créditos** (`DESEMBOLSO_VIA_TESORERIA=true`): liquidar el lote, desembolsar de a uno, ejecutar un
  pendiente aprobado u originar con desembolso ya no activan el contrato: mandan el neto al CBU de
  acreditación (contrato → solicitud → cliente) como lote de Tesorería y el contrato queda A_LIQUIDAR
  "en Tesorería". Tesorería avisa por `/internal/creditos/tesoreria/resultado` (X-Api-Key):
  CONFIRMADO → asiento + DISBURSEMENT y **ACTIVO** (aunque venga de un lote anterior: si la plata salió,
  el contrato se activa); FALLIDO/EXCLUIDO/RECHAZADO → **OBSERVADO** con el motivo, se puede volver a liquidar.
- **Sin doble pago:** la referencia del lote sale de los contratos y su número de intento (un reintento
  tras un corte cae en el mismo lote); Tesorería no admite dos pagos vivos por contrato ni reintentar un
  fallido que el origen ya reenvió; un contrato "en Tesorería" no se vuelve a mandar ni se desembolsa directo.
- **Conciliación** (`PAYMENTS_VIA_TESORERIA=true`): los pagos a agencias con saldo a favor van en un lote
  por corrida (estado EN_TESORERIA); acreditado → PAGADO; excluido/fallido → OBSERVADO, que no se reenvía
  solo cada hora.
- La pantalla "Liquidación por lote" y la ficha del contrato muestran "En Tesorería · LOT-…" u "Observado".
- QA de punta a punta en local: contrato → lote → aprobación del tesorero (otro usuario, vía grupo) →
  envío simulado → aviso → contrato ACTIVO. Encontró y corrigió un bug: las referencias "manual-N" de la
  carga manual chocaban entre lotes y el segundo lote descartaba sus pagos.

## H-215 · Portal: un solo archivo por documento pedido
**Fecha:** 2026-09-22 · **Módulo:** Portal del ciudadano · **Alcance:** pedido del usuario
- El paso 3 pasa de "elegí el tipo y adjuntá (hasta 10, incluido Otro)" a **tres casilleros fijos**:
  DNI frente, DNI dorso y recibo de sueldo, con **un único archivo cada uno**. Adjuntar de nuevo en un
  casillero reemplaza el anterior; se puede quitar. Sin "Otro".
- El backend del portal exige lo mismo aunque se llame a la API salteando el portal: sólo esos tres
  tipos (422 para cualquier otro) y uno de cada uno por solicitud (409 si ya está).

## H-214 · Crear el cliente desde la solicitud y documentos en la ficha del cliente
**Fecha:** 2026-09-22 · **Módulo:** Créditos / Clientes · **Alcance:** pedido del usuario
- **Crear cliente desde la solicitud:** el backend ya daba de alta la persona en el módulo Clientes
  (`promover-cliente`, H-203), pero la pantalla rehecha sólo ofrecía "Vincular". Vuelve "Crear cliente",
  con un formulario precargado con lo declarado (apellido, nombres, DNI, email) donde el asesor completa
  CUIL, teléfono, domicilio y localidad. Si el documento ya existe en Clientes, se vincula (no duplica).
- **Documentos en el módulo Clientes:** tabla `client_documents` (bytes en la base, como en Créditos),
  API para listar/subir/ver/borrar (`/api/clientes/{id}/documentos`, permisos `clients:read|write`) y
  sección "Documentos" en la ficha, con el mismo visor. Cada documento guarda su origen
  ("Solicitud SOL-…" o "Carga manual"). No se guarda dos veces el mismo archivo (sha256 por cliente).
- **Traspaso:** al crear o vincular el cliente, Créditos le copia los adjuntos de la solicitud por la API
  interna de Clientes (base64, idempotente). Si Clientes no responde, el alta no se deshace: se avisa y
  se reintenta con "Guardar en el cliente" (también disponible en solicitudes que ya tienen cliente).
- El CBU de acreditación no se carga en el cliente: la ficha sólo muestra CBUs de personas jurídicas y
  quedaría invisible; Créditos lo toma de la solicitud.

## H-213 · Portal: documentación en su propio paso y videos obligatorios antes de confirmar
**Fecha:** 2026-09-22 · **Módulo:** Portal del ciudadano · **Alcance:** pedido del usuario
- El trámite pasa a 5 pasos: Tus datos → Simulación → **Documentación** → **Videos** → Confirmación.
- **Documentación (paso 3):** sale de "Tus datos". Para seguir hay que adjuntar DNI frente, DNI
  dorso y el último recibo de sueldo ("Otro" es opcional). Los archivos se siguen subiendo al enviar
  (todavía no hay número de solicitud antes); un borrador retomado vuelve, como mucho, a este paso
  porque los archivos no se guardan en el dispositivo.
- **Videos (paso 4):** tres videos que se ven completos y en orden. No se puede adelantar (un salto
  vuelve al punto más lejano visto) ni cambiar la velocidad; sí volver atrás. Si la pestaña pasa a
  segundo plano, el video se pausa. Terminar el video sin haberlo recorrido no cuenta. Lo visto se
  recuerda en el dispositivo hasta enviar; la solicitud siguiente los vuelve a pedir.
- **Control en el backend:** `POST /portal/solicitudes` exige `videos_vistos` con todos los videos
  configurados (422 si falta alguno) y deja la constancia en `datos_adicionales.videos_vistos`. El
  bloqueo del reproductor corre en el navegador; esta validación impide saltearlo llamando a la API.
- Lista de videos: config `PORTAL_VIDEOS` ("id:Título,…"), expuesta en `GET /portal/videos`. Los
  archivos no van en el repo ni en la imagen: el contenedor del portal los sirve desde
  `CREDITOS_PORTAL_VIDEOS_HOST_PATH` (default `externalfiles/portal_videos`), con soporte de Range.

## H-212 · Impuestos, índices, feriados y workflow pasan al módulo Configuraciones
**Fecha:** 2026-09-22 · **Módulo:** Configuraciones (nuevo, :8011) / Créditos · **Alcance:** pedido del usuario
- La configuración que no tenía pantalla se muda a un módulo propio con backend (base aparte) y
  frontend (`/modules/configuraciones`): **impuestos, índices de referencia, feriados y la definición
  del workflow de aprobaciones**. Los bundles de productos quedan en Créditos (son productos de crédito).
- Créditos los lee por la API interna (`X-Api-Key`), con caché de 30 s y última copia hasta 10 min si
  Configuraciones no responde. **Sin copia, 503**: no se simula con un calendario vacío ni se aprueba
  con una regla inventada (fallar abierto salteaba el cuatro-ojos).
- Créditos conserva la **ejecución** del workflow (`pp_workflow_aprobacion`, con la DB como árbitro por
  nivel) y los GET de impuestos/índices que usa el armado de productos. Sin ABM ni tablas propias.
- Permisos por catálogo (`configuraciones:<catalogo>:read|write`). Configurar el workflow es un permiso
  aparte de operar Créditos.
- **Bug corregido:** las excepciones por usuario de un nivel (INCLUIR / EXCLUIR) se guardaban pero el
  motor las ignoraba. Ahora EXCLUIR saca la aprobación aunque se tenga el rol, e INCLUIR la da sin él.
- **Comportamiento conservado:** un índice dado de baja sigue devolviendo su valor a las líneas
  publicadas (antes también); si no, pasarían a cotizar sólo el margen.
- Migración: `python -m app.etl.migrar_configuraciones` (idempotente por clave natural). Las tablas
  viejas de Créditos quedan como respaldo, sin uso.
- Los componentes de pantalla de Créditos (encabezado, tarjeta, tabla, modal, pills, confirmación)
  pasan a `frontend/src/components/ui` para compartirlos; Créditos los re-exporta.

## H-211 · Poda del backend: sólo el circuito de créditos
**Fecha:** 2026-09-22 · **Módulo:** Créditos (backend, gateway, seguridad) · **Alcance:** cierre de la migración
- **Endpoints.** Se retiran los routers de las áreas de CCyPP que no se migraron: contabilidad, egresos
  (tesorería), seguros, despacho, mesa, juegos, controles de versión, migradores y `auth/mis-permisos`
  (lo reemplaza el gateway). De `caja` quedan el recibo en PDF y los pendientes de cobro; de `admin`,
  líneas, organismos (consulta) y parámetros; de `consultas`, las que usan las pantallas. También
  `aprobaciones/count`. Criterio: se va todo lo que no llama ninguna pantalla del backoffice ni el portal,
  salvo la **configuración del crédito que hoy no tiene pantalla** (impuestos, índices, feriados,
  workflow, bundles, sincronización/perfil crediticio del padrón), que queda documentada como pendiente.
- **Servicios que el crédito usa por dentro** siguen, podados a lo que usa: asientos (`contabilidad`),
  póliza al otorgar (`seguros`), OP del desembolso (`egresos`), recibo de la cancelación (`caja`).
  El registro de auditoría de cada mutación sigue igual; se retira la pantalla de consulta.
- **Código muerto** (análisis de referencias iterado hasta punto fijo): funciones de servicios y
  reportes, ~125 schemas y 23 modelos ORM de áreas retiradas. **Las tablas y sus datos en Postgres no
  se tocan**; el DDL de arranque que alteraba esas tablas se quitó (en una base nueva ya no existen).
- **Permisos.** Una sola área: `creditos:read|write` + `aprobaciones:aprobar|supervisar`. El seed de
  Seguridad **borra** los permisos de las áreas retiradas (y sus asignaciones a roles/usuarios).
  El gateway sólo reenvía los recursos del circuito; lo demás es 404.
- **Workflow.** Configurar los niveles de aprobación pasa de `seguridad:write` a
  `aprobaciones:supervisar` (gateway + módulo): `creditos:write` no alcanza, así quien carga créditos
  no puede sacarse su propio control.
- **Bug corregido.** El inbox de aprobaciones enlazaba a rutas de la SPA vieja (`/creditos/configurar`),
  que en Portezuelo terminaban en el dashboard; ahora `/modules/creditos/...`. Además *Solicitudes de
  crédito* no abría la solicitud del deep link (`solicitud_abrir`): se perdió al portar la pantalla.
- **Límite consciente:** los loaders de ETL de histórico (cheques, contabilidad general, liquidaciones
  de agencias) siguen: son la herramienta de migración de datos productivos, no se exponen.

## H-210 · Se retira la SPA propia del backoffice (`/creditos/`)
**Fecha:** 2026-09-22 · **Módulo:** Créditos · **Alcance:** cierre de la migración al frontend de Portezuelo
- Con las 30 pantallas de crédito ya en `frontend/src/modules/creditos/`, se borró
  `modules/creditos/frontend` (SPA TSX) y su servicio `creditos-web` del compose.
- nginx ya no la sirve: `/creditos` y `/creditos/*` redirigen (301) a `/modules/creditos/`, así los
  accesos guardados no terminan en 404.
- El login de Portezuelo pierde el `?next=` externo, que sólo existía para volver a esa SPA: ahora se
  ignora siempre (menos superficie de open redirect).
- Queda para la próxima etapa la poda del backend de las áreas descartadas (caja, contabilidad,
  tesorería, seguros, despacho, mesa, juegos, migradores), que todavía exponen endpoints.

## H-209 · Servicing: una respuesta sin cuerpo dejaba la pantalla en blanco
**Fecha:** 2026-09-21 · **Módulo:** Créditos (frontend) · **Alcance:** robustez
- `ContratoServicing.aplicar()` propagaba el contrato devuelto por la acción (pago, devengo,
  desembolso, reversa) a `onChange`. Si el endpoint respondía sin cuerpo, el `setDetalle` del
  padre hacía `c.id` sobre `undefined` **dentro del updater**, fuera del `try`: el error escapaba
  al render y tiraba abajo *Situación del cliente* entera (no sólo la fila).
- Ahora `aplicar` recarga siempre y sólo propaga el contrato cuando viene con `id`.
- El test de desembolso tapaba el caso (el doble devolvía `undefined`); ahora devuelve el contrato
  y verifica que tras desembolsar aparecen las acciones de servicing.

## H-208 · Tema claro/oscuro en toda la plataforma
**Fecha:** 2026-09-21 · **Módulo:** Portezuelo (frontend + portal) · **Alcance:** pedido del usuario
- El tema se resuelve con **tokens CSS** (`--c-*` en `index.css`) y `darkMode: "class"` en Tailwind:
  las clases de siempre (`bg-surface`, `text-gray-700`, `bg-blue-50`…) cambian de significado según
  el tema. **No se agregan variantes `dark:` en el markup** — si hace falta un color nuevo, se suma
  un token, no un `dark:`.
- Preferencia por navegador (localStorage, no sessionStorage): sobrevive al cierre de sesión y el
  selector está también en el login. Tres opciones: claro, oscuro y el del sistema operativo, que
  se sigue en vivo sólo mientras esté elegido "sistema".
- Los gráficos del tablero toman su paleta de `modules/creditos/graficos.js` (validada para ambos
  fondos); no quedan hex fijos en el markup.
- El **portal del ciudadano** lleva el mismo selector con sus propios tokens `--p-*`
  (`<html data-tema>`), respetando la identidad CCyPP.

## H-207 · Padrón único de clientes: el maestro pasa al módulo Clientes de Portezuelo
**Fecha:** 2026-09-20 · **Módulo:** Clientes / Créditos · **Alcance:** pedido del usuario
- CCyPP tenía su propio maestro de personas (`clientes`, migrado de `maeclientes`) y Portezuelo el suyo
  (`/api/clientes`): dos padrones para la misma persona. Ahora el **único maestro es el módulo Clientes**.
- En Créditos la tabla `clientes` pasa a ser **espejo de sólo lectura** de la identidad (nombre, documento,
  domicilio, contacto, CBU) y su `id` es el **id del padrón**, no una secuencia local. Lo propio del crédito
  —sueldo, organismo, categoría, débito automático— sigue en Créditos (`PUT /clientes/{id}/perfil-crediticio`).
- Se retiran de Créditos el alta, la edición y la baja de personas (405). El espejo se refresca con
  `POST /clientes/{id}/sincronizar` y al consultar un cliente que todavía no está espejado.
- El módulo Clientes suma dos endpoints internos (no salen del gateway): `/internal/clientes/{id}/ficha`
  (identidad completa) y `/internal/clientes/importar` (alta/merge por documento, idempotente).
- La promoción de una solicitud express (portal) da de alta a la persona **en el padrón** y espeja; si el
  módulo Clientes no responde, devuelve 503 en vez de crear un cliente local.
- **Migración de datos:** `app.etl.migrar_padron_clientes` empuja el maestro CCyPP al padrón por documento,
  reescribe las FKs (solicitudes, créditos, recibos, pólizas) y re-clava el espejo con el id nuevo. Es
  reentrante (tabla `clientes_padron_map`) y tiene `--dry-run`.
- **Pendiente:** los permisos por área de Créditos (`creditos:clientes:*`) quedan sin uso en el front; se
  podan cuando se retire la SPA vieja.

## H-206 · "Limpiar filtros" recargaba con los filtros viejos (cierre obsoleto)
**Fecha:** 2026-09-20 · **Módulo:** Backoffice (frontend) · **Alcance:** cobertura de tests
**Evidencia:** `ResumenCobros`, `ContabilidadGeneral`, `ChequesEmitidos` y `Polizas` llamaban a la
función de recarga en el mismo tick que los `setState` del limpiado, así que la petición salía con
los valores del render anterior: la UI mostraba los filtros vacíos pero los datos seguían filtrados.
En `ChequesEmitidos` y `Polizas` pasaba lo mismo al clickear una fila para filtrar por cuenta/agente
(el pedido iba sin el valor recién elegido).
**Impacto:** corregido pasando los filtros por argumento (`ver(d, h)` / `ver(off, e, filtros)` /
`buscar(off, filtros)`) en vez de leerlos del estado. Cubierto por
`ResumenCobros.test.tsx` y `ContabilidadGeneral.test.tsx`.

## H-205 · Integración con Portezuelo (sistema modular): identidad y permisos del gateway
**Fecha:** 2026-09-18 · **Módulo:** Seguridad / Integración · **Alcance:** pedido del usuario
- CCyPP pasa a ser el módulo **Créditos** de Portezuelo (`modules/creditos`, API :8010). El backoffice se
  publica en `/creditos/` (SPA propia) y su API en `/api/creditos/*` **detrás del gateway**; el portal
  ciudadano en `/portal-creditos/` con su API `/api/creditos/portal/*` directo al módulo (realm propio).
- **Sin login propio**: el gateway valida el JWT de Portezuelo e inyecta X-User-Id / X-Username /
  X-User-Permissions. El `Usuario` local se crea en el primer acceso (por username) para auditoría/workflow.
- **Permisos por área** administrados en Seguridad de Portezuelo: `creditos:<area>:read|write` (clientes,
  creditos, caja, tesoreria, contabilidad, seguros, despacho, mesa, juegos, general, seguridad) +
  `creditos:aprobaciones:aprobar|supervisar` (roles APROBAR / SUPERVISAR de los niveles del workflow).
  Reemplazan perfiles, grupos y permisos por pantalla del módulo (pantallas Usuarios/Grupos/Roles retiradas;
  sus endpoints no se publican en el gateway). Los niveles existentes del workflow se migran a APROBAR.
- **Hallazgo:** con la regla DESEMBOLSO/REFINANCIACION inactiva (default), `rechazar_pendiente` no exigía
  permiso de aprobación (`puede_aprobar` deja pasar a cualquiera sin regla activa). Corregido con el mismo
  criterio que H-153. Caso `pendiente-rechazo-exige-aprobador`.
- **Portal:** fuera de development el proveedor MOCK de Mi Catamarca exige `PORTAL_MOCK_SSO=true` (antes se
  activaba solo sin credenciales: en un portal publicado dejaba entrar a cualquiera como ciudadano demo).
- **Retirado del módulo** (lo reemplaza Seguridad de Portezuelo): login propio, ABM de usuarios/perfiles/
  grupos/permisos por pantalla (endpoints de `/admin` y pantallas), sus tests (`test_iam`,
  `test_admin_usuarios`, `test_qa_usuarios_perfiles`) y 15 casos de Controles de Versión de IAM. Las tablas
  legacy quedan como histórico del ETL. Los tests usan `tests/gateway_emulado.py` para emular el gateway.
- Casos `gateway-identidad`, `gateway-sin-identidad`. Principio `identidad-gateway`.

---

## H-204 · Tablero de cartera profesional (drill-down) + reorden del menú
**Fecha:** 2026-09-18 · **Módulo:** Créditos / Tablero · **Alcance:** pedido del usuario
- **Backend** (`/contratos/tablero`): pasó de agregados básicos a un tablero completo — KPIs (saldo vigente,
  capital colocado, cobrado, ticket prom., plazo prom., **TNA promedio ponderada por saldo**, **mora $ y %**,
  recaudado del mes, por-liquidar, vencen 30 días, cuotas), **desglose por estado y por producto** (con mora %),
  **aging de mora** por tramo (Al día / 1–30 / 31–60 / 61–90 / 90+), **evolución mensual** (originado vs
  cobrado, 6 meses) y el **detalle de contratos** (con `diasAtraso` y `moraBucket`) que alimenta el drill-down.
- **Frontend**: dashboard profesional — 8 tarjetas KPI con contexto, **donut** de cartera por estado, barras de
  **evolución**, tablas de **aging** y **por línea** con barras de participación. **Drill-down**: clic en
  cualquier segmento (tarjeta, estado, tramo de mora, línea, o chips de acceso rápido) abre el panel de detalle
  con los contratos de ese segmento (N°, cliente, línea, estado en pill, monto, saldo, días de atraso, próx.
  venc.). Gráficos en **SVG inline** (sin librerías externas, respeta el candado); CSS scopeado `.tcar-*`.
- **Reorden del menú** Créditos → Archivos (pedido): **Tablero de cartera, Situación del cliente, Solicitudes
  de crédito, Liquidación por lote, Caja de créditos, Resumen de cobros, Sistema de cálculos**, y al final
  Configurar Créditos y Líneas de crédito. "Resumen de cobros" se movió de Reportes a Archivos.
- **Verificado**: en vivo el tablero renderiza KPIs/donut/evolución/aging/producto y el drill-down por línea y
  por estado funciona; `test_tablero_cartera` actualizado a la nueva forma (KPIs + listas + detalle);
  `test_contratos` **45 passed**; tsc + candado OK.
- Caso `tablero-cartera-pro`.

---

## H-203 · Aprobar exige cliente registrado en el maestro
**Fecha:** 2026-09-18 · **Módulo:** Créditos / Solicitudes · **Alcance:** pedido del usuario
- **Requerimiento**: si el cliente **no está registrado** (alta express o solicitud del portal), al querer
  **aprobar** la solicitud debe avisar que el cliente no existe y que hay que **darlo de alta**.
- **Backend**: `POST /api/solicitudes/{id}/estado` con `aprobar` devuelve **409** si la solicitud es
  `NO_REGISTRADO`: "El cliente no está registrado en el maestro. Dalo de alta (o vinculá un cliente existente)
  antes de aprobar." (Rechazar/Anular no lo exigen.) Registrar = `promover-cliente` (crea/vincula el Cliente
  y deja la solicitud REGISTRADO).
- **Frontend**: el panel de detalle muestra el aviso "⚠ El cliente no está registrado en el maestro. Para
  aprobar, primero Dar de alta en maestro o Vincular cliente." y **deshabilita "Aprobar"** hasta registrarlo;
  los botones "Dar de alta en maestro" y "Vincular cliente" ya existían.
- **Verificado**: (API) aprobar sin registrar → 409; tras `promover-cliente` → APROBADA. (UI) en la solicitud
  real SOL-2026-00006 (express) el botón Aprobar aparece deshabilitado con el aviso. Nuevo test
  `test_no_aprobar_cliente_no_registrado`; se actualizaron 4 tests del portal para promover antes de aprobar
  (flujo real); `test_portal`+`test_solicitudes` **40 passed**; tsc + candado OK.
- Caso `aprobar-exige-cliente-registrado`.

---

## H-202 · Solicitud: bloqueo duro por no-elegibilidad (backoffice + portal)
**Fecha:** 2026-09-18 · **Módulo:** Créditos / Solicitudes · **Alcance:** pedido del usuario
- **Requerimiento**: al pedir la solicitud —tanto por el **canal web** como por el **backoffice**— si no cumple
  las condiciones, que **no pueda seguir**. Antes ambos permitían registrar una no-elegible ("un asesor revisa").
- **Backend (autoritativo)**: `POST /api/solicitudes` (backoffice) y `POST /api/portal/solicitudes` (portal)
  evalúan la elegibilidad con la **misma fuente que la simulación** (`_evaluar`) y devuelven **422** con los
  motivos si lo declarado no cumple (segmento/canal/edad/antigüedad/monto/plazo). Un dato **no declarado** no
  bloquea: `_elegibilidad` sólo aplica la regla del atributo cuando ese dato viene (así el portal no frena a
  quien aún no cargó su perfil; el backoffice revisa).
- **Frontend backoffice**: el asistente deshabilita **"Continuar"** (paso Simulación) y los botones
  **"Guardar borrador"/"Crear y enviar"** cuando la simulación da no elegible; el mensaje pasó de "podés
  registrarla igual" a "No cumple las condiciones… Ajustá los datos o elegí otra línea para continuar".
- **Frontend portal**: deshabilita **"Confirmar y enviar solicitud"** con el mismo criterio y avisa que no se
  puede enviar hasta cumplir las condiciones.
- **Verificado**: (backend) no elegible → 422 con motivos; elegible → 201. (UI backoffice) "Continuar"
  deshabilitado con LP-JUB-01 + AGENTE_PUBLICO/40, y re-habilitado al pasar a LP-PERS-01. Tests: se ajustó
  `test_no_crear_solicitud_no_elegible` (crear no-elegible → 422); `test_solicitudes`+`test_portal` **39 passed**;
  tsc + candado OK.
- **Nota (lotes)**: se revisó "Liquidación por lote" — **ya** agrupa por día de originación (`fecha_valor`) y
  sólo liquida los del mismo día; no requería cambio (era el comportamiento pedido).
- Caso `solicitud-bloqueo-no-elegible`.

---

## H-201 · Configurar Créditos: la copia independiente retiraba el original
**Fecha:** 2026-09-18 · **Módulo:** Créditos / Configurar · **Alcance:** bug reportado por el usuario
- **Síntoma**: al crear un préstamo como **copia independiente** (Nueva línea → "Basar en …" → Copia
  independiente, o botón Duplicar) y publicarlo, el sistema **retiraba la línea de origen** ("con qué me basé").
- **Causa**: `publicarCambios` (ConfigurarCreditos.tsx) tras publicar una copia (`copiadoDe`) mostraba
  "¿Retirar el original?" y, si se confirmaba, llamaba `ppEstado(orig, "retirar")`. Ese paso venía del modelo
  viejo "nueva versión reemplaza a la anterior", que ya no aplica: una **copia independiente es un préstamo
  nuevo que coexiste** con su origen (lo que pidió el usuario: "que funcione como préstamo independiente").
- **Fix**: se eliminó el ofrecimiento/retirada del original al publicar una copia. Publicar una copia ya
  **no toca** el original; el aviso ahora dice "El original queda intacto (son independientes)". Si se quiere
  dejar de ofrecer el original, se retira a mano desde su propio menú ("Retirar línea"). `copiado_de` queda
  sólo para trazabilidad/linaje (comentario del backend actualizado).
- **Verificado en vivo**: se creó QA-COPIA-H201 basada en LP-PERS-01, se publicó → la copia quedó PUBLICADO
  y **LP-PERS-01 siguió PUBLICADO** (no retirado); sin prompt de retirar. tsc + candado OK. Datos QA limpiados.
- Caso `copia-independiente-no-retira-original`.

---

## H-200 · Auditoría del alta de crédito (pantalla por pantalla): 3 defectos
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Solicitudes · **Alcance:** pedido del usuario (registrar comportamiento + mejoras/bugs)
- **Registro de comportamiento** del flujo de alta: (1) *Lista* — header + "＋ Nueva solicitud", filtros por
  estado en pills, búsqueda, tabla DataTable (N°/cliente/monto/plazo/cuota est./estado con pill). (2)
  *Asistente 3 pasos* — Solicitante (cliente del maestro con autocompletar, segmento, edad, antigüedad,
  relación), Simulación (línea filtrada por canal del backoffice, monto, plazo, **simulación en vivo** con
  debounce + mensaje de elegibilidad), Confirmación (resumen + destino + observaciones + Guardar borrador /
  Crear y enviar). (3) *Panel de detalle* — acciones según estado (Enviar / Aprobar-Rechazar-Anular /
  Originar), cronograma colapsable, diálogos in-app. (4) *Liquidación por lote* — lotes por día, Ver
  contratos, Liquidar → desembolso con confirmación.
- **Defecto 1 (BUG global — errores ilegibles)**: un 422 con `detail` estructurado (validación Pydantic) se
  mostraba como **"[object Object]"** en el banner de error (p. ej. al enviar la solicitud). Causa:
  `api.ts` hacía `new Error(detail.detail)` con un **array**. **Fix**: `mensajeDeError()` normaliza el array a
  texto por campo ("edad: debe ser ≥ 18", "campo: es obligatorio", etc.). Aplica a **toda la app**.
- **Defecto 2 (MEJORA — edad fuera de rango)**: el campo Edad aceptaba `< 18` (clamp cliente 0–99) aunque el
  label y el backend exigen 18–99, llegando a un alta que el backend rechazaba. **Fix**: se bloquea
  "Continuar" con **aviso inline** ("La edad debe estar entre 18 y 99") cuando la edad está fuera de rango.
  **Verificado en vivo** (edad 5 → botón deshabilitado + aviso).
- **Defecto 3 (BUG — TNA de la evaluación en tasa variable)**: `_evaluar` calculaba la cuota/TNA estimada con
  `_tasa` (sólo `tasa_default` → **0** en productos de tasa VARIABLE), así una línea BADLAR mostraba la cuota
  estimada **sin interés** y no coincidía con la simulación ni con la originación (que usan `_tna_base` =
  índice+margen). **Fix**: `_evaluar` usa `_tna_base` — motor único / simulado==contratado.
- Caso `auditoria-alta-credito`.

---

## H-199 · QA e2e de créditos (3+ hasta liquidar): dos defectos corregidos
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Solicitudes · **Alcance:** QA profundo pedido por el usuario (API + UI)
- **Corrida técnica (API)**: 3 créditos desde solicitud → evaluación → aprobación → originación → liquidación
  (LP-PERS-01 y LP-JUB-01 por **desembolso individual**, LP-VAR-01 por **lote**), + cobranza post-liquidación
  en uno, + prueba negativa (backoffice **no** puede originar la línea WEB-only LP-NUEVA-08 → 422). **32/32
  checks OK**. Contabilidad: los 4 asientos (3 otorgamiento + 1 pago) **balanceados** (debe=haber), doble
  partida correcta (Préstamos otorgados / Caja), `empresa_id` consistente. Cronograma francés correcto
  (capital+interés constante; la cuota 1 es más alta por el **cargo de otorgamiento** + IVA — no es bug).
- **Corrida de usuario (UI)**: 1 crédito completo por pantalla (asistente Nueva solicitud → Crear y enviar →
  Aprobar → Originar → Liquidar por lote → desembolsado, CTO-2026-00006 ACTIVO + asiento balanceado). La
  simulación en vivo del asistente **valida elegibilidad** (bloqueó LP-JUB-01 para AGENTE_PUBLICO/edad 40) y
  todos los diálogos son **in-app** (no nativos). Decimales "para mostrar" respetados (cuota a 2 decimales).
- **Defecto 1 (refresco de estado)**: tras "Crear y enviar a evaluación", el panel de detalle quedaba en
  **BORRADOR** con botón "Enviar a evaluación" pese a estar ya EN_EVALUACION (la lista sí era correcta).
  Causa: `crear()` esperaba `r.solicitud` del `POST /solicitudes/{id}/estado`, que devuelve el serial directo.
  **Fix**: `if (r?.id) s = r` (como `resolver()`). Se reabre el panel y muestra el estado correcto.
- **Defecto 2 (oferta del backoffice sin filtro de canal)**: el asistente listaba la línea **"Prestamo Web"
  (WEB-only)** porque pedía `ppOferta()` sin canal; originarla igual se rechazaba (elegibilidad), pero no
  debía ofrecerse. **Fix**: `/contratos/segmentos` expone `canalBackoffice` y el asistente pide la oferta
  filtrada por ese canal → aplica el filtro duro de canal (H-185) también en el alta del backoffice.
- Caso `qa-e2e-solicitud-hallazgos`.

---

## H-198 · Créditos: decimales de CÁLCULO vs decimales para MOSTRAR
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Parámetros · **Alcance:** pedido del usuario ("para redondeo toma 4, pero para mostrar 2")
- **Desdoble en dos parámetros**: el único `DECIMALES_CALCULO` se separa en (a) `DECIMALES_CALCULO`
  (0–6, default 2) = precisión INTERNA con que el motor `cronograma` redondea cada cuota (ej. 4), y (b)
  `DECIMALES_MOSTRAR` (0–6, default 2) = decimales con que se PRESENTAN los importes en pantalla (ej. 2).
  `DECIMALES_MOSTRAR` **no** altera el cálculo, sólo la visualización. Ambos ámbito `creditos`.
- **Backend**: helper `decimales_mostrar(db)` (refactor de `_decimales_param`); se seedean/backfillean ambos;
  `/contratos/segmentos` ahora devuelve `decimalesCalculo` y `decimalesMostrar` para el front.
- **Frontend**: "Parámetros de créditos" muestra los DOS campos ("para el cálculo (redondeo)" + "para
  mostrar"). En "Solicitudes de crédito" el formateo de importes (`fmtMoney`) usa `decimalesMostrar` de
  `/contratos/segmentos` (KPIs de simulación, resumen y cronograma).
- **Orden de menú**: por pedido, "Parámetros de créditos" se movió del módulo Créditos al módulo **General**
  (junto a "Parámetros generales"); la ruta `/creditos/parametros` no cambia.
- **Verificado**: tests + candado + tsc (ver abajo). Caso `decimales-calculo-vs-mostrar`.

---

## H-197 · Créditos: parámetros por ámbito + decimales del cálculo
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Parámetros · **Alcance:** pedido del usuario (separar params + decimales)
- **Separación por ámbito**: se agregó `Parametro.ambito` (`general` | `creditos` | `contabilidad`) con
  migración + backfill. "Parámetros generales" ahora filtra a `general` (los de canales/decimales y
  contables ya no se mezclan ahí). Endpoint `/admin/parametros?ambito=...`.
- **Pantalla nueva "Parámetros de créditos"** (Créditos): catálogo de **canales** (chips editables, +
  agregar, canal del portal, canal del backoffice) + **decimales del cálculo** (0–6).
- **Decimales del cálculo (nuevo, exclusivo de créditos)**: parámetro `DECIMALES_CALCULO` (default 2). El
  motor `cronograma` redondea cada cuota con esa precisión (`_r(x, dec)`); se pasa desde `_params_cronograma`
  a través de `decimales_calculo(db)` en preview, portal, solicitud y **originación**. Los contratos ya
  originados **conservan** su cronograma (snapshot); aplica a cálculos nuevos.
- **Verificado**: en vivo la cuota pasó de $137456,83 (2 dec) a $137457 (0 dec) al cambiar el parámetro, y
  volvió al restaurar. Tests `test_decimales_calculo_redondea_la_cuota` + `test_parametros_por_ambito`;
  módulos productos/contratos/portal/solicitudes **114 passed**; candado 109 + tsc OK. Pantalla en vivo.
  Caso `parametros-por-ambito`.

---

## H-196 · Créditos: se saca el Canal del alta de solicitud + validación de campos
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Solicitudes · **Alcance:** pedido del usuario
- **Canal fuera del alta de solicitud**: el canal es una propiedad de la **configuración del producto**
  (Disponibilidad), no una elección del operador al pedir la solicitud. Se quitó el selector; el alta de
  backoffice queda con canal **SUCURSAL** por defecto (la elegibilidad de canal la resuelve la config).
- **Validación de campos (buenas prácticas)**: edad **18–99** (2 dígitos) y antigüedad **0–1200 meses**
  (hasta 4 dígitos), con **clamp en el input** (frontend) y en el modelo **Pydantic `SolicitudIn`** (backend,
  `ge`/`le`) — la validación autoritativa vive en la API por donde pasan todas las escrituras. Monto y plazo
  (1–240) también acotados. (Un CHECK a nivel DB queda como refuerzo opcional.)
- **Verificado en vivo**: el paso 1 del wizard ya no muestra Canal; Edad (18–99) y Antigüedad (0–1200) con
  sus límites. Candado 108 + tsc OK. Caso `solicitud-campos-validacion`.

---

## H-195 · Créditos: se unifica "Originar" en "Solicitudes" + flujo de pedido mejorado
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Solicitudes · **Alcance:** consolidación de UX (pedido del usuario)
- **Observación del usuario (correcta):** "Originar Crédito (oferta)" y crear una "Solicitud" desde el
  backoffice hacen lo mismo — la pantalla **Solicitudes de crédito** ya trae el mismo wizard (buscar cliente
  del maestro → elegir línea de la oferta + simulación → confirmar) y además gestiona todo el ciclo. Nada
  navegaba a `/creditos/originar` salvo el menú.
- **Cambio:** se **retiró "Originar Crédito (oferta)"** del menú; `/creditos/originar` **redirige** a
  `/creditos/solicitudes-credito` (por si quedan deep links). El componente OriginarCredito queda sin uso.
- **Mejora del flujo de pedido:**
  - **Simulación EN VIVO**: en el paso 2, al cambiar línea/monto/plazo se recalcula sola (debounce), sin el
    botón "Simular".
  - **"Crear y enviar a evaluación"**: en el paso 3, un botón crea la solicitud y la **manda al Inbox** en un
    solo paso (además de "Guardar borrador").
- **Verificado en vivo**: menú sin "Originar"; wizard con GOMEZ, MARIA LAURA → sim en vivo (Cuota $68.812,
  TNA 41%, "✓ Elegible") → confirmación con los dos botones. Candado 108 + tsc OK. Caso `solicitud-unifica-originar`.

---

## H-194 · UX: Inbox como landing + cuadro de control con agrupaciones
**Fecha:** 2026-09-17 · **Módulo:** UX / Navegación · **Alcance:** pedido del usuario
- **Landing**: al ingresar (login) se va **directo al Inbox** (y el catch-all de rutas también).
- **Renombre + ícono**: "Inbox de aprobaciones" → **"Inbox"**; ícono modernizado (bandeja SVG en un badge
  redondeado, en la pantalla y en la barra superior).
- **Cuadro de control**: la pantalla ya no es una lista plana. Muestra **agrupaciones** (Solicitudes de
  crédito, Líneas de crédito, Desembolsos, Refinanciaciones, + "Otros") como tarjetas con su **cantidad**;
  las vacías quedan atenuadas. Al entrar en una agrupación se ve la **lista** de lo pendiente de ese grupo
  (aprobar/publicar/resolver, inline o con deep-link a la pantalla), con **"← Panel"** para volver.
- **Campana de alertas**: se **quitó** del Topbar por redundante con el Inbox (el Inbox ya avisa lo
  pendiente); queda solo el ícono de Inbox. Se le podrá dar otro uso más adelante (notificaciones del sistema).
- **Íconos de las agrupaciones**: se reemplazaron los emojis por **íconos de línea SVG** (estilo del sistema)
  en badges redondeados — Solicitudes (documento), Líneas de crédito (tarjeta), Desembolsos (billete),
  Refinanciaciones (ciclo), Otros (paquete); los grupos vacíos quedan atenuados.
- **Verificado en vivo**: login como admin → cae en el Inbox; el panel mostró Líneas de crédito con **1**
  pendiente ("Ver 1 →") y el resto en 0; al entrar → ítem "Adelanto de Haberes LP-ADEL-01, EN_REVISION,
  pedido por creditos"; el Topbar quedó solo con el ícono de Inbox. Candado 108 + tsc OK. Caso `inbox-cuadro-control`.

---

## H-193 · UX: vista restringida del menú lateral por rol
**Fecha:** 2026-09-17 · **Módulo:** UX / Navegación · **Alcance:** pedido del usuario
- **Regla de visibilidad del sidebar:** la vista **restringida** muestra sólo **Clientes** y **General**
  completos + **todas las opciones `new`** (los demás módulos aparecen únicamente si tienen alguna opción
  nueva, mostrando sólo ésas).
- **Por rol:** es **siempre** así para usuarios **no-ADMG**; el **administrador (ADMG)** por defecto ve todo
  y tiene el botón **"Ocultar módulos"** para alternar a la vista restringida (y "Mostrar todos los módulos"
  para volver). El botón sólo aparece para ADMG (perfil del JWT).
- Reemplaza el viejo esquema `oculto`/`soloNuevos` por una **regla uniforme** (`SIEMPRE_VISIBLE = {Clientes,
  General}` + `i.nuevo`). La seguridad real la sigue dando el RBAC (`puedeVer`); esto es sólo la vista.
- **Verificado en vivo:** admin (ADMG) → ve todo, "Ocultar" deja {Clientes, General, + módulos con `new`}
  (se ocultan Caja/Juegos/Mesa/Seguros/Tesorería/Adm.Finanzas, sin `new`); usuario XCR (creditos) → vista
  restringida SIEMPRE, sin botón. Candado 108 + tsc OK. Caso `sidebar-vista-restringida`.

---

## H-192 · UX: Inbox como ícono en la barra superior + limpieza de BADLAR
**Fecha:** 2026-09-17 · **Módulo:** UX / Navegación · **Alcance:** pedido del usuario
- El **Inbox de aprobaciones** pasó a ser un **ícono (bandeja)** en el Topbar, junto a la **campana** de
  alertas, con el badge de tareas pendientes. Se quitó "Inbox de aprobaciones" del menú de Créditos.
- **Limpieza de dato legacy (Opción A):** se descartó la versión BORRADOR (v2) remanente de "Crédito Tasa
  Variable (BADLAR)" con el DELETE version-aware existente — borra sólo la versión, deja la v1 publicada; la
  solicitud asociada referencia el producto (no la versión), así que no se toca. BADLAR quedó PUBLICADO v1.
- **Verificado en vivo:** ícono Inbox + campana en el Topbar; Inbox fuera del menú de Créditos; BADLAR
  PUBLICADO. Candado 108 + tsc OK. Caso `inbox-topbar`.

---

## H-191 · Configurar Créditos: vistas del catálogo (tarjetas / en línea) + saque del badge de versión
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Configurar · **Alcance:** UX del catálogo (pedido del usuario)
- **Selector de vistas** en el catálogo: **▦ Tarjetas** (la de siempre) y **≣ En línea** (lista con el
  componente `DataTable`: Línea+código, Estado con pill, Sistema, TNA, Monto, Plazo + menú de acciones ⋯).
  La elección se persiste en `localStorage` (`cfgc_vista`). Base para sumar más vistas a futuro.
- **Se quitó el badge "🌐 portal: vN"** de las tarjetas: era un remanente del versionado interno que
  confundía. Con el modelo de préstamos independientes (H-190) ya no se generan versiones internas, así que
  el badge dejaba de tener sentido.
- **Verificado en vivo:** toggle Tarjetas/En línea funciona; la lista respeta el candado (tabla = DataTable,
  pills, CSS scopeado `.cfgc-`); BADLAR ya no muestra "portal: v1". Candado 108 + tsc OK. Caso `catalogo-vistas`.

---

## H-190 · Configurar Créditos: duplicar en vez de versionar (préstamo independiente)
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Configurar · **Alcance:** simplificación de UX (pedida por el usuario)
- **Problema:** crear una variante de un préstamo publicado era confuso — "Nueva versión" agregaba una v2 al
  MISMO producto y hacía convivir "borrador v2" con "portal: v1", más el ciclo revisar→aprobar→publicar (~7 pasos).
- **Modelo nuevo — préstamos independientes:** en vez de versionar, se **duplica**. **⧉ Duplicar** crea un
  préstamo **NUEVO e independiente** (código propio, copia de la config vía `copiar_de`), que se edita y
  publica por su cuenta. Guarda `PPProducto.copiado_de` (trazabilidad + prompt de retirar-original).
- **Publicación en un paso:** `POST /api/productos/{id}/publicar-directo` encadena revisar→aprobar→publicar
  cuando el cuatro-ojos (regla LINEA) está **inactivo**; si está **activo**, sólo manda a revisión y devuelve
  `needs_approval=true` (otra persona aprueba — no se pierde la separación de funciones).
- **UI:** en el catálogo y en el editor, "Nueva versión" → **⧉ Duplicar** (pide el nombre, prellenado
  "… — copia"); en el borrador, botón único **Publicar** + **Descartar** (borra el borrador entero); al
  publicar una copia de un publicado, se ofrece **retirar el original**. De ~7 pasos a **2** (Duplicar → Publicar).
- **Verificado:** `test_duplicar_como_prestamo_independiente` (duplicar → publicar-directo en un paso →
  retirar original; copiadoDe correcto). Productos+contratos+portal+lifecycle **107 passed**; candado 108 +
  tsc OK. En vivo: Duplicar "Crédito Jubilados" → préstamo independiente LP-NUEVA-01 (borrador, código propio)
  con banner y botones nuevos → Descartar → borrado; DB limpia (7 productos). Caso `duplicar-prestamo-independiente`.

---

## H-189 · Portal (bug + mejora): opt-in de canal y disponibilidad editable en publicado
**Fecha:** 2026-09-17 · **Módulo:** Créditos / Portal · **Alcance:** QA del canal web
- **Bug (detectado por el usuario):** el portal mostraba productos **sin canal configurado** (p. ej.
  "Crédito Tasa Variable (BADLAR)", con la Disponibilidad **inactiva**). Causa: `_ofrecible_web` trataba
  "componente AVAILABILITY inactivo" como "sin canales = todos" → se ofrecía por la web.
- **Fix — OPT-IN público:** un producto aparece en el portal **sólo si la Disponibilidad está ACTIVA**
  (con el canal del portal, o `canales` vacío = todos). Sin Disponibilidad configurada → **no** se lista
  ni se puede solicitar (422). Evita exponer al público productos que nadie habilitó. Verificado en vivo:
  el portal pasó de mostrar {BADLAR, Prestamo Web, Personal Flexible} a **{Prestamo Web, Personal
  Flexible}** (los que tienen WEB); Jubilados (SUCURSAL/CONVENIO) sigue afuera.
- **Mejora (pedida por el usuario):** la **Disponibilidad se puede editar aunque la línea esté PUBLICADA**,
  sin crear versión nueva — canales/segmentos/reglas son metadata de **distribución**, no términos
  financieros congelados (no alteran contratos ya originados ni el cronograma). Endpoint
  `PUT /api/productos/{id}/disponibilidad` (upsert del componente AVAILABILITY sobre la versión vigente,
  cualquier estado). En Configurar Créditos los chips de canal quedan editables en producto publicado, con
  botón **"Guardar disponibilidad"**.
- **Verificado:** `test_portal_no_muestra_sin_disponibilidad` (inactiva → no aparece; al activar WEB en la
  publicada aparece). Portal+productos+contratos **99 passed**; candado 108 + tsc OK. Caso `portal-opt-in-canal`.

---

## H-188 · Contabilidad: libros separados por empresa (multi-plan)
**Fecha:** 2026-09-17 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (múltiples planes por empresa)
- **Modelo `Empresa`** (ente contable; una es predeterminada). Se agregó **`empresa_id`** a `cuentas_contables`,
  `asientos`, `ejercicios_contables` y `extracto_bancario_lineas`. El **código de cuenta pasó a ser único
  POR empresa** (antes único global): dos empresas pueden tener el mismo `1.1.01`.
- **Migración segura:** create_all crea `empresas`; `_migrar_iam` siembra la empresa predeterminada,
  agrega `empresa_id` (ALTER), **backfillea** todos los datos existentes a ella, baja la unique global de
  `codigo` y sube la compuesta `(empresa_id, codigo)`. Eventos `before_insert` defaultean la empresa
  predeterminada en cuentas/asientos → **el comportamiento mono-empresa queda idéntico** (todos los tests
  contables previos siguen verdes sin cambios).
- **Scope por empresa en TODO:** plan de cuentas (ABM + cargar-estándar/restaurar), sumas y saldos, estados
  contables, flujo de efectivo, conciliación bancaria, análisis por centro, asientos manuales, ejercicios
  (crear/cerrar/apertura, sin solape dentro de la empresa). Los generadores automáticos (otorgamiento/
  cobranza/pp_*) y cierre/apertura estampan la empresa correcta.
- **API:** `/contabilidad/empresas` (GET, POST, POST `/{id}/predeterminada`) + `empresa_id` en los reportes
  y el plan. **Front:** selector de empresa en Plan de cuentas (persistido en localStorage) que se inyecta
  como `empresa_id` en toda llamada `/contabilidad/*` (un solo punto en `api.req`).
- **Verificado:** `test_libros_separados_por_empresa` (empresa B con su plan y un asiento que NO aparece en
  los libros de A; código `1.1.01` conviviendo en ambas). Módulos contabilidad+contratos **65 passed** tras
  el refactor; migración Postgres OK (empresa GRAL, 45/45 cuentas y 2/2 asientos backfilleados); selector
  en vivo. Caso `multi-empresa-contable`.
- **Simplificación consciente (fase futura):** diarios, centros de costo e imputaciones siguen siendo
  GLOBALES (compartidos entre empresas); los contratos/servicing siguen posteando a la empresa
  predeterminada. Asignar contratos a una empresa distinta de la principal es el próximo incremento.

---

## H-187 · Contabilidad: Conciliación bancaria
**Fecha:** 2026-09-17 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (conciliación bancaria)
- **Modelo `ExtractoBancarioLinea`** (líneas del resumen del banco; `importe` con signo: + ingreso / − egreso;
  `conciliada` + FK opcional al movimiento del mayor). Tabla nueva (se crea sola con `create_all`).
- **Cotejo** contra los movimientos del **mayor** (asientos publicados) en la cuenta banco. **Conciliar
  manual**: seleccionar una línea del extracto → vincular un movimiento del **mismo importe con signo**
  (valida cuenta, importe y que el movimiento no esté ya conciliado). **Conciliar automática**: empareja
  pares del mismo importe sin conciliar, 1 a 1, prefiriendo fecha cercana. Se puede **desconciliar**.
- **Estado**: saldo extracto vs saldo mayor + **diferencia** (0 = cuadra) y pendientes de cada lado.
- **API** `/contabilidad/conciliacion` (GET estado; POST extracto/conciliar/desconciliar/automatica;
  DELETE extracto). **UI** pantalla "Conciliación bancaria" (Contabilidad → Reportes): resumen + dos tablas
  (extracto / mayor) con selección y vinculación, alta de líneas de extracto, automática.
- **Verificado:** `test_conciliacion_bancaria` (depósito 50k + pago 20k: manual + automática + validación de
  importe + desconciliar). Candado 108 páginas + tsc OK; página verificada en vivo sin errores. Caso
  `conciliacion-bancaria`.

---

## H-186 · Contabilidad: Flujo de efectivo (cash flow, método directo)
**Fecha:** 2026-09-17 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (flujo de efectivo)
- **Flujo de efectivo por método directo** sobre las cuentas de efectivo (Caja/Banco, configurables en el
  Parámetro **CUENTAS_EFECTIVO** = `1.1.01,1.1.02`): **saldo inicial** (mov. previos a "desde") +
  **entradas** y **salidas** del período agrupadas por la cuenta de **contrapartida** (de dónde vino / a
  dónde fue la plata) + **saldo final**. Sólo asientos publicados. `neto = Σentradas − Σsalidas =
  saldo final − inicial`, y **cuadra** con el saldo de Caja de sumas y saldos.
- **API** `GET /contabilidad/flujo-efectivo` (`svc.flujo_efectivo`); **UI** pestaña "Flujo de efectivo" en
  Estados contables (saldo inicial, entradas/salidas por contrapartida, flujo neto, saldo final).
- **Verificado:** `test_flujo_efectivo` (entrada 100k / salida 30k / neto 70k; con `desde` arrastra el
  saldo inicial). En vivo con los asientos reales: entradas 366.424,59 − salidas 4.553.036,21 = −4.186.611,62,
  igual al saldo acreedor de Caja. Caso `flujo-efectivo`.

---

## H-185 · Créditos: el canal deja de estar hardcodeado — catálogo y códigos configurables en Parámetros
**Fecha:** 2026-09-16 · **Módulo:** Créditos / Portal · **Alcance:** parametrización + separación real de canal
- **Motivación:** el código de canal ("WEB", "SUCURSAL") estaba **hardcodeado** en la API. Se llevó a
  **Parámetros** (tabla `parametros`, editable en Controles → Parámetros generales), siguiendo el principio
  de parametrización del proyecto. Tres parámetros sembrados y obligatorios (garantizados por seed):
  - `CANALES` = `SUCURSAL,WEB,APP,CONVENIO` — catálogo de canales (reemplaza la lista hardcodeada).
  - `CANAL_PORTAL` = `WEB` — qué canal habilita el **portal del ciudadano**.
  - `CANAL_BACKOFFICE` = `SUCURSAL` — canal asumido al originar desde el backoffice sin canal explícito.
- **La API los lee** (`canales_catalogo` / `canal_portal` / `canal_backoffice` en `productos.py`, con
  fallback al default): `GET /contratos/segmentos` devuelve el catálogo configurable; el fix H-184 usa
  `canal_backoffice(db)`; el portal usa `canal_portal(db)`.
- **Separación real de catálogo por canal (antes NO existía):** `GET /portal/productos` ahora **lista solo
  los productos habilitados en el canal del portal** — un producto sólo-SUCURSAL ya **no aparece** en la
  web (antes se listaban todos los publicados). Guarda dura en `POST /portal/solicitudes`: aunque se conozca
  el id, un producto no habilitado por el canal web da **422** ("no disponible por el canal web").
- **Configurable de punta a punta:** cambiar `CANAL_PORTAL` a `SUCURSAL` invierte qué productos ofrece el
  portal (cubierto por test).
- **Verificado:** `test_canal_web_filtra_portal_y_es_configurable` (test_portal.py) + módulos portal/
  productos/contratos **97 passed**. Parámetros visibles y editables en la pantalla Parámetros generales.
  Caso `canal-parametrizado`.
- **Refuerzos posteriores (misma tanda):**
  - **Parámetros OBLIGATORIOS (estricto):** los readers (`canales_catalogo`/`canal_portal`/`canal_backoffice`)
    fallan con error claro si el parámetro no existe, en vez de un default silencioso. Sembrados en el
    lifespan (producción) y en el fixture de tests.
  - **Oferta del backoffice filtra duro por canal:** `GET /contratos/oferta?canal=SUCURSAL` **no lista** un
    producto solo-WEB (antes sólo lo marcaba no elegible). Test `test_oferta_backoffice_filtra_por_canal`.
  - **UI:** el chip de canales/segmentos de Configurar Créditos ahora lee el catálogo configurable de
    `GET /contratos/segmentos` (la lista fija quedó sólo como fallback).
  - **Producto demo:** "Prestamo Web" (canal solo WEB) recreado y **publicado** de forma permanente.

---

## H-184 · Créditos (bug QA): un producto "solo WEB" se podía originar desde el backoffice con canal vacío
**Fecha:** 2026-09-16 · **Módulo:** Créditos / Originación · **Alcance:** E2E canal web punta a punta
- **Escenario probado (E2E):** producto **"Prestamo Web"** con Disponibilidad → **Canales = ["WEB"]** (solo
  portal) → publicado → solicitud creada desde el **portal del ciudadano** (canal=WEB, origen=PORTAL) →
  llega a la bandeja del backoffice → **control: no tomable desde backoffice** → originación legítima por
  canal WEB → liquidación/desembolso → **asiento de otorgamiento** visible en Libro diario, balanceado.
  Resultado del corrido por API: **21 OK / 0 FALLA / 1 BUG**.
- **Control que SÍ funciona:** originar con `canal=SUCURSAL` → **422** ("Canal SUCURSAL no habilitado
  (permitidos: WEB)"); en la oferta figura NO elegible y `solo_elegibles=true` lo excluye.
- **BUG encontrado:** originar **sin canal** (campo vacío/omitido) **salteaba** el chequeo de disponibilidad
  (`_elegibilidad`: `if disp["canales"] and can and ...` — con `can` vacío no evalúa el canal), de modo que
  un producto solo-WEB **se podía originar desde el backoffice** como venta directa. `OriginarCredito.tsx`
  manda `canal: cliente.canal || undefined`, así que un canal vacío llegaba al server sin piso.
- **Fix (`contratos.py` `_originar_impl`):** canal efectivo = `data.canal or (canal de la solicitud web) or
  "SUCURSAL"`. Así, originar sin canal desde el backoffice asume **SUCURSAL** (y un solo-WEB queda 422);
  si la originación proviene de una **solicitud del portal**, hereda su canal (WEB) y se procesa OK.
- **Verificado:** live post-fix — canal vacío → **422**, SUCURSAL → 422, WEB → 201. Regresión:
  `test_web_only_no_se_origina_desde_backoffice` (test_contratos.py). Datos QA (producto, solicitud,
  2 contratos, asiento de otorgamiento, actividad) **limpiados** de Postgres. Caso `originacion-canal`.
- **Observaciones de diseño (no bug, mejora sugerida):** (1) el **portal lista TODOS los productos
  publicados**, no filtra por canal WEB — hoy un producto solo-SUCURSAL igual aparecería en el portal;
  (2) "solo web" no es un flag de primera clase sino el array `canales` de AVAILABILITY. Si se quiere
  separación dura de catálogo por canal, conviene filtrar `GET /portal/productos` y `GET /contratos/oferta`
  por canal, o agregar visibilidad explícita en `PPVersion`.

---

## H-183 · Contabilidad (bug QA): la reversa no preservaba el centro de costo
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** QA profundo de H-182
- **Detectado en QA en vivo contra Postgres** (no en SQLite): al **reversar** un asiento manual, el
  contra-asiento (`reversar_asiento`) copiaba cuenta y montos invertidos pero **omitía `centro_codigo`**.
  Consecuencia: el asiento original impactaba su centro (p. ej. ADM) y su reversa caía en **"Sin centro"**,
  dejando el análisis por centro **asimétrico** (cada centro no neteaba a cero, aunque el neto global sí).
- **Fix:** `reversar_asiento` ahora copia `centro_codigo` por línea. La reversa cae en el mismo centro que
  el original → el centro netea a cero (bruto duplicado, saldo 0) y nada cae en "Sin centro".
- **Nota de diseño:** los asientos de **cierre (refundición)** y **apertura** siguen sin centro a propósito
  (son resúmenes a nivel cuenta que agregan múltiples centros; no corresponde imputarlos a uno solo).
- **Verificado:** QA en vivo contra Postgres **15/15 OK** (alta de centro, validación de centro inexistente
  →422, borrador no impacta / publicado impacta el saldo neto, por-centro refleja, reversa netea el centro
  y devuelve el saldo original; datos QA limpiados). Regresión cubierta en `test_centros_costo_analitica`
  (la reversa deja COM con bruto duplicado y saldo 0, sin fila "Sin centro"). Suite backend completa verde.

---

## H-182 · Contabilidad: centros de costo + test E2E del flujo contable
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (paso 6) + QA
- **Centros de costo** (dimensión analítica, tipo Odoo): ABM en **Contabilidad → Centros de costo**
  (código/nombre/activo), sembrados **ADM / COM / FIN / SEG**. Cada **línea de asiento** puede llevar un
  centro (columna **"Centro de costo"** en el editor, `— sin centro —` opcional); se valida contra centros
  **activos**. Modelo `CentroCosto` + `AsientoLinea.centro_codigo`.
- **Reporte "Por centro de costo"** en Estados contables: debe/haber/saldo por centro, con bucket
  **"Sin centro"**. Servicio `analisis_por_centro`; endpoints `/contabilidad/centros-costo` (GET/POST/PUT)
  y `/por-centro`.
- **Test E2E** (`test_e2e_contable`): recorre el flujo completo de punta a punta — cargar **plan estándar**
  → **parametrizar** (imputación evento→cuenta) → **asiento con centro** borrador→publicado → **estados
  contables** balanceados → **ejercicio** abierto → **cierre** (refundición a 3.3) → **bloqueo** del período
  → **export Excel**. Doble como plan de test; espejo del **manual con pantallas**.
- **Verificado:** suite backend **377 passed** (2 nuevos: `test_centros_costo_analitica`,
  `test_e2e_contable`); tsc + candado OK (107 páginas); UI verificada en vivo (columna Centro en el editor
  de asientos, tab "Por centro de costo"). Caso `centros-costo`.

---

## H-181 · Contabilidad: export a Excel de los reportes
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (paso 5)
- **Exportar a Excel** los reportes contables (openpyxl, `reports/excel.py`): **Sumas y saldos** (por cuenta
  + totales), **Estados contables** (Situación patrimonial + Estado de resultados en **dos hojas**) y **Libro
  diario** (una fila por línea de asiento). Endpoints `/contabilidad/{sumas-y-saldos,estados-contables,
  libro-diario}/excel` (respetan el rango de fechas).
- **UI:** botón **"⬇ Excel"** en la pantalla de Estados contables que exporta la vista actual.
- **Verificado:** los 3 endpoints devuelven `.xlsx` válido (firma PK, content-type spreadsheetml); botón en
  pantalla. Suite backend **375 passed**; tsc + candado OK. Test: `test_reportes_excel`.
  Caso `reportes-contables-excel`.

---

## H-180 · Contabilidad: ejercicios contables (apertura / cierre / bloqueo de período)
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (paso 4)
- **Ejercicios (períodos fiscales):** nueva pantalla Contabilidad → Archivos → **Ejercicios contables**.
  Cada ejercicio es un rango de fechas con estado **abierto/cerrado**; no se permite **solapamiento**.
- **Cierre:** genera el **asiento de cierre** — refundición de resultados: cancela las cuentas de ingreso y
  egreso y lleva el neto a **"Resultado del ejercicio" (3.3)** del PN; guarda el resultado (ganancia/pérdida)
  y **bloquea el período** (crear/editar/publicar asientos con fecha en el rango → 422).
- **Reabrir:** elimina el asiento de cierre y libera el período.
- **Apertura:** genera el **asiento de apertura** del ejercicio con los saldos **patrimoniales**
  (activo/pasivo/PN) del período anterior (los resultados no se arrastran).
- **Modelo:** `EjercicioContable` (nombre, desde, hasta, estado, resultado, asiento_cierre/apertura). Tabla
  nueva (create_all). El bloqueo se aplica en `crear/editar/publicar` de asientos manuales.
- **Verificado en vivo:** alta del "Ejercicio 2026" (Abierto) con acciones Generar apertura / Cerrar. Test
  cubre cerrar (resultado + cuentas de resultado en cero), bloqueo (422 en período cerrado) y reabrir.
  Contabilidad **15 passed** (suite completa corriendo). tsc + candado OK. QA data limpia.
  Test: `test_ejercicio_cierre_y_bloqueo`. Caso `ejercicios-contables`.

---

## H-179 · Contabilidad: diarios + ciclo borrador → publicado en los asientos (estilo Odoo)
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (paso 3)
- **Diarios (Odoo: journals):** cada asiento pertenece a un **diario** (Caja / Banco / Varios). Tabla
  `diarios_contables` sembrada; selector en el alta y columna en la lista. Los automáticos
  (otorgamiento/cobranza) van al diario **Caja**.
- **Borrador → Publicado:** un asiento manual **nace en borrador** — editable y **no impacta el mayor**;
  recién al **Publicarlo** afecta sumas y saldos / estados (los reportes excluyen borradores, como Odoo con
  los *posted*). Un **publicado es inmutable** (no se edita ni borra: se corrige por **reversa**); un
  **borrador** se edita o se elimina. Los automáticos nacen publicados.
- **Modelo:** `Asiento` sumó `estado` (borrador|publicado) y `diario_codigo` (migración idempotente);
  nueva tabla `diarios_contables`. `balances_por_cuenta` filtra `estado != 'borrador'`.
- **UI:** pantalla "Asientos" con columnas Diario y Estado (Borrador/Publicado/Reversa/Reversado) y acciones
  por estado — borrador: Editar / Publicar / Eliminar; publicado: Reversar; siempre Ver detalle.
- **Verificado en vivo:** creado un borrador (diario Caja, balanceado) → publicado (con aviso in-app);
  editar/eliminar/reversar según estado. Tests contabilidad **14 passed** (suite completa corriendo). tsc +
  candado OK. QA data limpia. Tests: `test_borrador_no_impacta_mayor`, `test_asiento_manual_y_reversa`.
  Caso `asientos-diario-borrador`.

---

## H-178 · Contabilidad: parametrización contable (asignar el asiento de cada operación)
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** pregunta del usuario ("cómo asignar un
asiento contable a una operación")
- **Problema:** los códigos de cuenta de los asientos automáticos estaban **hardcodeados** en el motor
  (`_linea("1.2.01"…)`), así que "asignar un asiento a una operación" implicaba tocar código.
- **Solución — Parametrización contable:** tabla `ImputacionContable` = mapa **evento → cuenta del plan**,
  editable desde **Contabilidad → Parametrización contable**. Eventos: otorgamiento (créditos a cobrar /
  caja-desembolso) y cobranza (capital / interés / punitorio / seguro / gastos / IVA). Se siembra con los
  códigos actuales (comportamiento idéntico) y el motor lee la config vía `codigo_para(db, clave, default)`
  en `asiento_otorgamiento` y `asiento_cobranza`.
- **UI:** pantalla agrupada por operación; cada evento tiene un **selector de cuenta** (sólo imputables del
  plan) que guarda al cambiar. Cambiar la cuenta de un evento **redirige el asiento** sin tocar código.
- **Validación:** no se puede mapear a una cuenta de agrupación (no imputable) → 422.
- **Verificado en vivo:** pantalla con Otorgamiento/Cobranza y sus cuentas; test reasigna el haber del
  otorgamiento a Banco y el asiento nuevo imputa a 1.1.02. Tests contabilidad **13 passed** (full suite
  corriendo). tsc + candado OK. Test: `test_imputacion_contable_dirige_el_asiento`. Caso
  `parametrizacion-contable`.

---

## H-177 · Contabilidad: estados contables + sumas y saldos (desde los asientos)
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** roadmap contable (paso 2)
- **Nueva pantalla** Contabilidad → Reportes → **Estados contables**, con 3 vistas y filtro por rango de
  fechas, todo calculado desde los asientos (auto + manuales) agrupando por el **rubro** del plan:
  - **Sumas y saldos** (balance de comprobación): por cuenta con movimiento — Σdebe, Σhaber y saldo
    deudor/acreedor; totales que balancean (chip ✓).
  - **Situación patrimonial**: **Activo = Pasivo + PN** (el PN suma el **Resultado del ejercicio**); chip
    "✓ Balancea".
  - **Estado de resultados**: **Ingresos − Egresos = Resultado** (ganancia/pérdida).
- **Cuentas sin rubro (hallazgo real):** algunos asientos usan códigos **fuera del plan** (el componente
  contable de Configurar Créditos imputa a 1.1.05.01, 2.1.07…, que no están en el plan estándar). El reporte
  los agrupa en **"Otras cuentas (a clasificar)"** (del lado del activo) para que la ecuación cierre y se vea
  qué falta clasificar. → **Resuelto:** se agregaron al plan estándar `1.1.05 Préstamos` / `1.1.05.01
  Préstamos otorgados` (activo) y `2.1.07 IVA débito fiscal (Créditos)` (pasivo); tras recargar el estándar,
  el reporte clasifica esas cuentas en su rubro y "Otras" queda **vacío** — la situación balancea limpia
  ($366.424,59 = $366.424,59) sin bucket.
- **Verificado en vivo:** con asientos de prueba, Situación **balancea** ($591.766,80 = $591.766,80),
  Resultados muestra ingresos, y 'otras' surge con las cuentas pp. Suite backend (nuevo
  `test_estados_contables`); tsc + candado OK. QA data limpia. Caso `estados-contables`.

---

## H-176 · Contabilidad: asientos manuales (doble partida + reversa) · fuera los diálogos nativos
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad / UX · **Alcance:** pedido del usuario
- **Sin diálogos nativos (primero):** el usuario marcó que las cajitas grises del navegador
  (`window.confirm/alert/prompt` — "localhost:5173 says…") **no van**; van los diálogos in-app
  (`confirmar`/`avisar`/`pedirTexto` de `src/ui/dialog.tsx`). Plan de cuentas usaba `window.confirm` para
  "descartar cambios" → se cambió por `confirmar({ danger:true })`. Se **sumó como Principio de diseño** y
  con **candado nuevo** en `check-diseno.mjs` (falla si una página usa window.confirm/alert/prompt).
- **Asientos manuales (contabilidad general):** nueva pantalla **Contabilidad → Asientos manuales**. Alta
  por **doble partida** con grilla de líneas (cuenta del plan · debe · haber), **balance en vivo**
  (Debe/Haber + pill "✓ Balanceado" / descuadre) y validaciones en backend: ≥2 líneas, cuentas existentes e
  **imputables**, sin negativos, línea es debe **o** haber, y **Σdebe = Σhaber ≠ 0**. Correlativo por año y
  auditoría (usuario).
- **Reversa:** genera el **contra-asiento** (debe/haber invertidos), marca el original *reversado* y **no
  borra** (event-sourcing / "la reversa contra-asienta, no elimina"). Los automáticos siguen en el Libro
  diario; esta pantalla lista sólo manuales + reversas.
- **Modelo:** `Asiento` sumó `numero, reversado, reversa_de, usuario` (migración idempotente en Postgres).
- **Verificado en vivo:** alta balanceada (Caja 5.000 / Banco 5.000 → "✓ Balanceado" → N° 1 Normal) y
  reversa (N° 2, con aviso in-app). Suite backend **370 passed**; tsc + candado OK. QA data limpia.
  Test: `test_asiento_manual_y_reversa`. Casos `asientos-manuales`, `sin-dialogos-nativos`.

---

## H-175 · Contabilidad: cargar plan de cuentas estándar + baja de "Plan de cuentas 2"
**Fecha:** 2026-09-16 · **Módulo:** Contabilidad · **Alcance:** pedido del usuario
- **Cargar plan estándar:** botón **"＋ Cargar plan estándar"** que puebla el árbol con un chart contable
  completo (Activo / Pasivo / Patrimonio neto / Ingresos / Egresos, con corrientes/no corrientes y
  subcuentas típicas, ~40 cuentas). **Idempotente** (no pisa ni duplica), grupos no imputables y saldo
  normal por rubro; incluye los códigos que usa el motor de asientos. Así la pantalla queda poblada como el
  mock sin cargar rama por rama. (Servicio `cargar_plan_estandar` + endpoint `/plan-cuentas/cargar-estandar`.)
- **Baja de "Plan de cuentas 2":** se eliminó la pantalla anterior (grilla-árbol simple) por redundante —
  menú, ruta, import y archivo `PlanCuentas2.tsx`.
- **Insumo (artículo de Fierro, soporte):** relevé funciones para sumar a Contabilidad más adelante —
  **múltiples planes** por empresa (pestañas reales), **importar/exportar** el plan, **asientos manuales**
  (recién ahí cobra sentido el flag *Manual* de la cuenta), **mayor por cuenta** por período y **saldos en
  moneda alternativa**. Próximo sugerido: asientos manuales (partida doble).
- **Verificado en vivo:** cargado el estándar en la DB (33 agregadas → árbol Activo/Pasivo/PN/Ingresos/
  Egresos nombrado y coloreado por rubro). Suite backend **369 passed**; tsc + candado OK.
  Test: `test_cargar_plan_estandar`. Caso `plan-cuentas-estandar`.

---

## H-174 · Contabilidad: Plan de cuentas moderno (master-detail) + "Plan de cuentas 2"
**Fecha:** 2026-09-15 · **Módulo:** Contabilidad · **Alcance:** pedido del usuario (mock aprobado)
- **Contexto:** se diseñó primero un **mock** (artifact) de la pantalla al estilo de sistemas contables
  (árbol + "Datos de la cuenta"); con el OK del usuario se implementó en la app.
- **Nueva "Plan de cuentas" (moderna)** — master-detail: **árbol jerárquico** plegable a la izquierda
  (con puntos de color por rubro, buscador y barra de alta/subcuenta/borrado) + panel **"Datos de la
  cuenta"** a la derecha: código, alias, nombre, descripción, **Rubro** (activo/pasivo/patrimonio/
  ingreso/egreso, chip de color) y **Tipo** (Caja/Banco/Cliente…), **Moneda**, **Saldo normal**
  (deudor/acreedor, *segmented*), toggles **Imputable** / **Carga manual**, y **Entidades relacionadas**
  (tipo/entidad, agregar/quitar). Breadcrumb de la ruta, guardar/descartar, y creación de cuenta/subcuenta
  con código sugerido.
- **Modelo extendido:** `CuentaContable` sumó `descripcion, alias, moneda, clasificacion, saldo_normal,
  imputable, manual, entidades (JSON)`. Migración idempotente en Postgres (ALTER … IF NOT EXISTS).
- **"Plan de cuentas 2":** la versión anterior (grilla-árbol simple, H-173) se conservó y se renombró en el
  menú a **Plan de cuentas 2** (ambas opciones con badge `new`).
- **Verificado en vivo:** master-detail carga la cuenta al seleccionarla, edita y **persiste** (probado el
  guardado de descripción → DB). Suite backend **368 passed**; tsc + candado OK (UI custom scopeada `.pcm-*`,
  excepción de diseño declarada). Test: `test_plan_cuentas_datos_completos`. Caso `plan-cuentas-moderno`.
- **Fidelidad al mock (ajuste posterior):** se alineó la pantalla al mock aprobado — pestañas
  `Planes de cuentas` / `Predeterminado (1)`, barra **"Editar"** con **íconos SVG** (hermana / subcuenta /
  eliminar / duplicar), **conectores** de árbol (líneas punteadas padre→hijo), **toggles** livianos (no
  encajonados) y **paleta por rubro** (activo verde, pasivo ámbar, patrimonio índigo, resultados rosa) vía
  tokens de tema `.pcm{--r-*}` en `styles.css` (sin hex en la página, candado OK). Las pestañas son visuales
  por ahora (soporte real de múltiples planes = feature aparte). Nota: hubo que **reiniciar el dev server**
  de Vite porque quedó sirviendo un módulo viejo (HMR trabado) que tiraba `ramas is not defined`.
- **Grupos nombrables + "agregar" repensado (ajuste posterior 2):** (1) las ramas de agrupación (nodos del
  árbol sin cuenta propia) ahora se pueden **nombrar** — al seleccionarlas se abre el panel en modo
  "Nombrar rama" (código fijo, imputable off) y al guardar se crea la cuenta (ej. la raíz "1" → "ACTIVO").
  (2) El alta se hace desde un **＋ que aparece al pasar el mouse** sobre cualquier fila (agregar subcuenta)
  y la cuenta nueva se muestra como **fila fantasma** en el árbol mientras se completa, para ver dónde
  queda; se guarda o se descarta. (3) Chevrons **planos** (›/˅ sin recuadro), raíces en **negrita
  mayúscula**, Duplicar/Eliminar movidos al pie del panel (contextuales). Verificado en vivo (nombrar la
  raíz "ACTIVO"; fantasma al agregar 1.2.01.01) y limpieza de datos QA.

---

## H-173 · Contabilidad: Plan de cuentas (ABM editable, plantilla base configurable)
**Fecha:** 2026-09-15 · **Módulo:** Contabilidad · **Alcance:** pedido del usuario
- **Nueva opción** Contabilidad → Archivos → **Plan de cuentas** (`new`). Se presenta como **árbol
  jerárquico por código** (1 → 1.1 → 1.1.01), **indentado y plegable**: cada rama se expande/colapsa, con
  Expandir/Colapsar todo. Las ramas intermedias que no existen como cuenta propia (p. ej. "1", "2.1") se
  muestran como nodos **"grupo"** sintéticos. Alta/edición en modal; se puede agregar **subcuenta** desde
  cualquier nodo (código del padre precargado). (Excepción de diseño declarada: `DataTable` es plana y no
  modela la jerarquía; grilla-árbol custom scopeada `.plc-tree`.)
- **Parte de la plantilla base** — las cuentas que usa el motor de asientos (Caja, Banco, Créditos a cobrar,
  IVA débito fiscal, Intereses, Seguros, Gastos administrativos). Se pueden **crear** cuentas propias,
  **renombrar** y **reclasificar** (activo/pasivo/patrimonio/ingreso/egreso).
- **Protecciones:** código único (409 si repite); las cuentas **base** del sistema no se borran ni cambian
  de código; una cuenta **con asientos** tampoco se borra (422). Botón **"Restaurar plantilla base"**
  (idempotente) agrega las cuentas base que falten sin pisar ni duplicar.
- **Coherencia con los asientos:** `_linea` ahora resuelve el nombre de la cuenta **desde el plan en la DB**
  (con la base como fallback), así renombrar una cuenta se refleja en los asientos **nuevos**.
- **Verificado:** ABM en vivo (lista base, modal flotante de alta) y suite. Tests:
  `test_plan_cuentas_abm`, `test_plan_cuentas_refleja_nombre_en_asientos`. Caso `plan-cuentas-abm`.

---

## H-172 · Créditos: revisión para liquidar sin desbordes + cronograma desplegable
**Fecha:** 2026-09-15 · **Módulo:** Créditos / UX · **Alcance:** pedido del usuario
- **Síntoma:** en el detalle de la solicitud, el valor largo del **CBU** se salía de la pantalla y la
  "Revisión para liquidar" se veía apretada.
- **Fix:** cada ítem de la revisión se **apila** (etiqueta chica arriba, valor abajo) y los valores largos
  hacen **wrap** dentro de su columna (`overflow-wrap:anywhere`), así el CBU (y cualquier dato) ya no
  desborda. El grid del panel también protege sus valores contra desborde.
- **Cronograma desplegable:** "Cronograma estimado" pasó a ser un **toggle plegable** (plegado por
  defecto, con contador de cuotas) para no alargar el panel; se abre cuando el asesor lo necesita.
- **Verificado en vivo:** CBU completo dentro de su columna; cronograma abre/cierra. Caso `revision-liquidar-ux`.

---

## H-171 · UX: el detalle de un registro debe ser FLOTANTE (no un panel inline)
**Fecha:** 2026-09-15 · **Módulo:** UX / Diseño (varias pantallas) · **Alcance:** pedido del usuario
- **Pedido:** "la pantalla cuando veo la solicitud debería ser flotante, eso revisalo en toda la aplicación".
- **Solicitudes de crédito** ([SolicitudesCredito.tsx](capresca-nuevo/frontend/src/pages/creditos/SolicitudesCredito.tsx)):
  el detalle dejó de ser un panel inline debajo de la tabla. Al clickear la fila abre **un único panel
  flotante** (modal con scrim) que reúne todo — datos, cronograma, documentos, revisión para liquidar,
  observación del asesor y las acciones (enviar/aprobar/rechazar/anular/originar + alta/vincular cliente).
  Se eliminó el botón "Ver detalle" separado (el panel flotante YA es el detalle completo).
- **Auditoría del resto de la app** (subagente, ~100 pantallas): la mayoría de las vistas de detalle ya
  eran flotantes (drawer/modal con scrim: Clientes, Configurar Créditos, Resoluciones, Modelos,
  Grupos/Perfiles/Usuarios, Auditoría de cambios…) o son reportes/dashboards/master-detail por diseño.
  **Casos inline corregidos** además de Solicitudes:
  - **Liquidación por lote** ([LiquidacionLote.tsx](capresca-nuevo/frontend/src/pages/creditos/LiquidacionLote.tsx)):
    "Ver contratos" abría una card inline → ahora es **modal** (`.liq-*`).
  - **Solicitudes (legacy)** ([Solicitudes.tsx](capresca-nuevo/frontend/src/pages/Solicitudes.tsx)):
    el detalle + el plan de cuotas resultante eran cards inline → ahora **modal** único (`.sold-*`).
- **Dejados como están (borderline, son drill-downs de reporte, no vistas de registro):** Balance/Mayor
  (cuenta → su mayor) y Fondo de garantía (agencia → desglose por juego) — su despliegue inline debajo de la
  tabla es el patrón esperado de un reporte; se documentan por si se quieren unificar más adelante.
- **Verificado en vivo:** el detalle de Solicitudes abre flotante sobre un fondo atenuado y cierra limpio
  (✕ / click afuera), sin empujar la página. tsc + candado de diseño OK (overlays scopeados por pantalla).

---

## H-170 · Solicitudes de crédito: revisión completa, alta de cliente al maestro, observación y Rechazar vs Anular
**Fecha:** 2026-09-15 · **Módulo:** Créditos / Solicitudes · **Alcance:** pedido del usuario (captura del inbox)
- **Rechazar vs Anular (aclarado + tooltips):** **Rechazar** = decisión crediticia **negativa** (se evaluó
  y se deniega) — sólo desde `EN_EVALUACION`, requiere **rol aprobador** y **motivo**, deja `RECHAZADA`.
  **Anular** = baja **administrativa** del trámite (error de carga, duplicada, el cliente desistió) —
  desde cualquier estado salvo `ORIGINADA`, sólo permiso de **edición**, motivo opcional. Los botones ahora
  llevan `title` con esa diferencia.
- **"Ver detalle" (aprobar/originar con todo a la vista):** botón que abre un modal con la revisión
  completa — datos de la solicitud, evaluación, **cronograma completo** (calculado con el mismo motor que la
  simulación/originación, vía `/productos/{id}/simular-preview`), documentos del solicitante y la revisión
  para liquidar. Desde el modal se Aprueba / Rechaza / Origina.
- **Observación del asesor (opcional):** campo en el modal que queda registrado en
  `datos_adicionales.obs_revision` (para **rechazar** funciona como el motivo). Al **originar**, la
  observación viaja al contrato (`datos_adicionales.observaciones`).
- **Alta de cliente = ir a Clientes → Maestro (decisión del usuario):** "Dar de alta en maestro" dejó de
  usar un mini-form; ahora **navega** al Maestro con el alta **completa** precargada (apellido/nombre, DNI,
  CUIL declarados) y un aviso; al **guardar**, vuelve a la solicitud y **vincula** el cliente recién creado
  (round-trip por query params + auto-vinculación). Se agregó **"Vincular cliente"** (typeahead) para
  enganchar uno que ya existe. Backend: `promover-cliente` acepta `cliente_id` (vincular existente) y el ID
  del cliente se autogenera (CL-…, H-169).
- **Verificado en vivo:** modal con cronograma y observación OK; navegación a Maestro con form completo
  precargado + aviso de retorno OK; tooltips OK. Suite backend **365 passed**; tsc + candado OK.
  Tests: `test_promover_vincular_cliente_existente`, `test_estado_guarda_observacion`. Caso `sol-revision-detalle`.

---

## H-169 · Clientes: el ID del maestro debe ser autogenerado (no el CUIL ni un N° de solicitud)
**Fecha:** 2026-09-15 · **Módulo:** Clientes · **Alcance:** reporte del usuario (captura del maestro)
- **Síntoma:** en el Maestro de clientes, la columna **ID** mostraba el **CUIT** en unas filas y un
  **N° de solicitud** ("SOL-2026-00003") en otra. El usuario pidió que el ID sea **autogenerado**.
- **Causa:** el `id_cliente` no tenía generación propia. Al **promover** una solicitud express al maestro
  (`/solicitudes/{id}/promover-cliente`) se hacía `idc = data.id_cliente or (cuil or _numero(db))` → si no
  había CUIL usaba el número **SOL-...** de la solicitud, y si había, el **CUIL**. El alta por ABM mandaba
  `id_cliente:""`. Los clientes demo del seed tenían códigos CUIL-like hardcodeados.
- **Fix:** el `id_cliente` se **autogenera del PK** (surrogate) con formato **`CL-000123`** (helper
  `app/core/codigos.py`: `codigo_cliente(pk)` + `codigo_cliente_provisorio()` como placeholder único
  pre-flush, dado que la columna es NOT NULL + unique). Se aplica en los dos caminos de alta
  (`clientes.crear` y `solicitudes.promover_cliente`) y en el seed. **Un código explícito sólo se respeta
  si viene de la migración/ETL** (CIDCLIENTE legacy numérico, que es un dato real del negocio y se usa en
  los joins del ETL). Así el ID nunca es el CUIL ni un SOL-.
- **Datos:** se normalizaron los 3 clientes demo existentes (CL-000001/2/5). No hay clientes migrados por
  ETL en esta base (conservarían su CIDCLIENTE).
- **Verificado:** suite backend; UI muestra CL-... en la columna ID. Tests:
  `test_id_cliente_autogenerado`, `test_promover_cliente_express_al_maestro`. Caso `cliente-id-autogenerado`.
- **Auditoría de toda la app (a pedido):** se revisó CADA columna string única (código/número) del modelo
  y su asignación en el alta (`app/api/`, `app/services/`, `seed.py`; ETL excluido a propósito). **No hay
  otro caso del bug**: el `id_cliente` era el único que copiaba un dato con significado (CUIL / N° de
  solicitud). El resto de los códigos/números generados por el sistema ya pasa por el generador correcto
  (`crear_con_numero_unico` + `_proximo_*` / `_codigo_libre`): `PPSolicitud.numero`,
  `PPContrato.numero_contrato`, `PPProducto.codigo` (el clonar NO copia el código origen, genera uno
  nuevo), y los `numero` correlativos de resoluciones, OP, recibos, pólizas, turnos. Los demás únicos son
  identificadores **tipeados por humano / externos** (CUIL, código de impuesto/índice, código de
  perfil/grupo, cuenta contable, clave de parámetro, username, ISO de moneda) — correctamente NO se
  autogeneran.
- **Endurecimiento derivado (unicidad concurrente):** `crear_expediente` usaba sólo check-then-insert; el
  N° de expediente es tipeado por humano (correcto), pero dos altas concurrentes con el mismo número caían
  en `IntegrityError` (500) en vez de un 409 limpio. Se agregó el catch → 409 con la CONSTRAINT como
  árbitro (mismo criterio que el CUIL, H-154). `test_numero_expediente_unico` sigue verde.
- **Nota (footgun latente, sin cambio):** `Perfil.codigo` tiene `default=""` en el modelo; hoy es inocuo
  (el alta exige código no vacío y chequea duplicado), pero convendría quitar ese default para que un alta
  sin código falle fuerte en vez de colisionar en `""`.

---

## H-168 · Despacho: editar un borrador de resolución/disposición
**Fecha:** 2026-09-15 · **Módulo:** Despacho · **Alcance:** completitud de la ABM (mismo editor)
- **Gap:** la pantalla de Resoluciones permitía **crear** y **ver**, pero no **editar** — ni siquiera un
  borrador. Se completó el ABM con edición, usando el mismo editor mini-Word (`RichText`).
- **Backend `PUT /api/despacho/resoluciones/{id}`** (`svc.editar_resolucion`): edita modelo (→ motivo),
  texto (HTML), importe, exp./nota origen y **reemplaza** la grilla de beneficiarios. **No** cambia
  tipo/número/año (rompería la serie del correlativo, única por tipo+año). Recalcula `asunto` del texto.
- **Inmutabilidad del acto emitido:** un instrumento **oficial** (firmado o con Nº Real) o **anulado** no
  se puede editar → el PUT devuelve **422**. Coherente con "no re-firmar" (H-164) y con los Principios
  (event ya emitido no se altera; se corrige por otro acto).
- **UI:** acción **"Editar"** (grilla y detalle) visible **sólo** en borradores (`estado≠F`, sin Nº Real,
  no anulada). El modal reusa `EditorResolucion` en modo edición: tipo y N° correlativo de sólo lectura,
  eyebrow "EDITAR BORRADOR · N° x/aaaa", botón "Guardar cambios". El modelo guardado (por código) se
  resuelve al id único para preseleccionar el combo.
- **Verificado en vivo:** creado un borrador (modelo "AYUDAS SOCIALES (SALUD)", plantilla cargada con
  **negritas** preservadas), editado importe ($15.000) y origen (E20 77/2026) → el detalle refleja los
  cambios y sigue Borrador; en resoluciones **oficiales** migradas el menú NO muestra "Editar". Modelo de
  prueba borrado. Suite backend **362 passed**; tsc + candado OK.
  Test: `test_resolucion_editar_borrador`. Caso `resolucion-editar-borrador`.

---

## H-167 · Despacho: ABM de Modelos de resoluciones (crear/editar con el editor mini-Word)
**Fecha:** 2026-09-14 · **Módulo:** Despacho · **Alcance:** pedido del usuario
- **Pedido:** "En la opción de modelos de resoluciones, se deben poder editar y crear nueva, y la idea es
  usar el mismo editor que creaste."
- **ABM completa:** la pantalla de Modelos dejó de ser sólo lectura. Layout de ABM estándar (header con
  **＋ Nuevo modelo** → card con buscador → `DataTable` → modal de alta/edición). La acción por fila
  **"Editar plantilla"** abre el mismo modal.
- **Editor compartido:** se reutiliza el **mismo** editor mini-Word de las resoluciones extrayéndolo a un
  componente `src/components/RichText.tsx` (barra Título/Subtítulo/párrafo, negrita/cursiva/subrayado,
  lista, alineación; guarda HTML). Tanto Resoluciones como Modelos lo importan (se eliminó la copia local
  y su CSS `.rt*` de Resoluciones).
- **Backend:** `POST /api/despacho/modelos` (código autoasignado = `MAX(codigo)+1`, tipo_res 3 si DIS / 1
  si RES) y `PUT /api/despacho/modelos/{id}` (descripción, tipo, seguros, plantilla). `tiene_plantilla` se
  recalcula según haya cuerpo. La descripción es **obligatoria**: el schema `ModeloResolucionIn` ahora la
  valida contra vacío-al-recortar (422), no sólo `min_length` del string crudo (`"   "` ya no pasaba a un
  modelo con descripción vacía).
- **Bug corregido — "no se ve lo que está guardado":** al abrir *Editar*, la plantilla guardada no
  aparecía en el editor (mostraba el placeholder), aunque el backend la devolvía completa (p.ej. modelo
  "1PRESTAMO JUBILADO": 3295 car. de HTML). Causa: `RichText` inicializaba su ref de control con
  `useRef(value)`; como el editor se **monta recién después** de cargar la plantilla (gate "Cargando…"),
  ya nacía con el HTML como `value` inicial → el guard `value !== last.current` era falso en el primer
  render y nunca volcaba el `innerHTML` en el `contentEditable`. Fix: la ref arranca en un centinela
  (`null`) para que el primer render **siempre** vuelque el contenido. (También afecta positivamente a
  editar resoluciones existentes, que usan el mismo componente.) Verificado en vivo: el editor muestra las
  3295 car. con **negritas** y párrafos **justificados** preservados.
- **Verificado:** smoke-test en vivo (alta → id/código nuevo, `tiene_plantilla` true; edición 200 con
  descripción/tipo/plantilla nuevos) y limpieza del modelo de prueba (vuelve a 338 reales). Modal renderiza
  con el `RichText` y ahora **muestra la plantilla guardada**. tsc + candado de diseño OK.
  Test: `test_modelo_abm_crear_editar`. Caso `modelos-resolucion-abm`. Menú marcado `new`.

---

## H-166 · Despacho: editor mini-Word, export a Word corregido, modelos por id
**Fecha:** 2026-09-14 · **Módulo:** Despacho · **Alcance:** pedido del usuario
- **Editor mini-Word:** el "Texto del instrumento legal" pasó de textarea a un editor rico
  (`RichText`, contentEditable + barra: **Título/Subtítulo/párrafo**, negrita/cursiva/subrayado, lista,
  alineación) que guarda **HTML**. Al elegir un modelo se carga su plantilla. El detalle muestra el HTML
  renderizado.
- **Formato preservado en la migración (mejora sobre H-165):** el RTF ya no se aplana a texto plano; se
  agregó `rtf_a_html` (mismo tokenizer, ahora rastrea negrita/cursiva/subrayado y alineación por párrafo →
  `<p>`, `<b>`, `<i>`, `<u>`, `text-align`). Se re-migró: los textos de resoluciones (41.300) y las
  plantillas de modelos conservan **negritas, cursivas y párrafos centrados** (títulos). El export a Word
  respeta la alineación (`text-align` → párrafo centrado/justificado).
- **Export a Word corregido:** (1) nombre institucional **correcto** — "CAJA DE CRÉDITO Y PRESTACIONES
  PROVINCIAL — Ca.Pre.S.Ca." (antes decía "Previsión Popular"); (2) **un solo título** limpio (tipo + N°,
  usa el real si está) con el **motivo como subtítulo** — antes ponía un "ASUNTO:" con el texto recortado y
  duplicaba encabezados; (3) **renderiza el HTML** del editor (h1-h3 → títulos centrados, b/i/u → runs,
  ul/li → viñetas) vía un `HTMLParser`→docx; si el texto es plano (migrado) lo rinde por líneas.
- **Modelos por id:** el `COD_MOD` legacy se repite entre tipos → la lista de Modelos y el combo "Modelo a
  utilizar" ahora usan el **id único** (rowKey/option/value), y crear-resolución + cargar-plantilla se
  resuelven por id (sin ambigüedad). El endpoint `/modelos` devuelve `id`; `/modelos/{id}` es por PK.
  (La pantalla de Modelos ya mostraba los 338 tras la migración de H-164; lo que faltaba era el id.)
- **Verificado:** editor en vivo (escribir + "Título" centra y agranda); export Word inspeccionado (nombre
  correcto, sin nombre viejo, HTML rendido); modelo por id + alta con modelo_id OK. tsc + candado OK.
  Tests: `test_resolucion_word_nombre_y_html` (+ los de H-164). Caso `resolucion-editor-word`.

---

## H-165 · Bug del lector DBF: los campos memo (.fpt) migraban vacíos (RTF)
**Fecha:** 2026-09-14 · **Módulo:** ETL / Migradores · **Alcance:** bug encontrado al migrar Despacho
- **Síntoma:** las resoluciones migraban **sin texto** ("no hay texto"), pese a que el `.FPT` (memos) existe
  (1,6 GB).
- **Causa:** `DbfReader` resolvía el archivo de memos recortando **1 carácter** del path
  (`resoluciones.dbf` → buscaba `resoluciones.dbfpt`), que nunca existe → `self._fpt=None` → **todos** los
  campos memo (M) devolvían "". Afectaba a cualquier migrador con memos, no sólo Despacho.
- **Fix:** resolver el `.fpt` por **nombre base** (`os.path.splitext` + `.fpt/.FPT/.dbt`). Además, los memos
  son **RTF**: se agregó `app/etl/rtf.py` (`rtf_a_texto`, algoritmo clásico *striprtf* — grupos anidados,
  destinos ignorables, `\uN`, `\'xx`) y el migrador de despacho pasa TEXTO y las plantillas de modelos por él.
- **Verificado:** re-migración → **41.300/41.396** resoluciones con texto plano legible (VISTO/CONSIDERANDO/
  RESUELVE) y **336/338** modelos con plantilla; en vivo, el detalle de la res. 1221/2025 muestra el cuerpo
  completo. Caso `dbf-memo-fpt-fix`.

---

## H-164 · Despacho: pantalla de Resolución igual al legacy + migración de los DBF reales
**Fecha:** 2026-09-14 · **Módulo:** Despacho · **Alcance:** pedido del usuario (replicar pantallas VFP + migrar)
- **Fuente legacy (verificada en código + DBF):** form `120050000reso_disp.scx` (formset: alta, "Carga Nº Real",
  beneficiarios, RichText). Campos de `Despacho/resoluciones.dbf`: NRO_RES (correlativo), FEC_RES, TIPO_RES,
  NRO_REAL, FEC_REAL, ID_TRAMITE/ID_LETRA/ID_NRO/ID_ANO (Exp./Nota origen), IMPORTE, COD_MOT, TEXTO(RTF),
  DISPOSICIO, LANULADA. `beneficiarios.dbf`: TIPO_DOC/NRO_DOC/NOMBRE/TIPO_BENE ligados por (NRO_RES,FEC_RES,
  TIPO_RES). `rtf.dbf` (modelos): COD_MOD/DES_MOD/MODELO(RTF). **Clave:** no hay tabla de motivos — el
  **motivo es la descripción del MODELO** (COD_MOT == rtf.COD_MOD), y elegir el modelo copia su RTF al texto.
  Numeración: correlativo por año+tipo; N° Real = MAX(nro_real)+1 por tipo y año, se carga después.
- **Modelo de datos:** `Resolucion` sumó numero_real, fecha_real, motivo_cod, motivo, importe, modelo_codigo,
  origen, nro_op, anulada; nueva tabla `ResolucionBeneficiario`; `ModeloResolucion` sumó `plantilla` (texto
  base). Migración de columnas en el arranque (`_migrar_iam`, ALTER idempotente).
- **Migrador (`etl/cargar_despacho`):** carga modelos (con plantilla), resoluciones (todos los campos, tipo
  RES/DIS, motivo resuelto desde el modelo) y beneficiarios (linkeados por nro+año+tipo). Registrado en
  `etl/registro` (clave 'despacho', re-ejecutable con reset; USOS_MENU + DBF list actualizados).
  **Migrado y verificado contra el backup real:** 338 modelos · 41.396 resoluciones · 127.875 beneficiarios
  (p.ej. res. 1010/2020 "INCAPACIDAD EXTRAJUDICIAL" $8.756.000 con 456 beneficiarios).
- **Backend:** `crear_resolucion` toma modelo/importe/origen/beneficiarios (el modelo define el motivo y, si el
  texto viene vacío, carga su plantilla); nuevo `asignar_numero_real` (endpoint `POST /resoluciones/{id}/
  numero-real`); `GET /resoluciones/{id}` con beneficiarios; `GET /modelos/{cod}` con plantilla.
- **Frontend (`despacho/Resoluciones.tsx`, rehecho):** lista `DataTable` (tipo, N° correlativo, N° real,
  fecha, motivo, importe, estado) con filtros tipo/año; editor modal **igual al legacy** (Nº Correlativo "se
  asigna al grabar", Nº Real "se carga luego", Modelo→Motivo, Importe, Exp./Nota origen, Texto del instrumento
  legal, grilla de Beneficiarios) con validación (importe ≥0, nombre de beneficiario requerido, modelo o texto);
  detalle con beneficiarios y "Cargar Nº Real". **Badge `new`** en el menú (Despacho → Resoluciones).
- **Verificado:** pantalla y editor renderizan con los 41K migrados; elegir modelo resuelve el motivo (ACTA
  VOLANTE); alta con modelo+beneficiarios+importe y carga de N° Real OK (test + API en vivo). tsc + candado OK.
  Caso `despacho-resolucion-legacy`.
- **Pendiente menor:** "Exp./Nota origen" es texto libre (el legacy usa dropdown de `Mesa/tipotram.dbf` +
  lookup de trámite); se puede enriquecer si se necesita.

---

## H-163 · Portal: la documentación se pide sólo en "Tus datos", no en "Mis solicitudes"
**Fecha:** 2026-09-10 · **Módulo:** Portal ciudadano · **Alcance:** pedido del usuario
- El pedido/carga de documentación va **sólo en el paso de datos** de la solicitud (`DocsPicker`). Se **quitó**
  la sección de documentos del detalle de "Mis solicitudes" (se eliminó el componente `DocumentosSolicitud` y
  su uso en el modal), consistente con la decisión previa H-131 (no gestionar adjuntos post-envío desde el
  portal). El backend de documentos sigue intacto y probado; el asesor los ve/descarga en el backoffice.
- **Verificado en vivo:** el detalle de una solicitud ya **no** muestra "Documentación"; el paso "Tus datos"
  sí. tsc portal OK. (Confirmado además con una solicitud real del propio usuario — "HERNAN, CARRASCAL" — que
  validó el nuevo flujo de identidad declarada de H-162.)

---

## H-162 · Portal: el ciudadano declara su identidad + documentos en "Tus datos"
**Fecha:** 2026-09-10 · **Módulo:** Portal ciudadano · **Alcance:** pedido del usuario
- **Aclaración de negocio:** Mi Catamarca (OIDC) **sólo confirma que la persona existe**, no devuelve su
  perfil. El flujo asumía que traía nombre/DNI (y un botón "Traer mis datos" simulaba haberes).
- **Cambio (frontend):** en el paso **Tus datos** el ciudadano ahora **carga a mano** Apellido, Nombre y DNI
  (obligatorios, con asterisco; DNI 7-8 díg.), además de situación/edad/antigüedad/sueldo. Se **eliminó** el
  botón "Traer mis datos de Mi Catamarca" y la llamada a `/haberes`. La **documentación** (DNI/recibo) se
  adjunta en **el mismo paso** (`DocsPicker`, selección en el cliente) y se **sube al enviar** la solicitud
  (best-effort; si algún archivo falla, se avisa y se puede subir desde el detalle). La confirmación muestra
  Solicitante + DNI. El borrador persiste los datos nuevos.
- **Cambio (backend):** `PortalSolicitudIn` suma `apellido`, `nombre`, `dni`; `enviar_solicitud` los **exige y
  normaliza** (422 si faltan o el DNI no tiene 7-8 díg.) y arma `cliente_datos.apellido_nombre = "Apellido,
  Nombre"` con el DNI declarado (antes tomaba la identidad del token OIDC).
- **Verificado:** `test_enviar_exige_identidad_declarada` (422 sin identidad / DNI inválido; 201 con
  "GOMEZ, ANA" + DNI normalizado). En vivo: el paso Tus datos muestra los campos + la sección Documentación,
  y con datos válidos avanza a Simulación. tsc portal + test_portal OK. Datos de prueba limpiados.
- **Controles de Versión:** caso `portal-identidad-declarada`.

---

## H-161 · Ícono de notificaciones más moderno (backoffice + portal)
**Fecha:** 2026-09-10 · **Módulo:** UX transversal · **Alcance:** pedido del usuario
- **Backoffice:** el bell de `Icon.tsx` pasó del path viejo al **bell redondeado estilo Lucide nuevo**; el
  badge se rehizo como pill con anillo del fondo (`--ground`), color `--crit` (antes hex fijo) y **pulso
  sutil**; micro-rotación del bell al hover. Respeta `prefers-reduced-motion`.
- **Portal:** se reemplazó el emoji `🔔` por el **mismo SVG** (currentColor), con hover y el mismo badge con
  pulso. Tokens de tema con fallback; sin romper el modo claro/oscuro.
- **Verificado:** ambos renderizan (captura del topbar del backoffice con el bell nuevo + badge). tsc de ambos
  apps + candado OK. Caso `icono-notificaciones-moderno`.

---

## H-160 · Portal: UI de documentación de la solicitud
**Fecha:** 2026-09-10 · **Módulo:** Portal ciudadano · **Alcance:** backlog de H-153
- **Problema:** el backend de documentos estaba completo (subir/listar/descargar/borrar, con validación de
  formato/tamaño y owner-scoping) y probado, pero **no existía la pantalla** en el portal (helpers de `api.ts`
  sin uso). El ciudadano no podía adjuntar su DNI ni el recibo.
- **Ahora:** en el detalle de la solicitud hay una sección **Documentación** (`DocumentosSolicitud`): lista de
  adjuntos con tipo/nombre/tamaño e ícono IMG/PDF, botón **Ver** (abre el archivo), **quitar** con confirmación
  en dos pasos, y **adjuntar** eligiendo el tipo (DNI frente/dorso, recibo, otro). Límites reflejados en la UI:
  JPG/PNG/PDF, máx 5 MB, hasta 10; sólo mientras la solicitud está EN_EVALUACION/BORRADOR (`puede_subir`).
- **Verificado en vivo:** con una solicitud de prueba en el portal — la sección renderiza; subir un archivo por
  API lo muestra como tarjeta ("DNI (frente) · dni.png · 67 B", contador 1/10) con Ver y ✕. tsc portal OK.
  Datos de prueba (solicitud, documento, auditoría) **limpiados**. Caso `portal-docs-ui`.

---

## H-159 · Portal: token vencido a mitad de sesión expulsa a Login
**Fecha:** 2026-09-10 · **Módulo:** Portal ciudadano · **Alcance:** backlog de H-153 (tanda 3)
- **Antes:** un 401 (token vencido) limpiaba el token y tiraba error, pero el estado `sesion` sólo se evaluaba
  al montar la app → la UI quedaba rota hasta recargar.
- **Ahora:** `api.ts` (`req`/`upload`/`abrirArchivo`) en un 401 limpia el token y dispara el evento global
  `portal:sesion-expirada`; `App.tsx` lo escucha y vuelve a `<Login/>` sin recargar. Sin refresh token todavía
  (fuera de alcance), pero ya no queda una sesión zombi. Caso `portal-token-expira-expulsa`.

---

## H-158 · Portal: state OIDC de un solo uso (anti-replay)
**Fecha:** 2026-09-10 · **Módulo:** Portal / Seguridad · **Alcance:** backlog de H-153 (tanda 3)
- **Antes:** el `state` iba firmado (CSRF stateless) pero el `nonce` nunca se persistía/consumía → un state
  válido no expirado podía reusarse dentro de su ventana de 10 min.
- **Ahora:** el nonce se **reserva** al emitir el login (`/auth/login`) y se **consume** en el callback
  (usando el store genérico `pp_idempotencia`, PK como árbitro). Un segundo callback con el mismo state se
  rechaza (400). Test `test_state_no_reutilizable`.

---

## H-157 · Idempotencia completa en pagos y cobros (dinero)
**Fecha:** 2026-09-10 · **Módulo:** Tesorería / Juegos / Créditos · **Alcance:** backlog ALTA de H-153 (tanda 3)
- **Problema:** `con_idempotencia` cubría el servicing de contratos, pero NO caja/egresos/juegos/payoff legacy;
  el front mandaba la Idempotency-Key pero el backend la ignoraba → un doble-POST podía duplicar el pago.
- **Cambio:** se envolvieron en `con_idempotencia` (enrutando por id de entidad para no serializar el modelo):
  caja `/cobrar` y `/cola/cobrar` (H-154), y ahora egresos `/ordenes/{id}/pagar` y `/pagar-chequera`, juegos
  `/liquidaciones/{id}/cobrar` y `/agencias/cobrar`, y payoff legacy `/creditos/{id}/cancelar`. El front
  `cancelarCredito` pasó a `postIdem`; los demás ya mandaban la clave.
- **Verificado:** `test_pagar_op_idempotente`, `test_cobrar_liquidacion_idempotente` — doble-POST con la
  misma clave devuelve el mismo resultado, sin duplicar.
- **Controles de Versión:** caso `idempotencia-pagos-cobros`.

---

## H-156 · Enforcement RBAC fino en el backend (no sólo en el front)
**Fecha:** 2026-09-10 · **Módulo:** Seguridad / RBAC · **Alcance:** backlog ALTA de H-153 (tanda 2)
- **Problema:** el nivel por pantalla que configura *Roles* (Perfiles.tsx) sólo se enforcaba en 1 endpoint;
  Clientes/Feriados confiaban en el gateo del front → un rol restringido podía escribir vía API.
- **Cambio:** las ESCRITURAS del **Maestro de clientes** (`crear`/`modificar`/`dar_baja`/`reactivar`) y del
  **calendario de Feriados** (`crear`/`editar`/`borrar`/`importar`) ahora exigen `requiere_permiso(ruta,
  "ESCRITURA")`. La lectura queda permisiva (la búsqueda de cliente la usan varios circuitos). ADMG y los
  roles sin RBAC configurado pasan (`sin_restricciones` → TOTAL), así no se rompe la operación single-admin.
- **Verificado:** `test_escritura_cliente_exige_permiso_backend` — un rol con sólo CONSULTA sobre
  `/clientes/maestro` recibe 403 al crear; admin crea (201).
- **Pendiente (extensión):** aplicar el mismo patrón a Contabilidad y demás routers que hoy sólo usan
  `get_current_user` o `requiere_perfil` coarse; alinear `requiere_perfil`/`_req_admin` para que miren
  `roles_de` (grupos) y no sólo el perfil principal.
- **Controles de Versión:** caso `rbac-fino-backend`.

---

## H-155 · Auditoría de las mutaciones de IAM (quién hizo qué en Seguridad)
**Fecha:** 2026-09-10 · **Módulo:** Seguridad / IAM · **Alcance:** backlog ALTA de H-153 (tanda 2)
- **Problema:** `admin.py` no dejaba rastro de ninguna mutación de IAM (usuarios/roles/grupos/permisos); sólo
  se auditaba el LOGIN. Grave para un módulo de seguridad.
- **Cambio:** helper `_actor` (usuario, perfil, IP) + `_audit` sobre `services.auditoria.registrar_cambio`,
  aplicado a **todas** las mutaciones: alta/edición/baja/reactivación/cambio de clave de usuario, perfil
  principal + roles adicionales, alta/edición/baja de grupos y sus roles, membresías (grupo±), permisos
  directos (permiso±), ABM de roles y sus permisos por pantalla (individual y bulk). Cada evento guarda
  quién, operación, antes/después e IP; el registro nunca interrumpe el flujo de negocio.
- **Verificado:** `test_iam_mutaciones_dejan_auditoria` — alta de usuario (con X-Forwarded-For) y de grupo
  quedan en `auditoria-cambios` con actor + IP + resultado.
- **Controles de Versión:** caso `iam-auditoria`.

---

## H-154 · Fixes del QA profundo (tanda 1): integridad de dinero y de administración
**Fecha:** 2026-09-10 · **Módulo:** Contratos / Caja / Clientes / IAM · **Alcance:** backlog ALTA de H-153
Primera tanda de correcciones de los hallazgos ALTA del QA profundo (`salida/qa-profundo-2026-09-09.md`),
cada una con test:
1. **Reversa de refinanciación bloqueada.** `contratos.py` `reversar` ahora rechaza (422) la actividad
   `RENEGOTIATION`: reversarla reactivaba el contrato viejo (recompute → ACTIVO con saldo entero) mientras el
   nuevo seguía vivo → mismo capital colocado dos veces. El front oculta el botón ↩ sobre RENEGOTIATION
   (`SituacionClientePP.tsx`). Test `test_no_reversar_refinanciacion_evita_doble_capital`.
2. **`liquidar_lote` idempotente + serializado.** Envuelto en `con_idempotencia` (Idempotency-Key) y cada
   contrato se toma con `with_for_update` + recheck de estado A_LIQUIDAR dentro de la transacción → doble-clic
   o dos lotes concurrentes no desembolsan dos veces ni duplican asiento. El front (`ctoLiquidarLote`,
   `ctoDesembolsar`) ahora manda la clave (`postIdem`).
3. **Cobros de caja idempotentes.** `/api/caja/cobrar` y `/cola/cobrar` pasan por `con_idempotencia`
   (el front ya mandaba la Idempotency-Key; faltaba honrarla en el backend). Enrutado por `recibo_id` para no
   serializar el modelo pydantic.
4. **Alta de cliente con CUIL único (la DB es árbitro).** `Cliente.cuil` ahora es `unique` (+ índice
   `uq_clientes_cuil` creado en la migración de arranque, guardado ante duplicados previos). `crear` inserta y
   deja que la constraint decida (IntegrityError → 409), con Idempotency-Key. Tests
   `test_alta_cliente_cuil_unico_y_dv`, `test_alta_cliente_idempotente` (nuevo `tests/test_clientes.py`).
5. **No dejar el sistema sin administrador.** Guard de "último ADMG activo" agregado a `editar_usuario` y
   `set_usuario_perfiles` (no degradar el perfil principal del único admin) y a `editar_perfil` (no deshabilitar
   el rol ADMG, que bloquearía el login de todos). Test `test_qa_no_degradar_ultimo_admin`.
- **Controles de Versión:** casos `no-reversar-refinanciacion`, `liquidar-lote-idempotente`,
  `cobro-caja-idempotente`, `cliente-cuil-unico`, `no-degradar-ultimo-admin`.
- **Pendiente (tanda 2):** idempotencia en egresos/juegos y payoff legacy; **auditoría de IAM**
  (`registrar_cambio` en las mutaciones de admin.py); **enforcement RBAC fino por pantalla** en el backend
  (hoy sólo front en Contabilidad/Clientes/Feriados); UI de documentos del portal; anti-replay del state OIDC.
- **pytest:** verde tras la tanda (8 tests nuevos); tsc + candado OK.

---

## H-153 · QA profundo (backoffice + portal): 2 agujeros de permisos corregidos + backlog
**Fecha:** 2026-09-09 · **Módulo:** transversal · **Alcance:** pedido del usuario (QA por pantalla/APIs/datos)
- **Método:** 4 revisiones estáticas en paralelo (créditos, seguridad/IAM, portal, APIs) + verificación
  dinámica en vivo (navegador + APIs contra Postgres + datos). Informe completo en
  `salida/qa-profundo-2026-09-09.md`.
- **Verificado en vivo (Postgres):** circuito de dinero completo — liquidación por lote → desembolso (2
  contratos ACTIVO, asientos balanceados), pago de cuota, **idempotencia** (reintento no duplica), **reversa**
  (recompute deja el saldo exacto), **payoff** (CERRADO), contabilidad balanceada en cada paso (desbalance 0).
  Datos demo limpiados después.
- **Corregidos (2 agujeros ALTA, ambos en el área de H-150):**
  1. **Aprobar/rechazar sin permiso con el workflow inactivo.** `solicitudes.py` (aprobar/rechazar) y
     `productos.py` (aprobar) delegaban todo en el motor; con la regla sembrada INACTIVA (H-141) el motor
     devolvía ok **sin mirar rol** → cualquier usuario autenticado resolvía. Fix: sin workflow activo se exige
     `_req_aprueba` (rol aprobador, H-150); con workflow activo sigue gateando el motor por rol de nivel +
     cuatro-ojos (no rompe cadenas N-niveles con roles intermedios). Tests:
     `test_aprobar_exige_rol_aun_con_workflow_inactivo`, `test_aprobar_linea_exige_rol_aun_con_workflow_inactivo`.
  2. **Grupo desactivado seguía otorgando acceso.** `roles_de` (`permisos.py`) filtraba vigencia pero nunca
     miraba `Grupo.activo`. Fix: sólo toma roles de grupos activos → desactivar un grupo corta el acceso de
     todos sus miembros de una. Test: `test_grupo_inactivo_no_otorga_acceso`.
- **Backlog priorizado (no corregido acá):** ALTA — reversa de refinanciación duplica capital; `liquidar_lote`
  no idempotente/serializado; idempotencia ausente en caja/egresos/juegos/payoff; alta de cliente sin unicidad
  concurrente (sin constraint en `cuil`); lockout del último admin (editar_usuario/set_perfiles/editar_perfil);
  IAM sin auditoría; RBAC fino sólo en front; portal sin UI de documentos; migradores sin test de permiso.
  MEDIA/BAJA y **casos de test faltantes (~Alta 20 · Media 30 · Baja 25)** detallados en el informe.
- **Controles de Versión:** casos `aprobar-exige-rol-wf-inactivo` y `grupo-inactivo-corta-acceso`.
- **pytest:** verde tras los fixes (3 tests nuevos); tsc + candado OK.

---

## H-152 · Diálogos in-app: fuera window.confirm / alert / prompt del browser
**Fecha:** 2026-09-09 · **Módulo:** UX transversal · **Alcance:** pedido del usuario
- **Antes:** confirmaciones, avisos y entradas rápidas usaban los diálogos **nativos** del navegador (el cartel
  gris "localhost:5173 dice…"): rompen la identidad visual (no respetan tema ni tipografía), varían por
  navegador/OS y bloquean el hilo.
- **Ahora:** módulo único **`src/ui/dialog.tsx`** con API imperativa drop-in: `confirmar()` → Promise<boolean>
  (variante **danger** roja para lo irreversible), `avisar()` (avisos/errores) y `pedirTexto()` →
  Promise<string|null> (motivo, importe, clave, cuotas). Modal **centrado**, con el tema de la app, scrim,
  esquinas redondeadas; **Esc cancela, Enter acepta, clic en el fondo cierra**, foco automático en el botón/
  input principal. El host `<Dialogos/>` se monta una vez en el root (`App.tsx`); el store es un singleton
  pub/sub, así los call sites sólo importan la función (sin context ni props).
- **Alcance:** se convirtieron ~15 `confirm`, ~10 `prompt` y ~58 `alert` en **14 pantallas** (Originar,
  Liquidación por lote, Solicitudes, Situación del cliente —pago parcial/prepago/diferir/payoff/reversar/
  refinanciar—, Caja de créditos, Configurar Créditos, Inbox, Migradores, Perfiles/Grupos/Feriados borrar,
  Usuarios reset de clave, Tablero, Controles de Versión). El alta/edición de cliente además **cierra con Esc**.
- **Verificado (navegador):** el diálogo in-app abre centrado y temeado (probado "Dar de baja" → input con
  foco), **Esc lo cierra sin mutar**; Solicitudes y demás rutas renderizan; consola limpia en pestaña nueva.
  tsc + candado 101 páginas OK.
- **Controles de Versión:** principio de diseño `dialogos-in-app` (+ `confirmar-irreversible` actualizado) y
  caso `dialogos-in-app`.

---

## H-151 · Maestro de clientes: alta/edición como ventana flotante centrada (modal)
**Fecha:** 2026-09-09 · **Módulo:** Clientes (Maestro) · **Alcance:** pedido del usuario
- **Antes:** el alta/edición de cliente abría como **panel lateral** (drawer) deslizado desde la derecha.
- **Ahora:** abre como **ventana flotante centrada** en el medio de la pantalla (modal), con scrim más marcado,
  esquinas redondeadas, `max-height:90vh` y scroll interno del cuerpo (header y footer fijos). Cambio de CSS
  puntual en `.drawer`/`.drawer-scrim` (`src/styles.css`), únicas usuarias = Maestro de clientes; sin tocar el
  JSX ni otras pantallas.
- **Verificado (navegador):** "Nuevo cliente" y edición abren centrados a ~680px (min(680px,94vw)) sobre el
  scrim, con la lista detrás; responsive a 1200px y a la vista angosta. tsc + candado 101 páginas OK.

---

## H-150 · Cuatro-ojos ordenado: quién aprueba sale de roles y grupos (no de overrides)
**Fecha:** 2026-09-09 · **Módulo:** Seguridad / Workflow / Créditos · **Alcance:** pedido del usuario
- **Problema:** el permiso para aprobar convivía en dos lugares desacoplados y confusos: (a) el RBAC por
  pantalla (perfil × ruta → nivel) y (b) el motor de workflow, que decidía "quién aprueba" con el **perfil
  principal** del usuario + **excepciones INCLUIR/EXCLUIR por nivel**. Habilitar a alguien exigía tocar la
  config del workflow, no sus roles. Pedido: *"que se cumpla el cuatro-ojos… con los roles y grupos, no de
  otra manera"*.
- **Cambio (una sola fuente = roles efectivos):**
  - `permisos.caps_creditos(db, user)` deriva **{edita, aprueba}** de los **roles efectivos** del usuario
    (`roles_de`: perfil principal + roles directos + **roles heredados de grupos**). Créditos edita quien
    tiene rol operador (`ADMG/XCR/OPER/SUPE`); aprueba quien tiene rol aprobador (`ADMG/SUPE`). Reemplaza el
    chequeo hardcodeado por perfil en `productos.py` y `solicitudes.py` (mismo helper para las dos pantallas).
  - `workflow._rol_apto(db, nivel, user)` ahora es `nivel.rol ∈ roles_de(db, user)`: el nivel define **qué
    rol** aprueba ese paso y el usuario lo cumple si tiene ese rol **por perfil o por grupo**. Se eliminó el
    camino de aprobación por **INCLUIR/EXCLUIR** por nivel (la "otra manera" que el usuario quería sacar). El
    cuatro-ojos (no aprueba quien ya intervino) queda intacto.
  - **Seed** de roles y grupos del circuito (idempotente): roles `OPER` (Operador de créditos) y `SUPE`
    (Supervisor/aprobador); grupos `GCRED-OP → OPER` y `GCRED-SUP → SUPE`. Sumar a alguien al grupo
    Supervisión le da el rol aprobador sin overrides.
  - **UI** (`WorkflowAprobaciones.tsx`): se quitó el panel "Excepciones por usuario" (INCLUIR/EXCLUIR) que ya
    no afectaba la aprobación; el inspector del nivel ahora explica *"aprueba todo usuario con el rol X, por
    perfil o heredado de un grupo — se asigna en Seguridad → Roles/Grupos"*.
- **Verificado — pytest (SQLite):** 345/345; nuevo `test_workflow_quien_aprueba_via_roles_grupos` (reemplaza
  el de INCLUIR): `creditos` (XCR) no aprueba un nivel rol ADMG (403) y, tras sumarlo a un grupo que otorga
  ese rol, **sí** aprueba. `test_permisos_por_perfil` sigue: XCJ {edita:false, aprueba:false}, XCR
  {edita:true, aprueba:false}, ADMG ambos. tsc + candado 101 páginas OK.
- **Verificado — Postgres (E2E live):** con LINEA activa y nivel rol `SUPE`: un operador XCR agregado al
  grupo `GCRED-SUP` (hereda SUPE) **aprobó** una línea enviada por admin (APROBADO, aprobadoPor); un operador
  XCR sin el grupo recibió **403**. Datos demo (2 usuarios, 8 líneas, membresías) y la config del workflow
  **limpiados/revertidos** (LINEA vuelve a inactivo, rol ADMG).
- **Controles de Versión:** principio `cuatro-ojos` reescrito (roles/grupos como única fuente, H-107/H-150) +
  caso `cuatro-ojos-por-roles`.

---

## H-135 · Circuito originación → liquidación por lote → desembolso
**Fecha:** 2026-09-09 · **Módulo:** Solicitudes / Originación / Liquidación · **Alcance:** pedido del usuario
- **Decisiones (usuario):** originar desde una solicitud es una **revisión** (no reingresa datos) y el
  contrato **siempre queda A_LIQUIDAR** (nunca desembolsa en el acto); el desembolso pasa por un **lote diario**.
- **Fase A — Originar = revisión + A_LIQUIDAR:** en `_originar_impl`, si la originación viene de una
  solicitud (`solicitud_pp_id`/`solicitud_id`) se fuerza `desembolsar=False` (queda A_LIQUIDAR); la
  originación **directa** (sin solicitud, p. ej. servicing/tests) mantiene el flag. En el backoffice el botón
  **"Originar contrato"** dejó de mandar al wizard de 5 pasos: ahora **confirma la revisión** (el panel ya
  muestra todos los datos + el checklist H-134) y llama a `originar` con los datos de la solicitud.
- **Fase B — Liquidación por lote:** `GET /contratos/lotes-liquidacion` agrupa los A_LIQUIDAR por
  **día de originación** (fecha_valor); `POST /contratos/liquidar-lote {fecha}` desembolsa todo el lote,
  respetando el **workflow DESEMBOLSO** (los que requieran aprobación quedan pendientes; el resto pasa a
  ACTIVO). Pantalla nueva **"Liquidación por lote"** (menú Créditos, badge new): lista de lotes por día →
  detalle de contratos → botón "Liquidar lote (N) → desembolso". La ruta GET se declara **antes** de
  `/{contrato_id}` (si no, se interpretaría como id).
- **Verificado (Postgres + navegador):** originar desde solicitud → **A_LIQUIDAR**; el lote del día lo lista
  (2 créditos, $1.300.000); liquidar el lote desde la UI → "Desembolsados: 2" y los contratos quedaron
  **ACTIVO**; la pantalla vuelve a "No hay créditos pendientes de liquidar". `test_portal` 21/21 (nuevo
  `test_originacion_deja_a_liquidar_y_lote_desembolsa`); candado 101 páginas OK; tsc frontend OK. Datos demo
  (contratos, cuotas, actividades, asientos y solicitudes) **limpiados**.
- **Fase C:** ver H-136.

---

## H-149 · Situación del cliente: vista centrada en el cliente (agrupa préstamos)
**Fecha:** 2026-09-09 · **Módulo:** Créditos / Servicing · **Alcance:** pedido del usuario (cliente con &gt;2 contratos)
- **Antes:** lista plana de contratos (mezclaba los de distintos clientes al buscar); con un cliente de varios
  préstamos no había una visión consolidada.
- **Ahora:** se busca el cliente y se ve **su situación**: por cada cliente una **tarjeta** con *N préstamos*,
  *activos*, *en mora* y **saldo total**, y debajo la lista de sus contratos; recién ahí se **elige el
  contrato** para operar (se expande el servicing como antes). Agrupado en el front por `cliente`
  (`grupos` con useMemo), ordenado por nombre; la columna Cliente sale de la tabla (queda en el encabezado).
- **Verificado (navegador):** GOMEZ con 3 préstamos → tarjeta "3 préstamos · 3 activos · Saldo total
  $2.100.000" + los 3 contratos; elegir uno abre el servicing; sin overflow. tsc + candado OK. Datos demo limpiados.

---

## H-148 · Situación del cliente: doble-clic tragado (dedup 4 s) + desborde horizontal
**Fecha:** 2026-09-09 · **Módulo:** Créditos / Servicing · **Alcance:** revisión funcional pedida (diferir/reversar "raro")
- **Diagnóstico:** las acciones de servicing (pagar, diferir, prepago, reversar, refinanciar) **funcionan bien
  en el backend y la UI las refleja** (verificado: diferir capitaliza y baja la cuota; reversar restaura saldo y
  cuotas, marca REVERSADA + REVERSAL). Los dos problemas eran de UI/cliente:
  1. **`postIdem` deduplicaba 4 s DESPUÉS de responder**: apretar la misma acción de nuevo dentro de esa
     ventana (p. ej. Diferir otra cuota, o Pagar la cuota siguiente) devolvía el resultado **viejo** y se
     perdía la 2ª acción (en pago, se perdía un pago). Verificado: doble-clic en Diferir aplicaba **1** en vez
     de 2. **Fix:** dedup **sólo mientras la request está en vuelo** (protege el doble-submit concurrente sin
     tragar acciones deliberadas; el árbitro real es la Idempotency-Key + backend). Ahora doble-clic → 2.
  2. **Desborde horizontal**: el detalle expandido dentro de la tabla de contratos (10 columnas) empujaba el
     ancho de la página a ~1278 px (viewport 736) → scroll lateral, botón de reversar al borde, header
     solapando la topbar. **Fix:** `overflow-x:auto` en la tarjeta de la tabla + `.sv-body` con `min-width:0`
     y stack a 1 columna &lt;900 px. Verificado: docScrollW 1278 → 743 (≈ innerWidth), botones alcanzables.
- **Sin cambios de backend** (fixes de `api.ts` + `SituacionClientePP.tsx`); tsc + candado OK. Datos demo limpiados.

---

## H-147 · Portal: soporte de modo oscuro (theme-aware)
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** hallazgo de la pasada visual (dark)
- **Hallazgo:** el portal era **light-only** — con el dispositivo en modo oscuro seguía en claro (no tenía
  `prefers-color-scheme`).
- **Fix:** bloque `@media (prefers-color-scheme: dark)` en `portal/src/App.tsx` que redefine los tokens
  (`--p-*`) con paleta oscura manteniendo la identidad (navy más claro para contraste + verde), y ajusta los
  fondos claros hardcodeados (`.p-alert`, `.p-ok`, `.p-preap`, `.p-pill.ok`, checks de los dots del stepper).
- **Verificado (navegador):** con `prefers-color-scheme: dark` el portal renderiza en oscuro on-brand
  (fondo navy, texto claro, stepper/brand en azul claro); **light sigue intacto**. tsc portal OK; responsive a
  375 px OK en ambos temas. El backoffice ya era theme-aware (toggle propio).

---

## H-146 · Portal: rangos de edad/sueldo/antigüedad en el backend
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** cierre del backlog de validaciones (H-141 §3)
- **Qué:** `DatosSolicitante` (base de `PortalSimularIn`/`PortalSolicitudIn`) ahora acota **edad 18-99**,
  **antigüedad ≥0** (≤1200) y **sueldo >0** con `Field(ge/le/gt)`; antes los `min/max` del portal eran sólo HTML
  "blandos" y el backend no revalidaba. Todos siguen opcionales (None = no declarado).
- **Verificado:** `/portal/simular` con edad 15 → **422**; edad 40 → 200. `test_portal` 23/23.

---

## H-145 · Validaciones y obligatorios en el Maestro de clientes
**Fecha:** 2026-09-09 · **Módulo:** Clientes · **Alcance:** backlog de validaciones del QA (H-141 §3, ítems 1-2)
- **CUIL con dígito verificador:** el front ahora valida el **DV** (mismo algoritmo que el backend
  `valida_cuil`), no sólo la longitud → se cierra el desajuste que dejaba pasar un CUIL de 11 dígitos con DV
  inválido y devolvía 422. Hint "Dígito verificador inválido" / "11 dígitos ✓" y bloqueo del botón.
- **Otros campos:** DNI (solo dígitos, 7-8, con aviso), email (formato, `type=email`), sueldo (solo numérico,
  ≥ 0), CBU (solo dígitos, 22, contador n/22). Cada uno con clase `err` + hint y **gatea "Crear/Guardar"**.
- **Obligatorios marcados:** asterisco rojo en **Apellido y nombre** y **CUIL**.
- **Backend `ClienteBase`:** `apellido_nombre` con `min_length=1` y `sueldo` con `ge=0` (paridad con el front).
- **Verificado (navegador):** CUIL `20111111110` (DV malo) → bloqueado con "Dígito verificador inválido";
  `20123456786` (válido) → "11 dígitos ✓" y botón habilitado. tsc + candado OK; `test_admin` 5/5. Sin datos demo.

---

## H-144 · Cliente por búsqueda también en Nueva solicitud (no alta manual)
**Fecha:** 2026-09-09 · **Módulo:** Solicitudes · **Alcance:** consistencia con H-143 (pedido del usuario)
- **Qué:** en el wizard de **Nueva solicitud** del backoffice, el cliente ahora **se elige del maestro** con el
  mismo **buscador typeahead** de Originar (apellido/CUIL/DNI, debounce 300 ms), con tarjeta del cliente
  seleccionado + "Cambiar cliente" y enlace a Clientes → Maestro si no hay resultados. Se **quitó** el toggle
  "Tipo de cliente" y el **alta express manual** (nombre/CUIL/DNI) de esta pantalla: la solicitud de backoffice
  es siempre para un cliente **REGISTRADO** (igual criterio que la originación).
- **Backend intacto:** el estado NO_REGISTRADO / alta express sigue existiendo para el **portal** (el ciudadano
  no está en el maestro) y su **promoción** vía "Dar de alta en maestro" (H-137). Sólo se sacó la carga manual
  de la UI de backoffice.
- **Verificado (navegador + Postgres):** typeahead ("perez" → PEREZ, JUAN CARLOS) → tarjeta → wizard → POST 201;
  la solicitud quedó **REGISTRADA con cliente_id**. tsc + candado OK. Datos demo limpiados.

---

## H-143 · Unificación del circuito: Originar = instrumentación; desembolso solo por lote
**Fecha:** 2026-09-09 · **Módulo:** Créditos / Originación · **Alcance:** resuelve la inconsistencia de H-141 (§5)
- **Problema:** había **dos caminos al desembolso** — el paso 5 de "Originar Crédito" (desembolso directo con
  `ctoDesembolsar`) y la nueva **Liquidación por lote**. No estándar (el desembolso no debe ser "un clic que
  aprueba y paga a la vez").
- **Decisión (usuario):** Originar = **solo instrumentación**; el contrato queda **A_LIQUIDAR** y **todo el
  desembolso** pasa por Liquidación por lote.
- **Cambio (frontend `OriginarCredito.tsx`):** el paso 5 dejó de desembolsar; ahora es una **confirmación**
  que muestra el contrato **A liquidar** + neto a acreditar y botón **"Ir a Liquidación por lote →"**. Se quitó
  el botón "Confirmar desembolso" y la función `confirmarDesembolso`. `otorgar()` ya mandaba `desembolsar:false`
  (queda A_LIQUIDAR). Paso renombrado "Instrumentado"; subtítulo/comentarios actualizados.
- **Verificado (navegador + Postgres):** recorrí el wizard (CBU obligatorio, H-141) → "Otorgar" → el contrato
  quedó **CTO-… A_LIQUIDAR**, la pantalla apuntó al lote, **sin** opción de desembolso directo. tsc + candado OK.
  Backend sin cambios (el flag `desembolsar` del API se conserva para tests/uso programático). Datos demo limpiados.
- **Cliente por búsqueda (no carga manual):** se quitó la carga manual de nombre/CUIL/DNI en el paso 1 de
  Originar. Ahora el cliente **se elige del maestro** con un **buscador typeahead** (apellido/CUIL/DNI, debounce
  300 ms, `api.clientes`), muestra una **tarjeta del cliente seleccionado** con "Cambiar cliente", y si no hay
  resultados enlaza a Clientes → Maestro (el alta vive ahí). Se mantiene, como alternativa, "traer de una
  solicitud aprobada". El paso 1 sólo avanza con un cliente/solicitud **seleccionado** (no tipeado). Verificado
  en el navegador (typeahead → tarjeta → sólo datos de evaluación).

---

## H-142 · Seguridad: catálogo de Roles vacío tras el reset + orden del menú
**Fecha:** 2026-09-09 · **Módulo:** Seguridad / IAM · **Alcance:** pedido del usuario
- **Hallazgo:** tras el reset (H-141), la pantalla **Seguridad → Roles (perfiles)** aparecía **vacía**
  ("Sin perfiles, 0 de 0"). Causa: `seed()` crea los usuarios con su **código de perfil** (ADMG/XCR/XCJ)
  pero **no sembraba la tabla `perfiles`** (el maestro de roles que lee `GET /perfiles-maestro`). El detalle
  del usuario sí mostraba el rol principal (lo toma de `usuarios.perfil`), pero el catálogo no tenía las fichas.
  (Además: el catálogo canónico `security.PERFILES` usaba códigos distintos —CR/CJ— a los operativos —XCR/XCJ—.)
- **Fix:** nuevo **`seed_perfiles(db)`** (idempotente, siempre, como impuestos/productos) que siembra el maestro
  de roles con los códigos que la app realmente usa: ADMG, XCR, XCJ, XCA, XTE, XSE, XDE, XME. Cableado en el
  `lifespan` y aplicado a la base actual. Ahora la pantalla lista los 8 roles con su **conteo de usuarios**
  (ADMG 1, XCR 1, XCJ 1, resto 0).
- **Orden del menú (pedido):** Seguridad → Accesos ahora es **Usuarios · Grupos · Roles (perfiles)**.
- **Verificado (navegador):** Roles muestra 8 habilitados con conteos; menú en el orden pedido; login OK.
  Suite completa re-corrida (los tests que ejercitan el cuatro-ojos activan la regla con `_activar_wf`).

---

## H-141 · QA E2E en base limpia: bloqueo cuatro-ojos single-admin + primeras validaciones
**Fecha:** 2026-09-09 · **Módulo:** QA transversal · **Alcance:** recorrido punta a punta + auditoría de validaciones (ver `salida/qa-visual-2026-09-09.md`)
- **Hallazgo bloqueante (single-admin):** en la app nueva, una solicitud cargada en **backoffice** no se puede
  aprobar: el workflow **SOLICITUD** (cuatro-ojos) exige rol **ADMG** en el nivel de aprobación, y el único
  ADMG (`admin`) no puede aprobar lo que creó (separación de funciones). Igual con **LINEA** al publicar. El
  **portal no** lo sufre (crea como `portal:<sub>`). **RESUELTO:** `seed_workflow` siembra **LINEA y SOLICITUD
  inactivos** (single-admin operable de entrada; se activan al sumar un 2º aprobador). Base actual con los 4
  workflows inactivos. Re-verificado E2E como admin: crear→aprobar→originar→lote→desembolso→ACTIVO, sin bloqueo.
- **Validaciones corregidas:** (1) backend `SolicitudIn.monto_solicitado`/`plazo_solicitado` → `Field(gt=0[/le=240])`;
  (2) wizard Nueva solicitud (express): exige **CUIL 11 díg** en paso 1 (gate + solo dígitos + hint) alineado
  con el 422 del backend, DNI solo dígitos, **asteriscos** en obligatorios; (3) **OriginarCredito**: CBU de
  acreditación **obligatorio** (solo dígitos, 22, gatea "Siguiente") — cierra el hueco de H-134 en originación
  directa; (4) estilo global `.req` (asterisco rojo).
- **Auditoría (pendiente, en el doc):** Clientes.tsx (DNI/email/sueldo/CBU sin validar + DV de CUIL + asteriscos);
  backend `ClienteCreate` (min_length); portal edad/sueldo (rangos en backend); unificar desembolso (paso 5 de
  Originar vs lote); QA visual dark/responsive y resto de módulos.
- **Verificado:** circuito E2E OK (con nota del bloqueo); `test_solicitudes`+`test_portal` 32/32; tsc front OK;
  candado 101 páginas OK. Datos demo del recorrido limpiados; workflows SOLICITUD/DESEMBOLSO restaurados.

---

## H-140 · Portal: guardar / retomar borrador de la solicitud
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** backlog UX (H-129)
- **Qué:** el ciudadano puede **guardar la solicitud a medias** y **retomarla** después. Botón "Guardar
  borrador" en el wizard; al volver, un banner "Tenés una solicitud sin terminar (guardada …)" con
  **Retomar / Descartar**. Al enviar la solicitud el borrador se limpia solo.
- **Cómo:** el estado del wizard (situación/edad/antigüedad/sueldo/haberes, producto/monto/plazo, destino,
  CBU, consentimientos y el paso) se persiste en **localStorage por `sub`** del ciudadano. **No** crea una
  PPSolicitud BORRADOR en el backend, así que no aparece en el Inbox del backoffice. Es por dispositivo
  (un futuro server-side/cross-device queda como follow-up).
- **Verificado (navegador):** cargué situación=Docente + edad=45, "Guardar borrador", recargué → apareció
  el banner; "Retomar" restauró los campos (Docente/45) y ocultó el banner. tsc portal OK.

---

## H-139 · Liquidación por lote: alerta de contratos esperando aprobación del desembolso
**Fecha:** 2026-09-09 · **Módulo:** Créditos / Liquidación · **Alcance:** quick win del backlog
- **Qué:** cuando el workflow **DESEMBOLSO** está activo, liquidar un lote deja los contratos **esperando
  aprobación** (no se desembolsan; quedan A_LIQUIDAR con un PPWorkflowPendiente). La pantalla ahora lo avisa.
- **Backend:** `GET /contratos/lotes-liquidacion` agrega `pendienteAprobacion` por contrato y `pendientes`
  por lote (cuenta los PPWorkflowPendiente objeto=DESEMBOLSO en estado PENDIENTE).
- **Frontend:** pill **"N esperando aprobación"** (crit) en la fila del lote y **"Esperando aprobación"** por
  contrato; aviso en el detalle: se desembolsan al aprobarse en el Inbox de aprobaciones y volver a liquidar
  no los duplica.
- **Verificado (Postgres + navegador):** activé DESEMBOLSO, originé y liquidé el lote → `pendientesAprobacion`
  = [CTO], el contrato quedó A_LIQUIDAR, y la UI mostró "1 esperando aprobación" (lote) + "Esperando
  aprobación" (contrato). `test_portal` 23/23 (nuevo `test_lote_marca_pendientes_de_aprobacion`); tsc OK.
  Datos demo limpiados y **regla DESEMBOLSO restaurada a inactiva**.

---

## H-138 · Módulos del menú ocultos por defecto; sólo el admin los revela
**Fecha:** 2026-09-09 · **Módulo:** Navegación / Sidebar · **Alcance:** pedido del usuario
- **Qué:** se ocultan del menú lateral los módulos **Despacho, Caja, Juegos/Quiniela, Mesa de Entradas,
  Seguros y Adm. y Finanzas**. Quedan escondidos por defecto para todos. (Controles de Versión quedó SIEMPRE
  visible a pedido del usuario, por ser la fuente de Principios/QA.)
- **Cómo:** `Modulo.oculto` en `menu.ts` marca esos 6 módulos; el `Sidebar` los filtra salvo que el usuario
  sea **administrador** (`permisos.sinRestricciones`, perfil ADMG) **y** haya activado el botón
  **"Mostrar módulos ocultos"** (con su preferencia guardada en localStorage). Un no-admin nunca ve esos
  módulos ni el botón. Se agregó el icono `eye-off`.
- **Créditos `soloNuevos` + sin leyendas:** el módulo Créditos ahora sólo muestra las opciones **`nuevo`**
  (Configurar, Solicitudes, Originar, Liquidación por lote, Caja de créditos, Situación, Inbox, Tablero,
  Sistema de cálculos, Resumen de cobros); las **heredadas del legacy** (Líneas de crédito, Simulador,
  Jubilados, Cancelación, Baja, Recálculo, Turnos, Cuenta corriente, Estadísticas, Informe, Listado, Mora…)
  quedan ocultas y las revela el **mismo botón de admin**. Además se quitaron del sidebar las **leyendas de
  grupo** (Archivos/Datos/Procesos/Consultas/Reportes) en todos los módulos. Verificado: Créditos lista 10
  opciones `nuevo` y 0 subheaders; con el toggle on reaparecen módulos ocultos y las opciones heredadas.
- **Verificado en el navegador (admin ADMG):** por defecto el sidebar salta de Clientes a Créditos (Despacho/
  Caja/etc. no aparecen) y muestra el botón "Mostrar módulos ocultos"; al activarlo reaparecen (Despacho,
  Caja, …) y el botón pasa a "Ocultar módulos"; se vuelve a ocultar al desactivarlo. tsc frontend OK; candado
  101 páginas OK.

---

## H-137 · "Dar de alta en maestro" completa el CUIL (revisión del alta express)
**Fecha:** 2026-09-09 · **Módulo:** Solicitudes / Alta express · **Alcance:** cierre del circuito web→maestro
- **Qué:** el alta express al maestro dejó de ser un clic ciego. Ahora abre una **mini-revisión** (modal) que
  **precarga apellido/nombre y DNI** declarados (el DNI viaja desde Mi Catamarca, H-134) y el asesor
  **completa/confirma el CUIL** —que la web no trae— antes de crear el cliente.
- **Backend:** `PromoverIn` sumó `cuil/dni/apellido_nombre`; `promover_cliente` exige nombre, **valida el
  CUIL (11 dígitos)**, normaliza dígitos, deduplica por CUIL (si ya existe, vincula) y crea el `Cliente` con
  esos datos; la solicitud pasa a REGISTRADA.
- **Frontend:** el input de CUIL acepta solo dígitos y corta en 11 (igual criterio que el CBU, H-130); el
  botón "Dar de alta" se deshabilita con un CUIL a medias.
- **Verificado (Postgres + navegador):** precarga JUAN CARLOS PEREZ / DNI 30123456; CUIL "27a35-6b" → "27356"
  (solo dígitos) con botón deshabilitado; CUIL válido "20-30123456-7" → Cliente con cuil=20301234567,
  dni=30123456, solicitud REGISTRADA; CUIL inválido → 422. `test_portal` 22/22 (nuevo
  `test_alta_maestro_completa_cuil`); tsc frontend OK; candado 101 páginas OK. Datos demo limpiados.

---

## H-136 · "Nueva solicitud" del backoffice = ventana flotante con pasos
**Fecha:** 2026-09-09 · **Módulo:** Solicitudes / Alta guiada · **Alcance:** Fase C del pedido (H-135)
- **Qué:** el alta de solicitud en el backoffice dejó de ser un form inline y pasó a ser una **ventana
  flotante (modal) con 3 pasos** — **Solicitante → Simulación → Confirmación** — con stepper, igual que el
  alta del ciudadano. Paso 1 exige el solicitante (registrado o express); paso 2 la línea/monto/plazo.
- **Simulación sin ensuciar datos:** nuevo endpoint `POST /productos/{id}/simular-preview` — **mismo motor
  único** que la originación/simulación persistida, pero **NO persiste** (no agrega PPSimulacion a la lista
  guardada del producto). Devuelve cuota promedio, total, TNA y **elegibilidad** (segmento/canal/edad/antig.).
- **Confirmación:** resumen (cliente, línea, monto, plazo, cuota estimada, elegible) + destino + relación +
  observaciones; "Crear" deja la solicitud en **BORRADOR** (el pipeline de evaluación/originación sigue igual).
- **Verificado (navegador + Postgres):** modal con los 3 pasos; en paso 2 la simulación corrió sola al entrar
  (Jubilados/AGENTE_PUBLICO → "No elegible…"; Personal Flexible → "✓ Elegible", cuota $76.395, TNA 52%); paso 3
  mostró el resumen; "Crear" → POST 201 y SOL-2026-00001 (BORRADOR) en la lista. `test_productos` 26/26 (nuevo
  `test_simular_preview_no_persiste_y_evalua`); candado 101 páginas OK; tsc frontend OK. Datos demo limpiados.

---

## H-134 · Originación de solicitudes web = revisión con datos completos para liquidar
**Fecha:** 2026-09-09 · **Módulo:** Solicitudes / Originación · **Alcance:** canal web (origen PORTAL)
- **Hallazgo:** una solicitud del canal web entra **express (NO_REGISTRADO)** y `enviar_solicitud` guardaba
  `cliente_datos` con **`dni:"" , cuil:""`**, descartando el **documento** que Mi Catamarca sí entrega
  (`Ciudadano.documento`). Además `originar` no exigía identidad ni CBU → se podía originar/liquidar un crédito
  web sin datos verificados. "Dar de alta en maestro" creaba un `Cliente` con dni/cuil vacíos.
- **Fix (decisión del usuario: obligatorio Nombre+DNI+CBU, bloqueo duro):**
  1. `enviar_solicitud` ahora arrastra el **DNI** (= `c.documento` de Mi Catamarca) al `cliente_datos` (el CUIL
     no lo da el OIDC; queda deseable, se completa en el alta).
  2. Nuevo helper **`_datos_liquidacion(db, s)`** (solicitudes.py): checklist "listo para liquidar" que **sólo
     aplica al canal web** (origen PORTAL / canal WEB). Obligatorios: apellido/nombre + DNI + CBU (22 díg.);
     deseables (no bloquean): CUIL, sueldo. Devuelve `aplica/lista/faltantes/items`; se expone en el serial de
     la solicitud (`datosLiquidacion`).
  3. `contratos.originar` **bloquea (422)** una solicitud web que no está `lista`, listando los faltantes
     (import lazy para evitar el ciclo solicitudes↔contratos). La originación pasa a ser una **revisión**.
  4. Backoffice (`SolicitudesCredito.tsx`): panel **"Revisión para liquidar"** con ✓/✕ por dato y badge
     lista/faltan datos; el botón **"Originar contrato" queda deshabilitado** si faltan datos. CSS scopeado
     `.sol-revli*` con tokens de tema.
- **Verificado (Postgres + navegador):** solicitud web completa → DNI `30123456` viajó, checklist **LISTA**,
  botón habilitado; al vaciar el DNI → checklist **FALTAN DATOS** (DNI ✕ "falta"), botón deshabilitado y
  `originar` respondió 422 "…completá DNI". `test_portal` 20/20 (nuevo
  `test_originacion_web_es_revision_y_bloquea_sin_datos`); portal+solicitudes+contratos 70/70; candado 100
  páginas OK; tsc frontend OK. Datos demo limpiados.

---

## H-133 · Portal: destino del crédito ("¿para qué lo necesitás?")
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** backlog UX (H-129) — propósito del préstamo
- **Qué:** en el paso 1 del wizard el ciudadano elige (opcional) el **destino** del crédito
  (Vivienda/Vehículo/Consumo/Educación/Salud/Refinanciación/Emprendimiento/Otro). Viaja en la solicitud,
  se ve en el resumen de confirmación y en el detalle, y **el asesor lo ve** en el backoffice al evaluar.
- **Backend:** `DESTINOS` (código→etiqueta) + `_destino_norm` en `portal.py` (fuente de verdad; normaliza a
  mayúsculas y descarta desconocidos → vacío). `PortalSolicitudIn.destino` opcional; se persiste el **código**
  en `datos_adicionales.destino`; `PortalSolicitudDetalle.destino` devuelve la **etiqueta**. El backoffice
  (`SolicitudesCredito.tsx`) muestra "Destino" en la grilla del detalle (map código→etiqueta).
- **Verificado (Postgres + navegador):** 'vivienda' → guardó `VIVIENDA`, detalle devolvió "Vivienda /
  refacción"; destino desconocido → vacío. En el portal el select aparece en el paso 1 y el resumen mostró
  "Destino: Vehículo"; la API del backoffice sirvió `datosAdicionales.destino=VIVIENDA`. `test_portal` 19/19
  (nuevo `test_solicitud_guarda_destino`); tsc portal+frontend OK; candado 100 páginas OK. Datos demo limpiados.

---

## H-132 · Portal: seguimiento visual del expediente (stepper en el detalle de la solicitud)
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** backlog UX (H-129) — tracking del trámite
- **Qué:** el detalle de "Mis solicitudes" abre con un **stepper** que muestra en qué etapa va el trámite:
  **Enviada → En evaluación → Aprobada → Otorgada**, y si fue rechazada, **Enviada → En evaluación → Rechazada**
  (rojo). Da al ciudadano visibilidad del expediente sin llamar ni escribir.
- **Sin cambios de esquema:** las etapas se **derivan del `estado`** de la PPSolicitud (`pasosExpediente()` en
  `portal/src/App.tsx`): EN_EVALUACION/APROBADA/ORIGINADA marcan el paso actual; ORIGINADA = todo verde;
  RECHAZADA corta con ✕. Etapas superadas en verde (✓), la actual en navy con glow, las pendientes en gris.
- **Diseño:** CSS scopeado `.p-track*` con tokens del portal; se agregaron `--p-crit`/`--p-crit-soft` (y se
  migró `.p-pill.crit` a esas variables). El portal no pasa por el candado (sólo escanea `frontend/`).
- **Verificado en el navegador (Postgres):** recorrí los 4 estados moviendo `pp_solicitud.estado`
  (EN_EVALUACION → APROBADA → ORIGINADA → RECHAZADA) y el stepper avanzó/coloreó correcto en cada uno.
  `test_portal` 18/18; tsc portal OK; candado 100 páginas OK. Datos demo limpiados.

---

## H-131 · Portal: se quita la carga de adjuntos de "Mis solicitudes"
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** pedido del usuario
- **Qué:** el detalle de "Mis solicitudes" ya **no** muestra la sección **Documentación** (subir/listar/borrar
  adjuntos). Se removió del portal (`portal/src/App.tsx`) el bloque JSX, el estado (`docs/tipoDoc/subiendo`),
  el `useEffect` de carga, los helpers `subirDoc/borrarDoc`, las constantes `TIPOS_DOC/TIPODOC_LABEL/kb`, el
  import `Documento` y el CSS `.p-doc*`.
- **Backend intacto:** los endpoints `/portal/solicitudes/{n}/documentos` y `/solicitudes/{sid}/documentos`
  siguen existiendo (el backoffice ve/descarga la documentación); sólo se sacó la **UI de carga del ciudadano**.
  `api.ts` conserva los métodos (exports sin uso, sin romper tsc).
- **Verificado:** el detalle en el navegador muestra resumen + cronograma y **ya no** "Documentación" ni
  "+ Adjuntar archivo". `test_portal` 18/18 (incluye los tests de documentos, que ejercitan el backend);
  tsc portal OK; candado 100 páginas OK. Datos demo limpiados.

---

## H-130 · Portal: CBU de acreditación + consentimientos obligatorios; CTA visible y responsive
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** siguiente lote del review de UX (H-129)
- **CBU + consentimientos (paso 3 · Confirmación):** para enviar la solicitud ahora se exige el **CBU de
  acreditación (22 dígitos)** y dos consentimientos explícitos: **términos y condiciones** del crédito y
  **tratamiento de datos personales**. `PortalSolicitudIn` sumó `cbu/acepta_terminos/acepta_datos`;
  `enviar_solicitud` valida (422 sin consentimientos o CBU ≠ 22 dígitos) y guarda en `datos_adicionales`
  `cbu` + `consentimiento {terminos, datos, fecha}`. El botón **"Confirmar y enviar solicitud"** queda
  deshabilitado hasta completar CBU (22) + ambos checks (`puedeEnviar`), con texto guía.
- **CTA más a la vista (paso 2 · Simulación):** el cronograma pasó a un `<details>` colapsado
  ("Ver el detalle de las N cuotas") y se agregó una **barra sticky** al pie con la **cuota** y
  **"Continuar →"**, siempre visible sin scrollear el detalle.
- **Responsive:** `html,body{overflow-x:hidden}`, header con `flex-wrap` (la nav baja a fila completa),
  y media queries a 680 px y 400 px. Verificado en 375 px: `innerWidth == documentElement.scrollWidth == 375`
  (sin scroll horizontal), header envuelve.
- **Endurecimiento del input CBU:** el campo acepta **solo dígitos** (descarta letras/símbolos al tipear o
  pegar, vía `onChange` con `replace(/\D/g,"").slice(0,22)`) y **no deja pasar de 22** (`maxLength=22`).
  Verificado en el navegador: tipear letras/símbolos → quedan solo dígitos; tipear 30 dígitos → corta en 22.
- **QA (Postgres):** al reiniciar el backend, el path vivo rechaza el envío sin consentimientos
  (422 "Tenés que aceptar los términos…") y persiste el CBU/consentimiento: `SOL-2026-00005` guardó
  `cbu=2850590940090418135201`, `{"terminos":true,"datos":true,"fecha":"2026-09-09"}`. **Datos demo
  limpiados** (borradas SOL-2026-00001..00005). `test_portal` 18/18; candado 100 páginas OK; tsc portal OK.

---

## H-129 · Portal UX (BBVA/fintech): pre-aprobado por afectación + slider en vivo
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** quick wins del review de UX (BBVA/Ualá/Brubank)
- **Contexto:** review de la solicitud vs. bancos/fintech. Se implementaron los dos quick wins de mayor impacto.
- **Pre-aprobado ('¿cuánto puedo pedir?'):** `POST /portal/pre-aprobado` busca por **bisección sobre el motor
  único** el mayor monto cuya cuota ≤ afectación (%·sueldo, default 30%), redondeado a $1.000; devuelve
  monto_máximo/cuota/afectación. El portal muestra en el paso 2 **"Podés pedir hasta $X · cuota Y (Z% de tu
  sueldo)"** + botón **"Usar el máximo"**. Si ni el mínimo entra en el margen, lo avisa.
- **Slider en vivo:** monto y cuotas pasaron de inputs numéricos a **sliders**; la cuota se **recalcula en vivo**
  (debounce 300 ms) al moverlos, sin apretar "Simular" (se quitó ese botón). Reusa `/portal/simular` (motor único).
- **Verificado en el navegador:** con sueldo declarado, el banner mostró "Podés pedir hasta $2.459.000 · cuota
  $275.958 (30%)"; "Usar el máximo" saltó el slider y la simulación se actualizó sola (cuota = 30% del sueldo).
  `test_portal` 18/18 (pre-aprobado respeta la afectación). Suite **339 passed**; candado 100 páginas OK; tsc OK.
- **Backlog de UX (del review, para más adelante):** un solo número protagonista (cuota) con detalle colapsado;
  destino del crédito; CBU de acreditación; guardar/retomar borrador; tracking visual del expediente;
  consentimientos explícitos; pagar/cancelar la cuota desde el portal; notificaciones push/email/WhatsApp reales.
- **Checkpoint:** snapshot del código en `checkpoints/checkpoint-20260909-1145-H128-portal-completo.tar.gz`
  (estado previo a estos quick wins; restaurar con `tar -xzf`).

---

## H-128 · Portal: "Mis créditos" (préstamo otorgado + estado de cuotas) + notificaciones
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** punto 2 pedido (ver el préstamo y sus cuotas)
- **Qué:** el ciudadano ve los créditos que le otorgaron (originados desde sus solicitudes, vía
  `PPSolicitud.contrato_id`), cómo vienen las cuotas y un feed de notificaciones.
- **Backend (portal, owner-scoped):** `GET /portal/creditos` (tarjetas: producto, saldo, progreso de cuotas,
  próxima cuota, 'En mora' si hay vencidas), `GET /portal/creditos/{contrato}` (detalle con el cronograma y el
  estado por cuota: Pagada/Pendiente/Vencida; 404 para ajenos), `GET /portal/notificaciones` (feed derivado del
  estado: otorgamiento reciente ≤21 días, próximo vencimiento ≤7 días, cuota vencida).
- **Frontend (portal):** nav **Mis créditos** con tarjetas + barra de progreso + detalle en modal con el
  cronograma coloreado por estado; **campana de notificaciones** con contador en el header.
- **Hallazgo de datos (Postgres):** el workflow de **SOLICITUD tenía 2 niveles (ambos ADMG)**; como en producción
  sólo existe el usuario `admin`, **ninguna solicitud podía aprobarse** (el 2º nivel no lo puede firmar el mismo
  que el 1º, cuatro-ojos) — bloqueaba silenciosamente TODO el pipeline de solicitudes (incluidas las del portal).
  Se restauró a **1 nivel** (como el seed) y se limpiaron las aprobaciones parciales trabadas. **Recomendación:**
  no configurar N-ojos con más aprobadores que usuarios reales disponibles; el motor debería avisar si una regla
  es insatisfacible con el padrón actual (posible mejora futura).
- **Verificado:** `test_portal` 17/17 (incluye el circuito completo solicitud→aprobar→originar→el ciudadano ve el
  crédito, cuotas y la notificación 'otorgado'). En el navegador: tarjeta CTO-2026-00018 (Activo, próxima cuota
  $81.826,47), detalle con el cronograma (18 cuotas Pendientes) y la campana con la notificación 'Crédito
  otorgado'. Candado 100 páginas OK; tsc backoffice y portal OK. Datos demo (contrato/asientos/solicitud) limpiados.

---

## H-127 · Provider de haberes (idea #2 del memo) — real + mock, listo para enchufar
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano / Integración · **Alcance:** andamiaje de la mitad pendiente de la idea #2
- **Contexto:** el SSO de Mi Catamarca da sólo identidad (openid/email/profile/phone), no haberes. El API de
  sueldo/antigüedad **aún no existe**. Se dejó todo el andamiaje detrás de una interfaz desacoplada, igual que el
  provider OIDC (`mi_catamarca.py`).
- **Backend:** `app/services/haberes.py` — `HaberesRealProvider` (pega a `HABERES_API_URL` con token, keyed por
  documento; parseo tolerante a nombres) o `MockHaberes` (datos demo deterministas); `get_provider()` elige por
  `haberes_configurado`. Config `haberes_api_url`/`haberes_api_token` por entorno. `GET /portal/haberes` devuelve
  `{disponible, sueldo, antiguedad_meses, segmento, empleador, fuente}`. Se agregó `documento` al token/identidad
  del ciudadano (clave del lookup).
- **Flujo:** el paso 1 del wizard tiene **"Traer mis datos de Mi Catamarca"** → autocompleta sueldo/antigüedad/
  situación y marca **✓ verificados** (o "de demostración" con el mock); si el ciudadano edita a mano, vuelve a
  **declarado**. La solicitud guarda `haberes_fuente` (declarado|micatamarca); el backoffice muestra "sueldo
  verificado ✓ Mi Catamarca" vs "declarado".
- **Enchufar el API real:** setear `HABERES_API_URL`/`HABERES_API_TOKEN` por entorno y ajustar el parseo de la
  respuesta en `HaberesRealProvider.por_documento` al contrato real. Nada más cambia.
- **Verificado:** `test_portal` 16/16 (mock disponible; la solicitud registra la fuente). En el navegador: el
  botón autocompletó Empleado público / 96 meses / $920.000 con la etiqueta "✓ Datos de demostración". Candado
  100 páginas OK; tsc backoffice y portal OK.
- **Cierre idea #2 del memo:** identidad (SSO, H-119) + solicitud online (H-122) + datos/elegibilidad (H-124) +
  documentación (H-126) + haberes (este, tras mock→real). La única dependencia externa restante es que Mi
  Catamarca publique el API de haberes.

---

## H-126 · Portal Fase 3+: documentación adjunta (ciudadano sube, asesor ve)
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano / Solicitudes · **Alcance:** Fase 3+ (una de las dos pendientes)
- **Qué:** el ciudadano adjunta su documentación (DNI frente/dorso, recibo de sueldo, otro) a **su** solicitud
  mientras está EN_EVALUACION, desde el detalle en "Mis solicitudes"; el **asesor la ve y descarga** en el
  backoffice (*Créditos → Solicitudes de crédito*) al evaluar.
- **Backend:** modelo `PPSolicitudDocumento` (bytes en la DB — `bytea`; a escala real iría a object storage,
  anotado). Portal (realm ciudadano, owner-scoped): `POST/GET/DELETE /portal/solicitudes/{numero}/documentos[/{id}]`
  con validación (`app/services/documentos.py`: formatos JPG/PNG/WEBP/PDF, ≤5 MB, ≤10 por solicitud) y auditoría
  del alta. Backoffice (interno): `GET /solicitudes/{sid}/documentos[/{id}]` (list + descarga). Sólo se adjunta/
  quita mientras la solicitud está EN_EVALUACION/BORRADOR (no tras resolverse).
- **Frontend:** portal — sección "Documentación" en el detalle (subir con tipo, listar con tamaño, abrir, quitar);
  descarga autenticada vía fetch→blob (el `<a>` no lleva el token). Backoffice — sección "Documentación del
  solicitante" en el panel de la solicitud con descarga (reusa `abrirArchivo`).
- **Verificado:** `test_portal` 14/14 (subida multipart, listado, descarga con bytes idénticos, descarga interna
  del asesor, validación de formato 422, 404 ajeno, borrado). En el navegador: subí DNI+recibo por API → el
  backoffice los muestra y **descarga 200 OK**; el portal muestra la sección con "+ Adjuntar archivo" y el borrado.
  Candado 100 páginas OK; tsc backoffice y portal OK. Datos demo limpiados.
- **Pendiente Fase 3+:** **haberes automáticos** (sueldo/antigüedad de Mi Catamarca) cuando exista el scope/API —
  hoy el ciudadano los declara.

---

## H-125 · Portal: la solicitud pasa a ser un proceso guiado de 3 pasos (wizard)
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano · **Alcance:** UX (sólo frontend, sin cambios de backend)
- **Qué:** a pedido, la solicitud del ciudadano se reorganizó como un **proceso de 3 pasos** con stepper:
  **1) Tus datos** (situación laboral, edad, antigüedad, sueldo) → **2) Simulación** (elegir producto/monto/plazo,
  ver cuota + elegibilidad + cronograma) → **3) Confirmación** (resumen de todo + "Confirmar y enviar solicitud").
- **Detalles UX:** el stepper marca el paso actual y los completados (✓ verde, clickeables para volver); el paso 1
  exige la situación laboral para continuar; cambiar producto/monto/plazo en el paso 2 **invalida la simulación**
  (un `useEffect` limpia el resultado) y bloquea el paso 3 hasta re-simular; al enviar, el wizard se reinicia y
  salta a "Mis solicitudes".
- **Sin backend nuevo:** reusa `/portal/simular` y `/portal/solicitudes` (Fase 2/3). `portal/src/App.tsx`.
- **Verificado en el navegador de punta a punta:** 1 Tus datos → 2 Simulación (✓ del paso 1 en verde) → 3
  Confirmación (resumen con afectación 7% y "✓ calificás") → "Confirmar y enviar" → SOL en "Mis solicitudes".
  tsc portal OK. Datos demo limpiados.

---

## H-124 · Portal Fase 3: datos del solicitante + elegibilidad + seguimiento
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano / Solicitudes · **Alcance:** Fase 3 (sin depender del API de haberes)
- **Motivación:** cerrar el pendiente de H-122 (la solicitud del portal caía en el backoffice con ELEGIBLE ✕ y
  cuota 0 porque el ciudadano no declaraba segmento/edad/antigüedad, y el canal WEB podía no estar habilitado).
- **Datos del solicitante:** el portal pide **situación laboral** (segmento, con etiquetas amigables →
  AGENTE_PUBLICO/DOCENTE/JUBILADO…), **edad**, **antigüedad (meses)** y **sueldo neto** (opcionales para simular).
- **Elegibilidad + afectación en vivo:** `POST /portal/simular` ahora corre el **mismo `_elegibilidad`** del
  backoffice (disponibilidad del producto vs. datos declarados, canal WEB) y calcula la **afectación** (cuota/
  sueldo). El portal muestra ✓ "calificás" o los **motivos** ("Canal WEB no habilitado", "Segmento no habilitado",
  "Edad máxima 65"…). Puede enviar igual (un asesor revisa). Diagnóstico real: *Personal Flexible* habilita WEB +
  empleados públicos → elegible; *Jubilados* sólo SUCURSAL/CONVENIO → no elegible por el portal (correcto).
- **Envío completo:** la solicitud guarda `segmento/edad/antiguedad_meses` (+ sueldo/afectación en
  `datos_adicionales`) → el backoffice la ve **bien evaluada** (segmento declarado visible en *Solicitudes*).
- **Seguimiento:** `GET /portal/solicitudes/{numero}` (owner-scoped, 404 para ajenas) devuelve estado, datos,
  afectación y el **cronograma estimado**; el portal lo abre en un modal al clickear la fila (con el motivo si
  fue RECHAZADA).
- **Verificado:** `test_portal` 12/12 (elegibilidad con/sin datos, afectación, guardado + detalle, 404 ajeno) y en
  el navegador de punta a punta: ✓ "calificás" en Personal Flexible, motivos claros en Jubilados, y el modal de
  detalle con el cronograma. Suite **333 passed**; candado 100 páginas OK; tsc portal OK. Datos demo limpiados.
- **Pendiente (Fase 3+):** documentación adjunta (subir DNI/recibo — requiere almacenamiento) y **haberes
  automáticos** (traer sueldo/antigüedad de Mi Catamarca cuando exista el scope/API — hoy el ciudadano los declara).

---

## H-123 · Identidad institucional: paleta navy+verde + isologo en backoffice y portal
**Fecha:** 2026-09-09 · **Módulo:** UI (ambas apps) · **Alcance:** branding Caja de Crédito y Prestaciones de Catamarca
- **Qué:** se aplicó la identidad oficial (logo + colores navy `#1e3a5c` / verde `#7cb342`) al backoffice y al
  portal del ciudadano, reemplazando el azul institucional heredado del legacy.
- **Colores por variables de tema (candado):** en `frontend/src/styles.css` se reasignaron los tokens en los 4
  bloques (`:root`, `@media dark`, `[data-theme=light/dark]`): `--brand` = navy, `--brand-2` = verde accesible,
  nuevo `--brand-green` = verde vivo del logo, `--btn-bg`/`--nav` alineados al navy. Los CTA primarios (`.cfgc
  .btn.primary`) pasaron a **navy** (antes verde → texto blanco sin contraste AA); el verde queda para acentos,
  badges "NEW", pills y logo. Portal (`portal/src/App.tsx`): paleta `--p-*` a navy+verde.
- **Isotipo (vector OFICIAL):** el usuario aportó los SVG oficiales (`isotipo-catamarca.svg` + `logotipo-catamarca.svg`,
  colores exactos navy `#1a3258` / verde `#81bc26`). Se **embebieron las paths reales** del isotipo en
  `frontend/src/components/Logo.tsx` y en `PortalLogo` (portal); `onDark` pinta el eslabón navy en blanco sobre el
  riel oscuro. Los tokens de tema se ajustaron a los **hex oficiales** (`#1a3258`/`#81bc26`). Los SVG fuente quedaron
  versionados en `frontend/public/` y `portal/public/`. Reemplaza el placeholder "CC" en el sidebar y en el
  login/header del portal. (Iteración previa: hubo 3 intentos de recrear la forma "a ojo" antes de tener el vector.)
- **Verificado:** en el navegador ambas apps con el isotipo oficial y la paleta (sidebar navy con isotipo blanco+verde,
  botón navy, login del portal con el isotipo a color). Candado 100 páginas OK; tsc backoffice y portal OK.

---

## H-122 · Portal Fase 2: el ciudadano envía la solicitud → Inbox del backoffice
**Fecha:** 2026-09-09 · **Módulo:** Portal ciudadano / Solicitudes · **Alcance:** Fase 2 del portal (memo idea #2)
- **Qué:** el ciudadano, tras simular, **envía su solicitud** desde el portal. Cae en el mismo pipeline pp del
  backoffice (evaluar → aprobar cuatro-ojos → originar contrato). No se duplicó lógica: se reutiliza `PPSolicitud`.
- **Backend** (`app/api/portal.py`):
  - `POST /api/portal/solicitudes` (realm ciudadano): crea una `PPSolicitud` **NO_REGISTRADO** (alta express con
    la identidad de Mi Catamarca: nombre/email) directamente **EN_EVALUACION**, `origen="PORTAL"`, `canal="WEB"`.
    Valida producto **publicado+vigente** y monto/plazo en rango. Marca de dueño `creado_por/enviada_por =
    "portal:<sub>"` para filtrar "mis solicitudes". Guarda en `datos_adicionales` la **cuota que vio al simular**
    (independiente de la elegibilidad del backoffice).
  - **Principios aplicados:** `Idempotency-Key` (doble-clic no duplica), `crear_con_numero_unico` (Nº
    SOL-AAAA-NNNNN único ante concurrencia, la constraint DB es árbitro), auditoría del alta (H-117/118).
  - `GET /api/portal/solicitudes`: sólo las del propio ciudadano (por su marca), estado y cuota estimada.
- **Frontend** (`portal/`): nav **Simular / Mis solicitudes**; CTA **"Solicitar este crédito"** tras la
  simulación (con `crypto.randomUUID()` como Idempotency-Key); pantalla "Mis solicitudes" con pills de estado
  (En evaluación / Aprobada / Otorgada / Rechazada).
- **Handoff verificado en vivo:** enviada SOL-2026-00003 desde el portal (JUAN CARLOS PEREZ, express) →
  aparece en *Créditos → Solicitudes de crédito* del backoffice como **EN_EVALUACION** y en el Inbox (campana).
  La cuota estimada del ciudadano ($56.111,84) se guardó y se muestra en "mis solicitudes".
- **Nota:** en el backoffice la solicitud del portal aparece **ELEGIBLE ✕** porque el ciudadano no declara
  segmento/edad/antigüedad — el asesor completa esos datos al evaluar (queda como pendiente de Fase 3: pedir esos
  datos en el portal o traerlos del API de haberes de Mi Catamarca cuando exista).
- **Verificado:** `test_portal` 9/9 (envío→inbox con cuota>0, idempotencia, mis-solicitudes+realm). Suite verde,
  candado 100 páginas OK, tsc (backoffice y portal) OK. Datos demo limpiados del Postgres.

---

## H-121 · Claridad de versionado en el catálogo: "vigente en portal" (Opción A)
**Fecha:** 2026-09-08 · **Módulo:** Configurar Créditos / Portal · **Alcance:** UX del versionado sin downtime
- **Síntoma reportado:** en el backoffice se veía "un solo publicado" (BADLAR) pero el portal ofrecía 3. No era
  un bug de datos ni de base (es la misma Postgres): la tarjeta del catálogo muestra el estado de la **última
  versión**, mientras que el portal ofrece la **versión publicada y vigente**, que puede ser una anterior.
  Datos reales: Jubilados v2 PUBLICADO (vigente) + v3 EN_REVISION; Personal Flexible v3 PUBLICADO + v4 EN_REVISION.
- **Decisión (Opción A):** mantener el versionado sin downtime (la vN publicada sigue ofreciéndose mientras se
  prepara la vN+1) y **hacerlo visible** en el backoffice.
- **Backend:** helper único `_version_publicada_vigente(prod)` en `productos.py` (sólo PUBLICADO + vigencia hoy,
  sin el fallback de `_version_efectiva`); lo usan el portal y el catálogo. `_serial` agrega `vigentePortal`
  (nro de versión ofrecida en el portal, o null).
- **Frontend:** la tarjeta de *Configurar Créditos* muestra, junto al badge de estado de la última versión, un
  chip **"🌐 portal: vN"** cuando una versión anterior sigue vigente en el portal, o **"no ofrecido"** cuando
  ninguna versión está publicada+vigente. Reusa `pill`/`pill ok` (sin clases nuevas ni hex; candado OK).
- **Verificado:** catálogo devuelve `vigentePortal` correcto (Jubilados→2, Personal Flexible→3, BADLAR→1,
  aprobados/retirado→null); chips vistos en el navegador ("EN REVISIÓN · 🌐 portal: v2", "no ofrecido"). Candado
  100 páginas OK; tsc OK; suite verde.

---

## H-120 · Ajustes del portal: sólo publicado+vigente + TNA variable unificada (motor único real)
**Fecha:** 2026-09-08 · **Módulo:** Portal ciudadano / Product builder · **Alcance:** QA del usuario sobre Fase 1
- **Contexto:** el usuario detectó dos cosas al revisar el portal: (a) debía mostrar sólo productos **publicados
  y vigentes**, y (b) la simulación del portal **difería de la "prueba en vivo"** del backoffice.
- **(a) Sólo publicado + vigente:** `_version_efectiva` tiene un *fallback* que devuelve la última PUBLICADA
  aunque no esté vigente por fecha (sirve a la oferta/originación internas). Para el ciudadano eso es incorrecto.
  Se agregó `_version_publicada_vigente` en `portal.py`: la versión sólo se ofrece si está PUBLICADO **y**
  `vigente_desde ≤ hoy < vigente_hasta`. `/portal/productos` y `/portal/simular` la usan (sin fallback).
- **(b) TNA de tasa variable — causa raíz:** la prueba en vivo y la originación calculan la TNA de una línea
  VARIABLE como **índice + margen**, pero `crear_simulacion` y el portal usaban `_tasa(v,"TNA")` = el default
  fijo (0% en la línea BADLAR) → simulaban a otra tasa. **Fix:** helper único **`_tna_base(db, v)`** en
  `productos.py` (FIJA = tasa_default; VARIABLE = índice+margen), adoptado por **originación, simulación pp y
  portal**. Verificado en vivo: BADLAR pasó de "TNA 0%" a **55%**, y `portal.simular` == `originar` al centavo
  ($1.454.019,63 para 1.000.000 a 12) — simulado == contratado también en tasa variable.
- **Dónde se cambian los estados (consulta del usuario):** en *Créditos → Configurar Créditos*, sobre el detalle
  de la versión: **Enviar a revisión** (BORRADOR→EN_REVISION), **Aprobar/Rechazar** (cuatro-ojos, cadena N-niveles),
  **Publicar** (APROBADO→PUBLICADO, fija vigencia y cierra la anterior) y **Retirar línea** (en el menú ⋮ de la
  fila). Endpoint `POST /productos/{id}/estado` (acciones: revisar/aprobar/rechazar/publicar/retirar/reactivar).
- **Verificado:** `test_portal` — la equivalencia portal == simulación pp interna se corre ahora **para cada
  producto publicado** (incluida la tasa variable). Suite completa en verde.

---

## H-119 · Portal del ciudadano — Fase 1: SSO Mi Catamarca (OIDC) + simulador (motor único)
**Fecha:** 2026-09-08 · **Módulo:** Portal ciudadano (app nueva) · **Alcance:** idea #2 del memo `migra_creditos.pdf`
- **Qué:** primera fase del **portal público** donde el ciudadano se loguea con **Mi Catamarca** y simula su
  crédito, para luego (Fase 2) enviar la solicitud al core. App **separada** (`portal/`, Vite en :5174) sobre el
  **mismo backend y la misma base** — no un segundo sistema.
- **Discovery real verificado** (con navegador; el WAF Cloudflare bloquea bots): issuer/authorize/token/userinfo
  en `https://api-mi.catamarca.gob.ar/openid/*`, Authorization Code, cliente confidencial (`client_secret_post`),
  sin PKCE anunciado. **Scopes = `openid email profile phone` → identidad, NO sueldo/antigüedad** (esa mitad de
  la idea #2 necesita otro scope/API de Mi Catamarca).
- **Backend:**
  - Config `micatamarca_*` (secretos por entorno; `.env`, nunca en el repo). Sin credenciales → **proveedor MOCK**
    determinista (dev/demo/tests), con credenciales → **proveedor real** (`app/services/mi_catamarca.py`).
  - **Realm separado:** `create_portal_token` emite un JWT con `scope="portal"`; dep `get_ciudadano` lo exige y
    `get_current_user` **rechaza** tokens de portal (y viceversa). Segregación probada.
  - Router público `app/api/portal.py`: `/auth/login` → `/auth/callback` (state firmado efímero, intercambio del
    code server-to-server, token en el fragmento `#`), `/me`, `/productos`, `/simular`. **El simulador corre sobre
    los PRODUCTOS PUBLICADOS del product builder (pp_*, versión efectiva) y reusa el mismo `cronograma` que la
    originación → simulado == contratado. NO usa las LineaCredito legacy.** El login del ciudadano se audita (H-117/118).
  - El **`redirect_uri` es el backend** (el SPA nunca ve el authorization code); registrar esa URL en Mi Catamarca.
- **Frontend (`portal/`):** SPA propia (identidad visual pública), login con botón "Ingresar con Mi Catamarca",
  captura del token en `/ingreso#token=`, y simulador (líneas activas + plan de cuotas con formato es-AR).
  Servicio Docker `portal` en :5174 (reusa la imagen del frontend como base → sin pull ni npm install offline).
  CORS del backend ampliado a :5174.
- **Verificado:** suite **327 passed** (incluye `test_portal` 6/6: flujo SSO mock, realms separados, state inválido,
  y **simulador == backoffice** al centavo). Portal probado en navegador de punta a punta (login mock → simulador,
  cuota promedio $47.247,98 / total $566.975,80, sin errores de consola). tsc del portal limpio.
- **Pendiente:** Fase 2 (envío de solicitud → inbox del backoffice) y Fase 3 (seguimiento + haberes automáticos
  cuando exista el scope/API). Operativo: **rotar el `client_secret`** (se compartió en captura), registrar el
  `redirect_uri` y validar conectividad server-to-server del backend con Mi Catamarca pese a Cloudflare.

---

## H-118 · Auditoría de cambios extendida a pagos, cobranza y aprobaciones (completa H-117)
**Fecha:** 2026-09-08 · **Módulo:** Seguridad / Trazabilidad · **Alcance:** cierre del pendiente de H-117
- **Qué:** se extendió el rastro de auditoría (H-117) a las **demás mutaciones que dinamizan dinero o
  autorizan** — las que el memo `migra_creditos.pdf` enumera junto a "aprobar/pagar":
  - **PAGAR** — actividad de servicing del contrato (`contratos.actividad`: PAYMENT/PAYOFF/PARTIAL_PREPAYMENT/
    RATE_CHANGE/…), capturando estado y saldo_capital antes/después.
  - **COBRAR** — cobranza de créditos por caja (`caja.cobrar` y `caja.cobrar_cola`), con nº de recibo y total.
  - **ANULAR** — anulación de recibo (`caja.anular_recibo`), con estado antes/después (de paso el endpoint
    pasó de `_u` anónimo a `user` real para poder atribuir el evento).
  - **APROBAR / RECHAZAR** — workflow cuatro-ojos (`aprobaciones.aprobar_pendiente`/`rechazar_pendiente`),
    incluyendo el paso intermedio de cadena N-niveles (registra nivel aprobado y cuántos faltan).
- **Patrón reutilizado:** mismo `audit.registrar_cambio` (falla en silencio, nunca rompe el negocio) +
  `audit.ip_de(request)`; los rechazos de regla se auditan como RECHAZADO. Sin tocar el motor ni la lógica.
- **Frontend:** el filtro de operación de *Seguridad → Auditoría de cambios* ahora ofrece ALTA/ORIGINAR/PAGAR/
  COBRAR/APROBAR/RECHAZAR/BAJA/ANULAR.
- **Controles de Versión:** proceso `auditoria-cambios` y su verificación actualizados; nuevo caso
  `auditoria-cambio-pago-aprobacion`.
- **Verificado:** `test_auditoria_cambios::test_pago_contrato_deja_auditoria` (cobranza OK deja rastro COBRAR
  con IP 10.20.30.40 y datos_nuevos; la anulación deja rastro ANULAR). Suite completa en verde; candado y tsc OK.

---

## H-117 · Auditoría de cambios del sistema nuevo (antes/después + IP) — idea del memo de migración
**Fecha:** 2026-09-08 · **Módulo:** Seguridad / Trazabilidad · **Alcance:** feature nueva (análisis de `migra_creditos.pdf`)
- **Origen:** análisis del documento `migra_creditos.pdf` (memo de estrategia de migración de créditos) vs.
  nuestro estado. Estamos por delante en casi todo (etapas 1-2-3 ya recorridas, datos reales, motor verificado,
  simulación≠solicitud, revalidación en backend, gate de afectación). El memo aporta 2 ideas incorporables; se
  toma la **#1**: *"para un sistema de créditos, auditoría desde el principio, con antes/después + IP"*.
- **Gap detectado:** el `EventoAuditoria` existente es el **log VFP migrado** (`maquina/usuario/sistema/perfil/
  proceso/opcion`) — guarda sólo el *hecho*. No hay rastro transversal con **diff antes/después, IP ni resultado**
  para las mutaciones del sistema nuevo. (Sí existe trazabilidad de servicing por event-sourcing `pp_actividad`.)
- **Qué se hizo:**
  - **Modelo** `AuditoriaCambio` (tabla `auditoria_cambios`): fecha_hora, usuario, perfil, ip, entidad, entidad_id,
    operacion, resultado (OK/RECHAZADO/ERROR), detalle, `datos_anteriores`/`datos_nuevos`/`cambios` (JSON, portable
    PG/SQLite). Índices en fecha_hora/usuario/entidad/operacion.
  - **Servicio** `services/auditoria.registrar_cambio` (+ `_diff`, `ip_de` con X-Forwarded-For, `consultar_cambios`,
    `obtener_cambio`). El registro **nunca interrumpe el negocio**: ante error propio hace rollback y sigue.
  - **Actor opcional** `deps.get_actor` (usuario/perfil por token si viene, IP siempre) — no lanza 401, así audita
    también endpoints sin sesión como `anonimo`.
  - **Instrumentadas 3 mutaciones sensibles:** alta de solicitud (`creditos.crear_solicitud`), originación
    (`contratos.originar`, incluye el caso "quedó pendiente por workflow" → RECHAZADO) y baja de crédito
    (`creditos.dar_baja_credito`, con estado antes/después). Los rechazos de regla/validación se auditan.
  - **Pantalla** Seguridad → **Auditoría de cambios** (`nuevo:true`): DataTable + filtros (texto/operación/resultado)
    + modal de diff (antes/después con cambios resaltados). CSS scopeado `.audc-*`, pills semánticos.
- **Controles de Versión:** proceso `auditoria-cambios`; casos `auditoria-cambio-alta` / `auditoria-cambio-rechazo`;
  principio `trazabilidad-temporal` extendido; entrada en `MENU_NUEVO`.
- **Verificado:** `test_auditoria_cambios` (3/3): alta OK deja rastro con IP `203.0.113.7` y `datos_nuevos`; alta con
  cliente inexistente queda ERROR; el diff de la baja registra `estado: [antes, "B"]`. Tabla creada en **Postgres**
  con sus índices. Candado de diseño 100 páginas OK; tsc OK.
- **Extensión:** la instrumentación a más mutaciones (pagos/cobranza, aprobaciones de workflow) se completó en
  **H-118**. Queda para evaluar la idea **#2** del memo (proveedor "Mi Catamarca" para traer sueldo/antigüedad
  y no ingresarlos a mano) — decisión del usuario, requiere el contrato real de esa API.

---

## H-116 · Controles de Versión: nueva sección "Procesos de calidad" + actualización de principios
**Fecha:** 2026-08-11 · **Módulo:** Controles de Versión · **Alcance:** documentación viva + QA
- **QA de todo:** suite backend completa en verde, candado de diseño limpio (99 páginas, 3 reglas), tsc limpio.
- **Nueva opción de menú "Procesos de calidad"** (Controles de Versión → Procesos): documenta los **10 procesos/
  mecanismos repetibles** que garantizan la calidad de la migración (no *qué* se construye, sino *cómo se
  garantiza*): candado de diseño, QA profundo, unicidad con la DB como árbitro, idempotencia, contabilidad
  balanceada (before_insert), event-sourcing (reversa única + recompute determinista), equivalencia vs VFP,
  migrador que traduce y verifica antes de tocar, seguridad de arranque, catálogo de casos ejecutable. Cada
  proceso trae descripción + pasos + dónde (archivos) + verificación (test) + referencia (hallazgo).
  Backend `PROCESOS` + `GET /controles-version/procesos`; frontend `Procesos.tsx` (CSS scopeado, badge new).
- **Revisión de staleness (pedido explícito):** se encontró que **6 principios de arquitectura/diseño no
  referenciaban las guardas mecánicas nuevas** — se actualizaron: `tabla-unica` (ahora nota "con candado"),
  `unicidad-concurrente` (extendido a los Nºs legacy H-108 + reversa H-110), `contabilidad-balanceada`
  (guarda before_insert H-109), `cuatro-ojos` (constraint de concurrencia H-107), `event-sourcing`
  (reversa única + determinismo H-110), `idempotency-key` (transiciones H-108). Los casos `dis-candado`,
  `equiv-tipo-calculo`, `css-scopeado` y `theme-aware` ya estaban al día.

---

## H-115 · Roadmap #2 (Tesorería): reimpresión de comprobantes consolidada sobre el buscador de egresos
**Fecha:** 2026-08-11 · **Módulo:** Tesorería / Egresos · **Alcance:** feature nueva (consolida VFP reimp*)
- **Qué:** §5.2 pide unificar las ~6 pantallas VFP de reimpresión (`reimpcreditos`, `reimpseguros`, `reimpvarios`,
  `reimppremios`, `reimpsubs`, `reimpro`) en **un solo visor**. En vez de una pantalla nueva, se agregó la
  acción **"Reimprimir comprobante"** por fila al buscador de egresos existente (`BuscaEgresos`, que ya busca
  los 340k egresos por apellido/cuil/recibo/resolución/OP).
- **Backend:** `GET /egresos/{id}/comprobante-pdf` — carga el egreso, mapea `sub_tipo`→tipo (Crédito/Seguro/
  Premio/Subsidio/Administración/Varios) y arma el PDF con el generador existente `recibo_reimpresion_pdf`
  (cabecera con no_recibo/origen/fecha/titular/total + línea de detalle; marca "ANULADO" si corresponde).
- **Frontend:** acción en el `DataTable` de BuscaEgresos (`api.comprobanteEgresoPdf`), abre el PDF en pestaña.
  Subtítulo actualizado para reflejar la consolidación.
- **Verificado:** endpoint devuelve PDF 200 (2.3 KB) para un egreso real; 404 para inexistente; la acción
  aparece en el menú de fila (probado en el navegador con 1.405 egresos de "PEREZ"). Test
  `test_reimpresion_comprobante_egreso_pdf`. Caso `reimpresion-egresos`.

---

## H-114 · Roadmap #1 (Créditos): nueva pantalla "Resumen de cobros de créditos"
**Fecha:** 2026-08-11 · **Módulo:** Créditos / Reportes · **Alcance:** feature nueva (VFP frm330150000rptcobcre)
- **Qué:** informe de cobranza de créditos por período mensual. Backend `services/consultas.resumen_cobros_creditos`
  + endpoint `GET /creditos/consultas/resumen-cobros` (filtro desde/hasta); frontend `ResumenCobros.tsx`
  (DataTable ordenable, KPIs, formato es-AR, CSS scopeado `.rescob-`, badge `new` en el menú Reportes).
- **Fuente de datos:** la cobranza real de los créditos migrados vive en `cuotas` (fecha_pago + total_pagado +
  desglose), NO en `recibos`/`pagos_cuota` (esos son del sistema nuevo, hoy vacíos) — igual que `pagos-caja`.
  Agrega cuotas pagadas por mes: capital, interés, IVA, seguro, gastos; la **mora se infiere como residual**
  (total pagado − suma de conceptos), porque la data migrada no la separa por cuota.
- **Verificado contra Postgres real:** 116 períodos, 77.567 cuotas pagadas, total histórico ≈ $6.39 mil
  millones cobrados. Test `test_resumen_agrega_por_periodo_y_mora_residual` (agregación por período + mora
  residual + no mezcla meses). Caso `resumen-cobros`. Nota: algunos períodos ("25-11", "202-11") son fechas de
  pago corruptas en la data migrada — el reporte las muestra fielmente; se filtran por rango de fechas.

---

## H-113 · Performance: la DB está bien indexada; el único reporte lento (balance) optimizado
**Fecha:** 2026-08-11 · **Módulo:** Backend / DB · **Alcance:** latencia de reportes
- **Barrido:** N+1 estático (los loops con query son sobre conjuntos chicos —productos/bundles/reglas— bajo
  impacto); índices en las 15 tablas > 100k filas; latencia real de los 6 endpoints de reporte más pesados.
- **La DB ya está bien indexada:** las columnas de búsqueda de las tablas grandes tienen índice (`egresos`
  tiene 10, `movimientos_contables` periodo/cuenta/fecha, `cuotas` credito_id, etc.). Nota: las búsquedas por
  nombre usan `ilike('%x%')` (wildcard inicial) que un btree no aprovecha — un índice `pg_trgm` ayudaría, pero
  es un tradeoff de mantenimiento, no un índice faltante.
- **Único endpoint > 200ms:** `/contabilidad/balance` a **1.0s** (agrega `asientos_lineas`, 2M filas). Los
  demás < 0.17s.
- **Fix seguro aplicado:** el balance hacía `join` a `asientos` **siempre**, aun sin filtro de fecha (el caso
  común) — puro overhead. Se hizo el join **condicional** (sólo con `desde/hasta`). **1.0s → 0.14s** (warm) /
  0.37s (cold); con filtro de fecha 0.009s. Resultados idénticos (sin filtro el inner join no descartaba nada).
  Verificado con los tests de contabilidad. Caso `perf-balance-join`.
- **Decisión semántica tomada (balance = sólo contabilidad de la app):** el balance filtraba también los 2M
  asientos legacy (89k desbalanceados, H-109) → no cuadraba y era lento. Se decidió que el balance de sumas
  y saldos es de la **contabilidad de la app** (doble partida); el mayor plano legacy se ve en el Mayor.
  Fix: `.where(Asiento.origen != 'legacy')` + índice `ix_asientos_origen`. Resultado: **1.0s → 0.035s** y
  ahora **CUADRA** (debe=haber=19.337.272,19; deudor=acreedor). Verificado con los tests de contabilidad.

### Housekeeping
- Cuenta de prueba `test.auditor` **eliminada** (login de prueba sobre data de producción). Memoria IAM
  actualizada (los 187 usuarios migrados quedan con clave `prueba123` para probar el enforcement).

---

## H-112 · Seguridad: la app arrancaba con un JWT_SECRET default (forjable) en cualquier entorno
**Fecha:** 2026-08-11 · **Módulo:** Seguridad / config · **Severidad:** ALTA (bypass de auth en producción mal configurada)
- **Hallazgo (revisión de seguridad del backend):** `core/config.py` tenía `jwt_secret: str = "cambiar-en-produccion"`
  como default. Si un deploy no setea `JWT_SECRET`, se firma/valida con ese secreto **público** (está en el
  código) → cualquiera puede **forjar un token JWT válido** = bypass total de autenticación. El comentario del
  archivo decía "los secretos vienen del entorno" pero el default lo contradecía.
- **Fix:** validador `model_validator` que **impide arrancar** si `environment` no es development/test y el
  `jwt_secret` sigue siendo el default. En dev/test el default se permite (comodidad). Falla ruidoso, no silencioso.
- **Otras verificaciones (OK):** todas las mutaciones tienen auth (routers con `dependencies`; aprobaciones/
  workflow autenticados por-endpoint; `auth` público a propósito). `password_hash` no se expone en ningún
  serializador. La única SQL dinámica (nombres de tabla en `etl/registro.py`) usa un **registro fijo** de
  migradores (no user input) y está admin-gated. No se loguean claves.
- **Verificado:** `test_config_seguridad.py` (producción + default → no arranca; producción + secreto propio → OK;
  development + default → OK). Caso `seg-jwt-secret`.

---

## H-111 · Equivalencia vs VFP: el mapeo `tipo_calculo=2` del motor es Alemán, pero la data real es Francés
**Fecha:** 2026-08-11 · **Módulo:** Motor de cálculo (créditos legacy) · **Severidad:** ALTA (afecta al tipo de crédito dominante)

### Qué se hizo
Comparación del motor nuevo (`domain/cuotas.generar_plan`) contra las **cuotas reales migradas de VFP**
(tabla `cuotas`, 202k filas / 3.136 créditos con plan) en Postgres — la cobertura de equivalencia que
faltaba: el test existente (`test_equivalencia_real`) sólo cubría francés con un fixture chico, pero la
data migrada es **94% tipo_calculo=2** (3.107 créditos).

### Hallazgo (alta confianza, evidencia directa de la data)
- El motor mapea `tipo_calculo=2 → _plan_aleman` (amortización de **capital constante**). La NOTA del propio
  `domain/cuotas.py` ya advertía: *"el mapeo exacto 1..4 → sistema debe confirmarse con datasets reales"*.
- **Discriminador puro de data (sin motor):** de 3.104 créditos tipo2 evaluables, **2.941 (94.7%) tienen
  amortización CRECIENTE** (firma de **francés**: total constante, amortización sube, interés baja) y sólo
  156 (5%) constante. Ej. crédito 149554: total ≈ 2600.9 constante, amort 1053.77→1085.21→1117.59…
- **Confirmación con el motor:** corriendo `generar_plan` como **FRANCÉS** (tipo 1) con el capital de apertura
  y la tasa derivada, reproduce esas cuotas tipo2 **al centavo** (149554: 29/30 cuotas OK; 177955: 24/24).
  amort 1053.77=1053.77, int 1232.88=1232.88, iva 258.90=258.90. El `_plan_frances` del motor ya usa la
  convención exacta de VFP (pago constante **con IVA incluido**, "calibrado contra tmpdev.DBF") — o sea el
  motor está bien; lo que está mal es **a qué rama se rutea el tipo_calculo=2**.

### Impacto
Toda **originación nueva por el flujo legacy** (`POST /creditos/solicitudes/{id}/otorgar` → `generar_plan`)
sobre una línea con `tipo_calculo=2` produce un cronograma **alemán** en vez de **francés** → cuotas,
amortización e interés equivocados. Es el tipo de crédito dominante (94% de la cartera migrada). Los créditos
YA migrados muestran sus cuotas VFP almacenadas (correctas); el bug es para los que se recalculan/originan.

### Veredicto refinado (definitivo): 1 y 2 están INVERTIDOS respecto a VFP
Discriminando por forma de amortización en TODA la data (sin motor): **tipo_calculo=1 → 24/24 créditos
amortización CONSTANTE (Alemán)**; **tipo_calculo=2 → 2941/3104 (94.7%) CRECIENTE (Francés)**. El motor
mapea al revés (`1→francés (default), 2→_plan_aleman`). El test de equivalencia existente pasa porque
*hardcodea* `tipo_calculo=1` para créditos francés — valida la matemática, enmascara el mapeo.

### Radio de impacto: el mapeo errado está cableado en 3 lugares
- `domain/cuotas.py`: `1→francés, 2→alemán, 3→directo`.
- `seed.py`: rotula líneas seed `tipo_calculo=1="Personales (Francés)"`, `=2="AGJS (Alemán)"`.
- `frontend/LineasCredito.tsx`: `SISTEMAS = {1:"Francés", 2:"Alemán", 3:"Directo"…}` (etiqueta de UI).
- **El migrador copia el código VFP verbatim** (`cargar_maestros.py`: `tc = I(x.get("tipo_calcu"))`), sin traducir.

### Dos fixes válidos (decisión de negocio, pendiente)
- **A · Cambiar la convención de la app** para que coincida con VFP (1=Alemán, 2=Francés): swap de ramas en
  el motor + swap de etiquetas UI + seed + actualizar el test de equivalencia. La app adopta los códigos VFP.
- **B · Traducir en el migrador** (recomendable si se prefiere la convención intuitiva 1=Francés): el migrador
  mapea VFP `tipo_calcu` 1↔2 al código de la app, y se corrige el `tipo_calculo` de las `lineas_credito` ya
  migradas. La app conserva 1=Francés; se arregla el dato.
- El 5% "constante" de tipo2 y los tipo 3/4/5 (poca data) requieren más muestras antes de tocar.

### Caracterización completa (mirando amort E interés — corrección de un análisis previo incompleto)
Un primer pase miró sólo la amortización y confundió Directo con Alemán. Verificado con el motor al centavo:
| VFP tipo_calcu | forma (amort / interés) | sistema | app | evidencia |
|---|---|---|---|---|
| **1** | constante / **constante** | **Directo** | 3 | motor Directo 60/60 (Alemán 1/60) |
| **2** | crece / baja | **Francés** | 1 | motor Francés al centavo (149554/177955/110573) |
| **3** | crece / baja (línea 9012) | **Francés** | 1 | 5 créditos, total constante |
| **4, 5** | — sin créditos migrados — | ? | verbatim | no verificable |

**Ningún código VFP en uso mapea a Alemán** (la app tiene la rama, pero la cartera real es Directo + Francés).

### Fix aplicado — Opción B (traducir en el migrador)
- **Migrador** (`etl/cargar_maestros.py`): `VFP_A_APP = {1: 3, 2: 1, 3: 1}` (4/5 verbatim). La app conserva su
  convención (1=Francés, 2=Alemán, 3=Directo); motor/UI/seed sin tocar.
- **Data ya migrada**: `UPDATE lineas_credito` atómico → quedó **311 Francés (tipo1), 81 Directo (tipo3)**,
  0 Alemán, 4/5 intactos.
- **Verificado end-to-end** con el `tipo_calculo` corregido de la línea: Francés 29/30, 24/24, 35/36; Directo
  60/60, 60/60 (los ~1 miss de francés son el ajuste de última cuota). Test regresivo `test_equivalencia_tipo_calculo`
  con fixture real (`fixtures_tipo_calculo_real.json`, 3 Francés + 2 Directo). Caso `equiv-tipo-calculo`.
- **Pendiente (menor):** confirmar el mapeo de tipo 4/5 cuando haya créditos migrados que los usen.

---

## H-110 · Event-sourcing del servicing: reversa idempotente (bug de concurrencia) + recompute determinista
**Fecha:** 2026-08-11 · **Módulo:** Situación del cliente / servicing (Configurar Créditos) · **Alcance:** event-sourcing
- **`_recompute` es correcto (verificado):** es una **función pura** de las actividades no-reversadas — resetea
  las cuotas a los importes **pristinos** del snapshot (`cronograma_pristino`) y re-aplica las actividades en
  orden `(fecha, creado_en)`. Recomputar N veces da el mismo estado. Test `test_recompute_determinista` (3×).
- **Bug de concurrencia (corregido):** `reversar` chequea `if a.estado == "REVERSADA": 409` pero es **TOCTOU**
  (SELECT-then-write). `PPActividad.reversa_de` era sólo FK, **sin unicidad** → dos `reversar` concurrentes de la
  misma actividad crean **dos REVERSAL + dos contra-asientos** = **reversa doble financiera**.
- **Fix (la DB es árbitro, mismo patrón que cuatro-ojos/recibos):** constraint única `uq_pp_actividad_reversa_de`
  sobre `reversa_de` (los NULL —no-reversas— conviven; sólo los no-null son únicos) + índice de arranque. El
  endpoint captura el `IntegrityError` de la carrera y devuelve **409**, no 500. Data verificada sin duplicados
  (pp_actividad 100% del sistema nuevo, 0 reversa_de repetidos).
- **Verificado:** `test_servicing_concurrencia.py` (la DB rechaza la 2ª reversa; recompute determinista) +
  `test_backdating_y_reversa` (reversa→recompute restaura el estado exacto) + 42 tests de contratos verdes.
  Casos `reversa-idempotente`, `recompute-determinista`.
- **Nota menor (no bug):** el tie-break del orden de replay es `(fecha, creado_en)`; dos actividades con idéntico
  timestamp de microsegundo tendrían orden dependiente de la inserción — colisión improbable, sin impacto real.

---

## H-109 · Guarda mecánica del principio "contabilidad balanceada" (Σdebe = Σhaber)
**Fecha:** 2026-08-11 · **Módulo:** Contabilidad · **Alcance:** integridad del libro contable
- **Chequeo de la data primero:** de 1.049.946 asientos, 89.844 están desbalanceados — pero **el 100% son
  `origen='legacy'`** (mayor plano de VFP importado de una sola pierna). Los asientos que genera **la app**
  (doble partida: `pp_otorgamiento` 12, `pp_devengo` 19, `pp_cobranza` 23, `pp_reversa` 2 + otorgamiento/
  cobranza) están **todos balanceados**. El invariante se cumple hoy.
- **Pero no estaba enforced:** los builders en `services/contabilidad.py` balancean por construcción cuidadosa;
  no había ninguna validación en runtime. Un futuro cambio o un bug de redondeo desbalancearía un asiento de
  la app **en silencio** (corrupción del libro).
- **Fix (invariante mecánico, como el candado de diseño y las constraints):** evento SQLAlchemy
  `@event.listens_for(Asiento, "before_insert")` en `models.py` que valida `Σdebe = Σhaber` en cada asiento de
  la app y **falla ruidoso** (`ValueError`) si no balancea. Excluye `origen='legacy'` (una pierna por diseño).
- **Verificado:** `test_contabilidad_balance.py` (app desbalanceado → rechazado al flush; app balanceado → OK;
  legacy de una pierna → permitido) + 68 tests de contabilidad/contratos/caja siguen verdes. Caso
  `contab-balance-guarda`.

---

## H-108 · Auditoría de unicidad/idempotencia: el módulo legacy genera números de negocio sin árbitro DB
**Fecha:** 2026-08-11 · **Módulo:** Caja / Egresos / Juegos / Despacho / Seguros / Mesa · **Alcance:** integridad transaccional

### Hallazgo sistémico (auditoría con subagente, 15 endpoints)
- **Patrón TOCTOU:** los generadores de número de negocio del **módulo legacy migrado de VFP** hacen
  `SELECT max(numero)+1` a nivel aplicación y luego `INSERT` sobre un campo con **sólo `index=True`, sin
  `unique=True`**. Dos requests concurrentes leen el mismo máximo, ambos insertan el mismo número y
  **ninguno falla** → números de **recibo / OP / recibo-quiniela / resolución / póliza / turno duplicados**
  (dinero con identidad repetida). Ninguno usa `crear_con_numero_unico`.
- **El módulo nuevo `pp_*` (Configurar Créditos) SÍ cumple** ambos principios (originar/refinanciar/actividad/
  solicitud/producto usan `crear_con_numero_unico` + `con_idempotencia`). El legacy no.
- **Idempotencia:** sólo 5 endpoints (`pp_*`) leen `Idempotency-Key`. Las altas legacy y las transiciones
  críticas `otorgar`/`desembolsar`/`devengar` no → doble-click puede otorgar dos créditos de una solicitud
  o generar dos asientos de devengo.

### Ranking de riesgo (ALTO = crea dinero sin guarda de DB)
1. `POST /caja/cobrar` · 2. `POST /caja/cola/cobrar` · 3. `POST /creditos/{id}/cancelar` → **Recibo.numero**
4. `POST /egresos/ordenes` → OrdenPago.numero · 5. `POST /juegos/agencias/cobrar` → CajaPagoAgencia.no_recibo
6. `/despacho/resoluciones` · 10. `/productos/{id}/nueva-version` (PPVersion) · 12. `/egresos/autorizaciones`
(AutorizacionOP.nop) · Poliza.numero · 13-14 turnos. **Idempotencia faltante:** 7. `otorgar` · 8. `devengar`
· 9. `desembolsar` · 11. `POST /creditos/solicitudes`.

### Fix aplicado (todas las altas que crean DINERO: recibos, OP, cobranza de quiniela)
- **Recibo.numero → `unique=True`** (modelo) + índice `uq_recibos_numero` en Postgres al arranque. La tabla
  `recibos` está **vacía** y el número es `max+1` global → unique global correcto y seguro.
- Los **3 sitios** de emisión de recibo (`services/caja.py`: cobrar, cola/cobrar, cancelar/payoff) pasan por
  el nuevo helper **`_emitir_recibo`** = `crear_con_numero_unico` (primer-libre + SAVEPOINT + reintento).
- **Frontend (double-submit):** 5 cobros de dinero (`cobrar`, `cobrarCola`, `cobrarAgencia`,
  `cobrarLiquidacion`, `pagarOP`) pasaron de `req` plano a **`postIdem`** (dedup in-flight + Idempotency-Key),
  alineados con `ctoActividadCaja`. El botón "Cobrar" no se deshabilitaba durante el request.
- **Además: `OrdenPago.numero`** (`uq_ordenes_pago_numero`) y **`CajaPagoAgencia.no_recibo`** (quiniela,
  `uq_caja_pagos_agencia_no_recibo`), con la misma técnica. Data verificada **sin duplicados** antes de la
  constraint: ordenes_pago 3.078 filas / caja_pagos_agencia 31.715 filas, ambas 0 dup; número global en las dos.
  Creaciones (`crear_op`, cobranza de agencia) envueltas en `crear_con_numero_unico`.
- **Verificado:** `test_caja_concurrencia.py` (4 tests: la DB rechaza recibo/OP/recibo-agencia duplicado;
  `_emitir_recibo` reintenta con número fresco) + egresos/juegos/caja verdes. Casos `caja-recibo-unico`,
  `op-numero-unico`, `agencia-recibo-unico`.

### Tanda 2 — constraints compuestas (verificando la data VFP primero)
- **Aplicadas (4, data verificada SIN duplicados a su alcance):** Resolución `(anio,tipo,numero)`
  (`uq_resoluciones_anio_tipo_numero`), Póliza `numero` global (`uq_polizas_numero`), Turno de mesa
  `(fecha,numero)` (`uq_turnos_fecha_numero`), PPVersion `(producto_id,numero_version)`
  (`uq_pp_version_producto_numero`). Las 4 generaciones se envolvieron en `crear_con_numero_unico`.
- **NO aplicables — resultaron NO-bugs (números no-únicos por diseño; la identidad es el `id`):** análisis
  de la data lo confirma, no requieren decisión de producto:
  - `AutorizacionOP.nop`: se duplica por (nop, sistema, año) **todos los años, incl. 2026 (4), 2025 (18),
    2024 (24)** → patrón vigente, no data vieja. El nop no es identidad única (VFP lo reusa). `(nop,sistema,fecha)`
    da 0 dup pero es una coincidencia de granularidad, no una regla. **Sin fix**; forzar unicidad rompería
    operaciones legítimas. (El alta `POST /egresos/autorizaciones` no tiene chequeo de dup, y así debe quedar.)
  - `TurnoCredito.numero`: es una **posición de cola repetible** — el mismo (periodo,tipo,numero) se asigna a
    personas distintas en días distintos (y hasta 2 veces el mismo día: 158 dup por (periodo,tipo,numero,fecha)).
    **Sin fix**; no hay unicidad que aplicar.

### Tanda 3 — idempotencia en transiciones críticas
- **`con_idempotencia` agregada a:** `POST /creditos/solicitudes` (alta), `otorgar`, `desembolsar`, `devengar`.
  Un reintento/doble-click con la misma Idempotency-Key no duplica (los 2 de créditos devuelven Pydantic →
  se serializan con `jsonable_encoder` para el store/replay). Frontend: las 5 mutaciones de dinero ya mandan
  la key vía `postIdem`.
- **Verificado:** `test_idempotencia_transiciones.py` (misma key = misma solicitud/crédito; sin key = nueva) +
  `test_resolucion_numero_unico_por_anio_tipo` (compuesta). Casos `num-compuesto-unico`, `idem-transiciones`.

### Cierre
- **H-108 cerrado.** Todas las altas/transiciones que crean o mueven dinero en el legacy tienen ahora a la DB
  como árbitro de unicidad (7 índices) y/o idempotencia (4 endpoints). Los 2 casos que quedaban se investigaron
  a fondo y son **no-bugs** (números no-únicos por diseño), sin acción pendiente.

---

## H-107 · Bug de concurrencia en cuatro-ojos (bypass de N-ojos) + triage de la deuda de tablas
**Fecha:** 2026-08-11 · **Módulo:** Workflow de aprobaciones / Frontend · **Alcance:** control interno + diseño

### Bug crítico (corregido): la cadena de aprobación se podía completar duplicando un nivel
- **Diagnóstico (deep-QA):** `aprobar_paso` calcula el nivel actual como `max(aprobados)+1` e inserta una
  fila en `pp_workflow_aprobacion`, que **no tenía constraint única**. Bajo concurrencia, dos aprobadores
  del nivel 1 leen el mismo estado, ambos insertan una fila nivel-1, y `completo = len(aprobados) >= total`
  marca **completa** una cadena de 2+ niveles **sin que nadie apruebe los niveles superiores** → bypass de
  la separación de funciones (N-ojos), un control interno crítico.
- **Fix (la DB es árbitro):** constraint única `uq_wf_aprobacion_nivel (objeto, objeto_id, nivel_orden)`
  (modelo + índice creado en el arranque, idempotente). `aprobar_paso` captura el `IntegrityError` de la
  carrera y devuelve **409** ("otro aprobador resolvió este nivel, refrescá"), no 500. Los tres callers
  (LINEA/SOLICITUD/pendiente) ya propagan el status.
- **Verificado:** `test_workflow_concurrencia.py` — la 2ª aprobación del mismo nivel la rechaza la DB, y
  `aprobar_paso` devuelve 409 ante la carrera simulada. Sin duplicados previos en Postgres. **295 passed.**
  Caso `wf-concurrencia`.

### Triage de la "deuda de tablas" (31 páginas grandfathered): la etiqueta estaba inflada
- Al ir a migrar las 31 `<table>` crudas a `DataTable`, se encontró que **la mayoría NO son grillas CRUD**
  sino **layouts de reporte/contables** (LibroDiario=asientos, Balance, PlanillaContable, PremiosCompensados
  agrupado por interior, TableroCartera, PorCartera…), **wizards/herramientas** (Originar, Configurar,
  Simulador, Recálculo) o **mini-tablas de preview** (TurnosAdmin). `DataTable` (para ABM/maestros, modelo
  Maestro de clientes) es la herramienta equivocada para esos casos — forzarla los empeoraría.
- **Los ABM reales ya usan `DataTable`** (Clientes, Usuarios, Roles, Grupos, Líneas).
- **Migradas las 3 grillas planas server-paginated** a `DataTable`, verificadas en vivo contra Postgres:
  `AutorizacionesOP` (9 cols, "1–25 de 25.433", pager avanza a 26–50), `BuscaEgresos` (13 cols + rowStyle
  para anulados, "1–100 de 1.405"), `ContabilidadGeneral` (11 cols, "1–100 de 106.557"). Allowlist **31 → 28**.
- **Clasificación de las 28 restantes (todas custom legítimo, NO deuda):** 12 reportes con footer de totales
  (LibroDiario, Balance, PlanillaContable, TableroCartera, ReporteOP…) que DataTable no representa; 5
  cronogramas/proyecciones financieras (Originar, CajaCreditos, SituacionCliente…); 3 agrupados (Polizas,
  ChequesEmitidos, PremiosCompensados); 4 de referencia/doc (Vision360, ModeloDatos, Migradores, Configurar);
  4 interactivas/preview (SolicitudesCredito master-detail, Anexos multi-select, TurnosAdmin, Feriados).
  `SolicitudesCredito` es la única candidata futura (master-detail), pero migrarla cambiaría su interacción.

---

## H-106 · Candado de diseño: 3ª regla «CSS scopeado por pantalla» (preventiva, lección H-083)
**Fecha:** 2026-08-11 · **Módulo:** Frontend / gobierno de diseño · **Alcance:** enforcement
- Se sumó al `check-diseno.mjs` (+ hook) una **3ª regla mecánica**: una página no puede DEFINIR una clase
  genérica *bare* (una palabra, sin prefijo de scope — `.card`, `.row`, `.cell`, `.header`…) en su `<style>`,
  porque pisa esa clase en toda la app. Es la lección de **H-083** (el calendario de feriados se deformó por
  una clase `.fer` compartida) encapsulada mecánicamente. Denylist de ~70 palabras genéricas; se ignoran las
  clases prefijadas (`.fer-cell`, `.pa-row`, `.tcar-dot`) y los selectores multi-clase/descendientes.
- **Medición previa: 0 violaciones** — la app ya prefija todas sus clases; la regla es **100% preventiva**
  (sin deuda que grandfatherear). Allowlist `diseno-allow-clases.txt` creado vacío por simetría.
- **Demostrado:** una página de prueba con `.card{…}` bare → hook `exit 2` (bloquea); `.foo-ok` (con guion)
  pasa. Escaneo final limpio: **97 páginas, 3 reglas**. Caso `dis-candado` (ahora 3 reglas) y principio
  `css-scopeado` marcados como *con candado*.
- **Estado del candado:** de 1 → **3 reglas mecánicas** (tabla única · color por tema · CSS scopeado),
  cubriendo los 3 principios de diseño que más se rompían o más caro costó romper (H-083).

---

## H-105 · Candado de diseño extendido a «color por variable de tema» (2ª regla mecánica)
**Fecha:** 2026-08-11 · **Módulo:** Frontend / gobierno de diseño · **Alcance:** enforcement
- Se sumó al `check-diseno.mjs` (+ hook PostToolUse) una **segunda regla dura**: una página no puede usar
  **hex cromático fijo** en estilos — los colores salen de variables de tema (`--ok/--warn/--crit/--brand-2`
  y sus `*-soft`, `--surface`, `--ink…`). Se permiten `#fff`/`#000` (house style: texto sobre brand, sombras)
  y los hex dentro de `var(--x, #hex)` (fallback). Escapes iguales que la regla de tablas: comentario
  `diseño-ok:` o allowlist `diseno-allow-colores.txt`.
- **Medición reveló deuda mayor a la estimada:** no eran 5 páginas sino **34** con hex cromático (grises
  `#555/#888`, rojo `#c0392b`, verdes `#1d7a3f/#eaf7ef`, y paletas de data-viz en Feriados/Tablero/Quiniela).
- **Barrido a tokens (61 reemplazos en 30 páginas):** grises→`--ink-soft/--ink-faint`, verdes→`--ok(-soft)`,
  rojos→`--crit(-soft)`, ámbar→`--warn(-soft)`, azules→`--brand-2`, bg neutro→`--surface-2`. Se **excluyeron
  las 4 páginas de data-viz** (Tablero, Feriados, ControlesVersion, Quiniela) donde el hex es paleta
  categórica legítima — quedan como único grandfathered. Deuda **34 → 4**.
- **Verificado en vivo** (Docker relevantado con `open -a Docker`): scanner limpio (97 páginas, 2 reglas),
  tsc OK, y los tokens resuelven a color real y **theme-adaptive** — probado en `Perfiles.tsx`: `.pa-new`
  = verde `--ok`, bordes de nivel consulta/escritura/total = `--brand-2`/`--warn`/`--ok` (valores del tema
  oscuro activo: #7fb0ff/#e0975a/#57c48a). El swap además **arregla el dark mode** que los hex fijos rompían.
- **Data-viz migrado también (deuda 4 → 0):** se definió una **paleta categórica de tema `--dv-*`**
  (blue/green/amber/orange/red/purple/teal/slate) con variantes light+dark en los 4 bloques de
  `styles.css`, y se cablearon las 3 páginas con paletas reales (Feriados=tipos, TableroCartera=estados,
  ControlesVersion=grupos) a `var(--dv-*)`. `AplicativoQuiniela` estaba mal clasificada: sus colores eran
  **semánticos** (positivo/negativo) → `--ok`/`--crit`. **Allowlist de colores vacío**: toda la app usa
  variables. Verificado en vivo que los puntos del Tablero resuelven a la paleta dark (#57c48a/#7fb0ff/
  #9aa7bd) y cambian a la light (#1a7f4b/#2f64c8/#64748b) al togglear tema.
- **Referencia de "cómo se hace bien":** `Perfiles.tsx` (semántico) y `TableroCartera`/`Feriados` (paleta
  `--dv-*`). Caso `dis-candado` actualizado y principio `theme-aware` marcado como *con candado*.

---

## H-104 · QA profundo Usuarios/Roles/Grupos: asignación aditiva + unicidad de rol como árbitro DB
**Fecha:** 2026-08-11 · **Módulo:** Seguridad · **Alcance:** integridad del RBAC/IAM
- **QA en vivo contra Postgres** (34+ chequeos sobre las tres pantallas): validaciones de alta (código/
  clave/duplicados), candados de baja (self-baja, último admin), permisos por pantalla (nivel inválido,
  ruta inválida, NINGUNO borra, bulk), vigencias, y resolución de acceso efectivo punta a punta
  (usuario con rol principal + grupo→roles + permiso directo = unión correcta con nivel máximo). Todo verde.
- **Bug de datos (corregido):** "Asignar usuarios a un rol" desde la pantalla de Roles **pisaba el rol
  principal** del usuario y **perdía el anterior** (un XCR asignado a otro rol quedaba sin XCR). En un
  modelo multi-rol es incorrecto. Ahora es **aditivo**: suma el rol como adicional (`usuario_perfil`) sin
  tocar el principal; es idempotente; la lista de **Miembros** y el **conteo** del rol pasan a ser la
  **unión** (principal + adicional) con flag ★/adicional; el **borrado de rol** se bloquea si es principal
  o adicional de alguien, o si está incluido en un grupo. UI actualizada ("Sumar el rol X a usuarios…").
- **Unicidad concurrente (principio de arquitectura):** `perfiles.codigo` no tenía **constraint única**
  (sólo índice), a diferencia de `usuarios`/`grupo` — el chequeo de duplicado era sólo TOCTOU aplicativo.
  Se agregó `unique=True` + índice `uq_perfiles_codigo` (creado en el arranque, idempotente). Además las
  altas de **rol/grupo/usuario** ahora traducen la violación de unicidad de la DB (carrera real) a **409**
  (`_commit_unico`), no 500 — la DB es el árbitro.
- **Verificado:** tests `test_iam_asignar_rol_es_aditivo`, `test_iam_borrar_rol_bloqueado_por_grupo`,
  `test_iam_rol_codigo_unico` (+ los 3 previos) → **293 passed**. Datos demo `ZQA*` limpiados de Postgres.

---

## H-103 · Fase 4 IAM + editor de Usuario en pestañas + revisión UX del acceso
**Fecha:** 2026-08-11 · **Módulo:** Seguridad · **Alcance:** UX del control de accesos
- **Fase 4 (permisos directos por UI):** el editor de Usuario ahora permite otorgar/quitar un permiso
  directo sobre una pantalla (nivel CONSULTA/ESCRITURA/TOTAL, con vigencia desde/hasta) — el backend ya
  resolvía `usuario_permiso`, faltaba la pantalla. Endpoints `POST/DELETE /admin/usuarios/{id}/permisos-directos`
  (nivel NINGUNO borra; ruta inválida → 422). Verificado contra Postgres: se persiste en `usuario_permiso`,
  aparece en "acceso efectivo" y el botón **Quitar** lo elimina (0 filas). Caso `iam-permiso-directo` (auto).
- **Editor de Usuario rediseñado en pestañas** (Roles · Grupos · Permisos directos · Acceso efectivo · Datos),
  reemplaza el modal apilado que crecía sin límite. Cada solapa tiene su ayuda contextual; ★ = rol principal.
  El alta queda en un modal simple (usuario/nombre/clave/rol principal) y el detalle IAM sólo al editar.
- **Hallazgos UX corregidos en la revisión funcional:**
  1. **Rutas duplicadas** en el menú (`/contabilidad/cierre`, `/caja/control` aparecen 2 veces por alias de
     reimpresión) generaban *keys* duplicadas en el `<select>` de pantallas → se **deduplica** `PANTALLAS` por ruta.
  2. **Terminología inconsistente** "perfil" vs "rol": botón "Nuevo perfil", "bundle de permisos", "Editar {código}"
     → unificado a **rol** en Roles, Usuarios y Grupos ("Nuevo rol", "conjunto de permisos", "Editar rol X").
  3. **Anglicismos** en subtítulos ("Bundles de roles") → "Conjuntos de roles"; pluralización "1 grupos" → "1 grupo".
  4. **ADMG confuso**: su grilla de permisos mostraba "0/18 con acceso" en varios módulos pese a tener bypass total
     → banner **"Acceso irrestricto"** en el panel de acceso del rol ADMG.
- **Limpieza de datos demo:** se borró el permiso directo de prueba en `test.auditor` y el grupo demo `PRUEBA/TI`
  (0 miembros) que habían quedado de mocks previos.

---

## H-102 · Rediseño IAM: Usuario → Grupo → Rol → Permiso con grants directos y vigencia
**Fecha:** 2026-08-10 · **Módulo:** Seguridad · **Alcance:** modelo de accesos
- **Modelo objetivo** (pedido por el usuario): Usuario pertenece a Grupos → cada Grupo tiene Roles →
  cada Rol tiene Permisos; además el usuario puede tener roles y permisos DIRECTOS; todo con **vigencia**
  (desde/hasta) para cubrir licencias/vacaciones que se apagan solas.
- **Migración aditiva** (no reescritura): Perfil=Rol, perfil_permiso=rol_permiso, usuario_perfil=usuario_rol.
  Tablas nuevas `grupo`, `grupo_rol`, `usuario_grupo`, `usuario_permiso`; vigencia agregada a usuario_perfil
  (ALTER Postgres en startup, guardado por dialecto).
- **Resolución** (`app/core/permisos.py`): acceso efectivo = **unión** de roles directos + roles heredados
  de grupos + permisos directos, con **nivel máximo** por pantalla y **filtro por vigencia**. `mis-permisos`
  y `requiere_permiso` ya lo consumen; el enforcement (menú/rutas/botones) no cambió.
- **UI**: pantalla **Grupos** (ABM + asignar roles), editor de **Usuario** con grupos + vigencia + vista de
  **acceso efectivo**; **'Perfiles' → 'Roles'** en el menú. Decisiones: vigencia sólo en asignaciones del
  usuario, workflow por rol principal.
- **Verificado**: tests `test_iam.py` (cadena grupo→rol→permiso, vigencia que vence, borrar grupo en uso) +
  contra Postgres real (un usuario XCR heredó Clientes+Seguros sólo por pertenecer a un grupo con el rol AUGR).
  Casos `iam-cadena`, `iam-vigencia`, `iam-grupos-ui`. Diseño en `salida/diseno-iam.md`.
- **Fase 4 completada** en H-103: UI de **permisos directos** al usuario.

---

## H-101 · QA intenso de Usuarios y Perfiles: 9 validaciones/candados faltantes
**Fecha:** 2026-08-10 · **Módulo:** Seguridad → Usuarios / Perfiles · **Hallado por:** QA agresivo (pytest + navegador)
El QA de edge cases encontró 9 huecos, todos corregidos:
- **Usuarios:** se aceptaba **password vacío** y **corto** (<6), **username vacío**, y **reset de clave vacío**
  → ahora 422 con mensaje. Se podía **darse de baja a uno mismo** y **dar de baja al último admin activo**
  (lockout total) → ahora 409. (OK previo: un usuario dado de baja no puede loguear; reactivar lo restaura.)
- **Perfiles:** se aceptaba **código > 6 chars** (columna varchar(6)) → 422. Un **perfil deshabilitado NO
  bloqueaba** a sus usuarios → ahora el login de un perfil con maeperfil.habilitado=false devuelve 403.
  **Ruta de permiso malformada** (vacía / sin '/') → 422. (OK previo: borrar un perfil cascadea sus permisos.)
- Verificado contra Postgres real (mensajes claros en los forms). Tests `test_qa_usuarios_perfiles.py` (11);
  casos `qa-usuarios-validacion`, `qa-perfiles-validacion`.
- **Observación de dato (no bug):** los usuarios reales usan ~43 códigos de perfil (UJU1, SCRG…) que en su
  mayoría NO están en el maestro maeperfil (19 códigos). El RBAC se configura por perfil de maeperfil; para
  gobernar a esos usuarios hay que **reasignarlos** a un perfil del maestro (herramienta 'Asignar usuarios').

---

## H-100 · Motor de workflow de aprobaciones configurable (Seguridad → Workflow)
**Fecha:** 2026-08-10 · **Módulo:** Seguridad (nuevo) · **Principio:** cuatro-ojos (ahora configurable)
- **Qué:** herramienta para configurar el cuatro-ojos / **N-ojos en serie** por tipo de objeto. Antes el
  cuatro-ojos estaba hardcodeado (rol ADMG, 1 aprobador); ahora es una regla editable.
- **Modelo** (`pp_workflow_regla` / `_nivel` / `_nivel_usuario`): una regla por objeto (LINEA, SOLICITUD,
  DESEMBOLSO, REFINANCIACION); N **niveles en serie**; cada nivel aprueba un **rol** base con **cuatro-ojos**
  on/off y **overrides por usuario** (INCLUIR/EXCLUIR). Seed idempotente replica el comportamiento actual
  (LINEA/SOLICITUD activas 1 nivel ADMG; DESEMBOLSO/REFINANCIACION inactivas).
- **Evaluador** `app/services/workflow.py` `puede_aprobar(objeto, user, actores)` → (ok, status, motivo):
  precedencia **rol → 403**, luego **cuatro-ojos → 409**. Enganchado en la aprobación de **líneas** y
  **solicitudes** (reemplaza el chequeo hardcodeado; mismo comportamiento por defecto).
- **UI** en **Seguridad → Workflow de aprobaciones** (badge new, `/seguridad/workflow`): activar/desactivar,
  editar niveles (nombre/rol/cuatro-ojos), agregar niveles en serie, y overrides de usuario. Sólo ADMG edita.
- **Verificación:** 34/34 live (caso `wf-reglas`); `test_workflow_config_cambia_quien_aprueba` prueba que un
  override INCLUIR habilita a 'creditos' (perfil XCR) a aprobar y que un no-admin no configura (403); los
  tests de cuatro-ojos existentes siguen verdes.
- **Fase 2 (entregada — cadena N-niveles):** `pp_workflow_aprobacion` registra cada aprobación por
  instancia; `workflow.aprobar_paso/progreso/limpiar_aprobaciones` ejecutan la **cadena en serie**:
  con 2+ niveles, la 1ª aprobación NO cierra (sigue EN_REVISION) y recién la última pasa a
  APROBADO/APROBADA. Enganchado en **líneas** y **solicitudes** (rechazar/reenviar reinicia la cadena).
  El **Inbox** ahora es multinivel: muestra cada objeto en su **nivel actual** sólo a los aprobadores
  elegibles de ese nivel ("Nivel k de N"). **UI:** builder visual (Seguridad → Workflow) con lienzo
  disparador → niveles en serie → fin + panel de configuración. Test `test_workflow_cadena_n_niveles`,
  caso `wf-cadena`.
- **Fase 2b (entregada — gates de desembolso/refinanciación):** con la regla del objeto activa, la
  acción NO ejecuta: crea un `pp_workflow_pendiente` (request→aprobar→ejecutar). El pendiente aparece
  en el **Inbox** del aprobador del nivel (no del emisor) y suma al **badge de la campana**; se aprueba
  **inline** desde el propio Inbox (botones Aprobar/Rechazar). Al completar la cadena, se ejecuta la
  operación real (desembolso o refinanciación). Endpoints `/aprobaciones/pendientes/{id}/aprobar|rechazar`.
  Por defecto las reglas DESEMBOLSO/REFINANCIACIÓN quedan **inactivas** (flujo directo intacto); se
  activan en Seguridad → Workflow. Test `test_gate_desembolso_pendiente_y_aprobacion`, caso
  `wf-gate-desembolso`. Suite 269 passed.

## H-099 · QA de Configurar Créditos: config sin validar al guardar + borrado que rompe con 500
**Fecha:** 2026-08-10 · **Módulo:** Créditos → Configurar Créditos · **Hallado por:** QA de navegador (nuevo criterio)
- **Bug 1 — el editor guardaba configuraciones inválidas (200):** `PUT /productos/{id}/config` no validaba
  nada. Se persistían `montoMin > montoMax`, `plazoMin > plazoMax` y **TNA negativa**. Peor: `publicar`
  sólo chequeaba montos/plazos, **no la TNA negativa**, así que una tasa negativa podía llegar a PUBLICADO.
  **Fix:** `_validar_cfg` en el guardado (422 ante contradicciones/negativos, tolerando borradores
  incompletos con ceros) + `publicar` ahora también rechaza TNA/mora negativa y mín. no positivos.
- **Bug 2 — borrar una línea referenciada tiraba 500:** `borrar` hacía `db.delete(prod)` sin chequear
  referencias; si la línea era **padre** de otra (`padre_id` FK) o tenía **contratos** (`producto_id` FK),
  el commit reventaba con `IntegrityError` crudo (500). **Fix:** guardas explícitas → **409** con mensaje
  ("tiene N derivadas / N contratos") + red de seguridad try/except IntegrityError → 409.
- **Observación (no bug, lleva al workflow):** con un solo usuario (admin) el cuatro-ojos **bloquea** el
  circuito — admin envía a revisión y no puede aprobar lo propio, así que no se puede publicar desde la
  app. Correcto por diseño, pero muestra la necesidad de configurar aprobadores (herramienta de workflow).
- **Verificación:** contra Postgres real (min>max → 422, TNA<0 → 422, válida → 200; borrar padre → 409).
  Tests `test_guardar_config_rechaza_invalidos`, `test_borrar_linea_con_referencias_da_409`. Casos
  `cfg-valida-guardar`, `cfg-borrar-ref`. Datos demo eliminados.

## H-098 · Idempotency-key implementada en las altas mutantes (evitar duplicados por reintento/doble clic)
**Fecha:** 2026-08-10 · **Módulo:** Créditos (altas mutantes) · **Principio:** idempotency-key
- **Qué:** las altas mutantes aceptan un header `Idempotency-Key`. Si llega dos veces la misma clave
  (doble clic, retry de red), se devuelve el **mismo** resultado y **no** se crea un segundo registro.
  Distinto de la unicidad del número (que evita ids repetidos): esto dedup-lica la **operación**.
- **Dónde (barrido de lo nuevo):** `POST /api/productos` (línea), `POST /api/solicitudes`,
  `POST /api/contratos/originar`, `POST /api/contratos/{id}/refinanciar` y
  `POST /api/contratos/{id}/actividad` (**servicing/pago — el más sensible: no pagar dos veces**).
  No aplicado a Feriados/Impuestos/Índices (ya rechazan duplicados con 409) ni a desembolsar
  (guardado por estado). Helper `app/core/idempotency.py` + tabla `pp_idempotencia` (reserva la clave
  con su PK única — mismo criterio de árbitro que la unicidad concurrente; libera la reserva si la
  operación falla, para poder reintentar).
- **Front:** helper `postIdem` en `api.ts` manda la `Idempotency-Key` y **dedup-lica el doble clic**
  (reusa promesa+clave para envíos idénticos en vuelo). Cableado en las 5 altas.
- **Verificación:** contra Postgres real, `POST /solicitudes` x2 con la misma clave → mismo
  `SOL-2026-00001`, **1 sola fila**; clave distinta → `00002`. Tests `test_idempotency_key_no_duplica_altas`
  (solicitud + pago no se duplica). Caso `idem-key`. Principio marcado **IMPLEMENTADO**.

## H-097 · Bug: "Crear y diseñar" en Configurar Créditos daba Error 500 (código de línea duplicado)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → Configurar Créditos (`POST /api/productos`) · **Hallado por:** QA de navegador (reporte del usuario)
- **Síntoma:** en Configurar Créditos, "＋ Nueva línea" → "Crear y diseñar" devolvía **Error 500**.
- **Causa raíz:** el código de la línea se generaba como `LP-NUEVA-{count(productos)+1:02d}`. Como la
  constraint `pp_producto_codigo_key` es **única** y el sufijo salía del **total de productos** (no del
  máximo libre), al haber huecos por líneas creadas/borradas antes el código colisionaba
  (`duplicate key value violates unique constraint … Key (codigo)=(LP-NUEVA-09) already exists`).
- **Fix:** se genera el **primer `LP-NUEVA-NN` libre** consultando los códigos existentes
  (`app/api/productos.py`, endpoint `crear`), garantizando unicidad sin importar los huecos.
- **Por qué no lo cazó el QA previo:** los tests corren en SQLite con base **vacía**, donde el sufijo por
  `count()` nunca colisiona; el bug sólo aparece contra una base con líneas `LP-NUEVA-*` ya presentes
  (Postgres de producción). **Regresión agregada:** `test_crear_linea_no_colisiona_codigo` **siembra**
  el código que la vieja lógica elegiría (forzando la colisión) y verifica que crear no rompa y que dos
  creaciones den códigos distintos. Verificado en el navegador contra Postgres real: `POST → 201`.
  Dato demo creado en la verificación **eliminado** (línea `QA Verificación Fix`).
- **Barrido de hermanos (nuevo criterio de QA: revisar todas las altas contra dato real):** el mismo patrón
  `count()+1` para generar identificadores únicos estaba en **dos lugares más**, ambos corregidos al
  "primer libre por prefijo": `numero_contrato` (`CTO-AAAA-NNNNN`) en **originar** y **refinanciar**
  (`app/api/contratos.py`, helper `_proximo_numero_contrato`), y `numero` de solicitud (`SOL-AAAA-NNNNN`)
  en **Solicitudes** (`app/api/solicitudes.py`, `_numero`). Regresiones: `test_originar_no_colisiona_numero_contrato`
  y `test_solicitud_no_colisiona_numero` (fuerzan el hueco borrando una fila). **Feriados / Impuestos / Índices**
  ya resolvían el duplicado con **409** (no 500), OK. Los `max()+1` de juegos/egresos/seguros son seguros
  (no reusan números) y quedan como están. Altas verificadas desde la app contra Postgres real
  (Solicitudes → `SOL-2026-00001/02/03`, 201, únicas; datos demo eliminados).
- **Concurrencia multi-usuario (TOCTOU):** "primer libre" por sí solo NO alcanza — dos usuarios calculan
  el mismo número y el 2º INSERT choca con la constraint (500). **Fix definitivo:** `crear_con_numero_unico`
  (`app/core/numbering.py`): cada intento va en un **SAVEPOINT** y fuerza el INSERT; ante `IntegrityError`
  (otro request tomó el número) revierte sólo el savepoint y **reintenta** con un número fresco. La base es
  el árbitro (no hay lock aplicativo). Aplicado a **línea, originar, refinanciar y solicitud**. Regresión
  `test_numbering_reintenta_ante_colision_concurrente` (fuerza la carrera) + verificación en vivo contra
  Postgres: **10 altas de solicitud en paralelo → 10/10 201, cero 500, 10 números únicos**. Nota: esto da
  unicidad e idempotencia del *número*; la idempotencia de *operación* (mismo request duplicado por doble
  clic/retry) es otra cosa y requeriría una **idempotency-key** explícita — hoy dos requests iguales crean
  dos registros distintos (a veces correcto: un cliente puede tener dos solicitudes/contratos).

## H-083 · Maestro de feriados + regresión en Controles de Versión + badge "new"
**Fecha:** 2026-08-07 · **Módulo:** Contabilidad (nuevo maestro) / Controles de Versión / Sidebar
- **Regresión (lo pedido):** los tests de caza de bugs ahora **se registran en Controles de Versión**
  para regresión. Se sumaron casos: `cfg-vigencia`, `ori-piso` (auto), `calc-feriado`, `sc-catalogo`,
  `sc-debug`, `mae-feriados` (live), `mae-feriados-motor` (auto). Catálogo: **46 casos (30 live)**. De acá
  en más, cada bug encontrado suma su caso.
- **Badge "new" en el menú:** las opciones creadas en la migración muestran un pill verde **new** a la
  izquierda del nombre (Configurar Créditos, Originar, Sistema de cálculos, Impuestos, Índices, Feriados,
  y todo Controles de Versión). Flag `nuevo: true` en el ítem del Sidebar.
- **Maestro de feriados (nuevo):** `Contabilidad → Feriados` (`/contabilidad/feriados`), tabla `feriados`
  (pais ISO-2, fecha, nombre, tipo, origen, activo; único por país+fecha). Configurable **por país**
  (AR/UY/CL/BR/MX/ES). Se puede **cargar/editar/borrar manualmente** o **importar de fuente oficial**
  (Nager.Date, `date.nager.at`) con **respaldo calculado** si la fuente no responde (fijos + Carnaval/Viernes
  Santo vía algoritmo de Pascua para AR). Seed idempotente del calendario AR (año actual + 2). El maestro
  **alimenta el motor**: `_feriados_engine(db)` inyecta el set en `cronograma` vía `_params_cronograma`
  en preview, originación y simulación, así los vencimientos no caen en feriado cuando el producto ajusta a
  día hábil. **UX:** toggle **Tabla/Calendario**, tabla **ordenable** por columnas, y vista **calendario anual**
  (12 meses, feriados resaltados). Tests `test_feriados.py` (5). Pendiente previo (maestro de feriados)
  **cerrado**.

## H-096 · Bug: el prepago perdía un pago parcial previo de la cuota (hallado por QA de navegador)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing / Caja
Recorriendo el proceso **desde la aplicación** (wizard Originar → Caja): tras un **pago parcial** de una cuota,
aplicar un **prepago** dejaba la cuota con `pagado = 0` — el abono parcial del cliente **se perdía**. Causa:
`_aplicar_prepago` reseteaba `q.pagado = Decimal(0)` al regenerar las cuotas. **Fix:** al regenerar se
**preserva el abono acumulado** (`pagado`) y la cuota se marca PAGADA sólo si el abono ya cubre el nuevo total.
Verificado por UI (el $40.000 reaparece) y test `test_prepago_no_pierde_pago_parcial_previo`; caso CV
`ori-prepago-parcial`. QA de navegador (Originar + Caja) recorrido completo: otorgar→desembolsar→cobrar cuota/
parcial/prepago/adelanto con recibo + asiento — todo OK salvo este bug, ya corregido.

## H-095 · QA de operaciones combinadas (punta a punta, con reversa idempotente)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing (QA end-to-end)
Test de proceso completo con operaciones **entremezcladas** en un mismo préstamo: pago normal + pago parcial +
pago con **mora (backdating)** + **prepago** (baja cuota) + **diferimiento** + **reversas** + **adelanto** de N
cuotas + **payoff**, verificando invariantes en cada paso (asientos balanceados, `saldo = Σcapital pendiente`,
sin importes negativos) y la **idempotencia de la reversa** (revertir el diferimiento devuelve el estado exacto
previo; revertir el prepago restaura cuotas y saldo). Test `test_operaciones_combinadas_y_reversa`; caso CV
`ciclo-combinado`.
**Nota metodológica:** el probe directo con `db.commit = db.flush` (monkeypatch para no persistir) da falsos
positivos en secuencias multi-actividad porque `_recompute` + reset-a-pristino dependen de commits reales entre
actividades. El QA correcto va por el **path HTTP real** (TestClient), que sí commitea cada actividad. No era un
bug del código: el proceso real funciona.

## H-094 · Adelanto de N cuotas + QA de ciclo de vida (2 bugs corregidos)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing (QA end-to-end)
- **Adelanto de N cuotas** (`PAYMENT` con `cuotas: N`): registra N pagos completos (uno por cuota, cada uno con
  su mora y asiento); el saldo baja por el capital de las N. Botón "Adelantar cuotas" en la Caja. Test
  `test_adelanto_de_n_cuotas`.
- **QA de ciclo de vida completo por variante** (`test_lifecycle.py`): para cada sistema (francés/alemán/
  americano/bullet), crea la línea → solicitud → aprobar → originar → desembolsar → cobra todas las cuotas →
  **CERRADO**, verificando invariantes; más cancelación anticipada (payoff) y refinanciación. **Encontró y
  corrigió 2 bugs reales:**
  1. **Residuo de redondeo**: al cerrar, `saldo_capital` quedaba en ~$0.02 en vez de 0. Fix: `_recompute` fuerza
     `saldo_capital = 0` cuando el préstamo queda CERRADO (todas las cuotas pagadas).
  2. **Bullet no cerraba**: las cuotas en $0 (períodos sin pago del bullet) nunca se marcaban PAGADA (abono 0 →
     break), así que el contrato nunca llegaba a CERRADO. Fix: `_recompute` marca como PAGADA toda cuota sin
     importe; el pago saltea las cuotas en $0 (apunta a la próxima con importe); `_recompute` se llama tras el
     desembolso para dejar el estado limpio desde el arranque.
  Casos CV `caja-adelanto`, `ciclo-sistemas`, `ciclo-cancelacion`, `ciclo-refinanciacion`.

## H-093 · Nueva opción: Caja de créditos (paso 4)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → Caja (nuevo)
Paso 4 del roadmap. Nueva opción **Créditos → Caja de créditos** (`/creditos/caja`): pantalla de cobranza
dedicada de contratos de la línea nueva. Buscador de contratos activos → al elegir muestra saldo, próxima
cuota + vencimiento + ya pagado; selector de **medio de pago** (EFECTIVO/TRANSFERENCIA/DEBITO/CHEQUE); botones
**Cobrar cuota** (total), **Cobro parcial** y **Prepago**. Cada cobro registra la actividad (con `medio_pago`
en el `dato`), genera el **recibo** y el **asiento** al Libro Diario, y actualiza el saldo. La Caja **orquesta
el servicing existente, no recalcula nada** (reusa `/contratos/{id}/actividad`). Backend: `ActividadIn.medio_pago`
guardado en el `dato` de la actividad. Verificado en el navegador (cobro cuota $145.198 con EFECTIVO → recibo +
asiento balanceado + saldo $934.710), demo limpiado. Test `test_cobro_caja_registra_medio_pago`; casos CV
`caja-medio` (auto), `caja-ui` (manual). **Paso 4 (Caja) entregado — roadmap completo (1→4).**

## H-092 · Situaciones de pago (paso 3): diferimiento + refinanciación (cierra paso 3)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing
Con las reglas de negocio definidas por el usuario (el diferimiento **capitaliza interés**; la refi usa
**nueva tasa + plazo**):
- **Diferimiento / payment holiday** (`PAYMENT_HOLIDAY`, importe = N cuotas a diferir): las próximas N cuotas
  quedan en $0; el interés de esos N períodos se **capitaliza** (compuesto) al saldo y el tramo restante se
  **re-amortiza** sobre el nuevo saldo (sube). `_aplicar_holiday` reusa el motor + reset-a-pristino → reversa
  restaura. Verificado: 2 diferidas en $0, resto sube, saldo crece, cierra en 0, reversa OK. Tests
  `test_diferimiento_capitaliza_interes`, `test_diferir_cuotas_invalidas_rechaza`.
- **Refinanciación** (`POST /contratos/{id}/refinanciar` {tasa, plazo}): modelada como **cerrar el viejo +
  crear uno nuevo** sobre el saldo (como en la banca), evitando tocar el set de filas fijas. El anterior queda
  **REFINANCIADO** (no admite más actividades) y se enlaza con el nuevo (`refinanciado_en`/`refinancia_de`).
  El nuevo genera su cronograma con la nueva tasa/plazo sobre el saldo. Test
  `test_refinanciacion_cierra_viejo_y_crea_nuevo`. UI: botones "Diferir cuotas" y "Refinanciar" en el servicing.
  Casos CV ori-diferir/ori-refinanciar. **Paso 3 (situaciones de pago) COMPLETO.**

## H-091 · Situaciones de pago (paso 3): prepago de capital (regenera el tramo)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing / Contabilidad
Segunda situación del paso 3. **Prepago de capital** (`PARTIAL_PREPAYMENT`) con dos modos:
- **BAJA_CUOTA**: mismo número de cuotas pendientes, cuota menor.
- **BAJA_PLAZO**: misma cuota (la francesa original), menos cuotas; las sobrantes quedan saldadas.
**Cómo**: se guarda en el snapshot el **cronograma pristino** + `frecuencia`/`impuestos`; `_recompute` ahora
**resetea a los importes pristinos** antes de reproducir (así regenerar por prepago es **idempotente** y la
reversa restaura el cronograma original). Al procesar un prepago, `_aplicar_prepago` re-amortiza el tramo
pendiente reutilizando el motor `cronograma` (única fuente de verdad, `cargo_pct=0` — no re-cobra el
otorgamiento; mantiene el IVA sobre interés), preservando las fechas de vencimiento. Asiento Debe Caja /
Haber capital por el importe prepagado. UI: botón "Prepago capital" (elige modo). Verificado: saldo baja por
el importe, Σcapital pendiente = nuevo saldo, última cuota cierra en 0, asiento balancea; la reversa restaura
cuota y saldo. Tests `test_prepago_baja_cuota`, `test_prepago_baja_plazo`,
`test_reversa_de_prepago_restaura_cronograma`, `test_prepago_supera_saldo_rechaza`; casos CV ori-prepago-*.
**Nota de diseño**: las cuotas regeneradas no re-aplican cargos de otorgamiento/administrativos (una vez, ya
estructurados); llevan capital+interés+IVA. **Pendientes del paso 3**: adelanto de N cuotas, payment holiday,
refinanciación (necesitan reglas de negocio) → después, junto/antes de la nueva Caja (paso 4).

## H-090 · Situaciones de pago (paso 3): pago parcial de cuota
**Fecha:** 2026-08-10 · **Módulo:** Créditos → servicing / Contabilidad
Primera situación de pago del paso 3 (ver salida/plan-pagos.md). **Pago parcial de una cuota**: `PAYMENT`
ahora acepta un `importe`; si es menor al saldo de la cuota, es un **abono parcial** que se acumula en
`pagado` y **no baja el saldo de capital** hasta completar la cuota (queda PENDIENTE). `_recompute` se
rediseñó para aplicar los abonos en orden acumulando (soporta pago total y parcial, retrocompatible; la mora
no amortiza, se descuenta del abono). El **asiento** de un parcial imputa capital/interés/comisiones/impuestos
**proporcionalmente** (balancea exacto). La **reversa** de un parcial restaura `pagado` (event-sourcing).
UI: botón "Pago parcial" en el servicing. Tests `test_pago_parcial_de_cuota`, `test_reversa_de_pago_parcial`;
casos CV `ori-pago-parcial`, `ori-reversa-parcial`. **Pendiente del paso 3**: prepago de capital (baja
cuota/baja plazo — requiere regenerar el tramo restante), adelanto de N cuotas, payment holiday, refinanciación.

## H-089 · Nueva opción: Solicitudes de crédito (línea nueva)
**Fecha:** 2026-08-10 · **Módulo:** Créditos → Solicitudes (nuevo)
Roadmap paso 1. Nueva opción **Créditos → Solicitudes de crédito** (`/creditos/solicitudes-credito`).
- **Modelo** `pp_solicitud` (tabla nueva): cliente **registrado** (FK al maestro `clientes`) o **no registrado**
  (alta express en JSON), línea `pp_` solicitada, monto/plazo, perfil (segmento/canal/edad/antigüedad/relación),
  `evaluacion` (elegibilidad + cuota/TNA estimada), `contrato_id` al originar.
- **Workflow con cuatro-ojos**: BORRADOR → EN_EVALUACION → APROBADA → ORIGINADA (o RECHAZADA/ANULADA); quien
  envía no aprueba; no se aprueba una solicitud no elegible (422).
- **Cliente no registrado = ambos según permiso**: alta express + endpoint `promover-cliente` que lo da de
  alta en el maestro real (o vincula si el CUIL ya existe).
- **Integración con originación**: `originar` acepta `solicitud_pp_id`; una solicitud APROBADA se origina como
  contrato y queda ORIGINADA + ligada (no re-origina, 409). Reutiliza elegibilidad (Fase E) y el preview del
  cronograma (única fuente de verdad) para la cuota estimada.
- **APIs** `/api/solicitudes` (CRUD + estado + promover-cliente). **Frontend**: bandeja con filtros por estado,
  formulario de nueva solicitud (registrado/express) con elegibilidad en vivo, detalle con acciones y botón
  Originar. Badge `new` en el menú. Registrado en Controles de Versión (tabla + rutas + 6 casos + changelog).
- **Tests** `test_solicitudes.py` (9): alta registrada/express, cuatro-ojos, no-elegible, originar desde
  aprobada, promover cliente, permisos.
**Verificado**: la originación desde solicitud (nueva y legacy) ya estaba probada contra dato real (188512).

## H-088 · Bundles mostraban una versión no vigente del miembro
**Fecha:** 2026-08-10 · **Módulo:** Créditos → bundles
El endpoint `/contratos/bundles` serializaba cada miembro con `_serial` (usa `_ultima` = la última versión,
que puede ser un **borrador** o una **v2 con vigencia futura**), inconsistente con la oferta/originación que
usan `_serial_efectivo` (versión vigente hoy). Un paquete podía mostrar términos de un borrador (ej. una TNA
más alta en preparación) en vez de lo que el cliente recibe hoy. **Fix:** bundles ahora usa `_serial_efectivo`.
Test `test_bundle_muestra_version_vigente_no_borrador`; caso CV `ori-bundle-vig`.

## H-087 · Robustez: relación de pricing inválida se aceptaba silenciosamente
**Fecha:** 2026-08-10 · **Módulo:** Créditos → originación
Una `relacion` inexistente (ej. "INEXISTENTE") se aceptaba (201), se trataba como ESTANDAR (bonus 0) y se
**persistía tal cual en el snapshot** del contrato → basura de datos. **Fix:** se valida contra
`RELACION_PRICING` (ESTANDAR/PREFERENCIAL/PREMIUM); si no es válida, 422. El frontend usa un dropdown del
catálogo (no se ve afectado). Test `test_relacion_invalida_rechaza`; caso CV `ori-relacion-inv`.
**Verificado sin bug en la misma ronda:** segmentación multi-criterio (AND de segmento+canal+edad con motivos
específicos), relationship pricing sobre línea no negociable (aplica, por diseño), herencia con vigencia,
balance de todos los asientos del ciclo.

## H-086 · Componente de mora (OVERDUE) no se aplicaba — ahora sí
**Fecha:** 2026-08-07 · **Módulo:** Créditos → servicing de contratos / Contabilidad
El componente **OVERDUE** y su `moraTNA` (default 120%) se configuraban y guardaban (tasa MORA en
`pp_producto_tasa`) pero el servicing de los contratos pp_ **nunca los aplicaba**: pagar una cuota vencida
no generaba punitorio (el sistema legacy sí tenía mora en `domain/mora.py`, pero los contratos nuevos no).
**Implementado:** al pagar (`PAYMENT`) una cuota vencida, se calcula el interés punitorio reutilizando el
calculador legacy `calcular_mora` (int_pun = cuota · (moraTNA/365)/100 · días, con IVA), descontando los
**días de gracia** del componente; se suma al importe cobrado, se guarda el desglose en la actividad
(`dato.mora_dias/interes_punitorio/iva_punitorio`) y se **asienta** (punitorio a 4.1.02, su IVA a la cuenta
de impuestos). La mora sólo aplica si el componente OVERDUE está **activo** y se congela en el snapshot
(`mora_tna`, `dias_gracia_mora`). Frontend: badge "⚠ mora Nd" en la actividad de pago. Tests
`test_mora_punitorio_en_cuota_vencida`, `test_sin_mora_si_cuota_al_dia`; casos CV `ori-mora`, `ori-sin-mora`.

## H-085 · Bugs de cálculo: doble cobro del cargo al desembolso + financiable ignorado
**Fecha:** 2026-08-07 · **Módulo:** Créditos → motor de cronograma / originación
Encontrados haciendo probes de invariantes sobre el motor:
- **Doble cobro del cargo al desembolso.** El motor pone el cargo `DESEMBOLSO` (no financiable) en la
  1ª cuota (`cuota1_extra`), y además `_liquidacion` lo **restaba del neto acreditado** → el cliente lo
  pagaba dos veces. **Fix:** el motor es la única fuente de verdad; el cliente recibe el **monto completo**
  (`neto = monto`), el cargo vive sólo dentro del cronograma. `_liquidacion` ahora informa `cargosFinanciados`
  (al capital) y `cargosEnCuotas` en vez de deducir. Frontend del wizard actualizado. Test
  `test_cargo_desembolso_no_se_cobra_doble` + `test_otorgar_y_desembolsar_por_pasos` ajustado.
- **'Financiable' se ignoraba con momento PRORRATEADO.** La config CHARGE tiene `momento` y un flag
  `financiable` separado; si quedaban `PRORRATEADO` + `financiable=true`, el motor prorrateaba y el flag no
  hacía nada (trampa silenciosa). **Fix:** `financiable` tiene **prioridad** (se suma al capital sin importar
  el momento). Test `test_financiable_tiene_prioridad_sobre_prorrateado`.
Ambos registrados como casos en Controles de Versión (`ori-doble-cargo`, `calc-financiable-prio`).

## H-084 · Bug de UI: colisión de clase CSS en el calendario de feriados
**Fecha:** 2026-08-07 · **Módulo:** Contabilidad → Feriados (frontend)
Las celdas de feriado en la vista Calendario se renderizaban como **barras verticales** (altas y
angostas) en vez de cuadrados. **Causa raíz:** la clase modificadora de la celda era `.fer`, que
**colisiona** con `.fer` (el contenedor raíz de la página, con `padding: 4px 2px 40px`); las celdas
heredaban 40px de padding inferior. **Fix:** renombrada la clase de celda a `.hol` (holiday). También se
mejoró la UX (pedido del usuario): Importar arriba a la derecha, toggle Tabla/Calendario bajo "Agregar
manual", celdas cuadradas uniformes (28px, grilla fija), colores por tipo bien diferenciados
(Inamovible #d7263d rojo, Trasladable #f2a01d ámbar, Puente #7c3aed violeta, No laborable #0e9488 teal)
y **leyenda**. **Regresión:** el bug era invisible a los tests de backend; como no hay runner de tests de
frontend, se registró como **caso documentado (manual)** en Controles de Versión — pantalla "Feriados
(pantalla)": `fer-ui-calendario` (celdas cuadradas, sin colisión de clase), `fer-ui-leyenda`, `fer-ui-orden`,
`fer-ui-importar`. Catálogo de casos: **51 (30 live)**. **Lección:** evitar nombres de clase CSS de una
sola palabra que puedan chocar con contenedores (usar prefijos por componente).

## H-082 · Vencimientos en feriado + gobernanza del calculador
**Fecha:** 2026-08-07 · **Módulo:** Créditos → motor de cronograma / Sistema de cálculos
- **Bug (fechas): el ajuste hábil sólo salteaba fines de semana, no feriados.** Con `SIGUIENTE_HABIL`
  un vencimiento podía caer en feriado nacional (ej. 1-ene Año Nuevo). **Corregido:** `_ajusta` ahora
  también saltea feriados. Los **feriados nacionales de fecha fija** (Año Nuevo, Memoria, Malvinas,
  Trabajador, Revolución de Mayo, Independencia, Inmaculada, Navidad) están por defecto; los
  **movibles/trasladables** (Carnaval, Viernes Santo, puentes por decreto) se inyectan vía el parámetro
  `feriados` de `cronograma`. Verificado: 1-ene→2-ene; Carnaval inyectado 16→18-feb; `SIN_AJUSTE` intacto
  (retrocompatible). Test `test_vencimiento_ajusta_feriado_nacional`.
  **Pendiente (mejora):** un maestro de feriados por año (tabla + migrador) para alimentar `feriados`
  con los movibles automáticamente; hoy hay que pasarlos explícitos.
- **Decisión "modificar la fórmula" (cerrada e implementada):** se adopta **motor certificado inmutable +
  gobernanza por `pp_calculador_version`**. La pantalla Sistema de cálculos ahora muestra, por sistema, la
  **versión certificada real de DB** (v2 PUBLICADO, motor CERTIFICADO, checksum) además del checksum vivo
  del código, y una sección de **Gobernanza** que explica que la fórmula no se edita en runtime: se publica
  una nueva versión del calculador con su checksum y los contratos quedan congelados sobre la versión con
  la que se calcularon.
- **Observación menor (no bug):** en AMERICANO/BULLET la gracia se ignora (numéricamente inocuo: el
  americano ya es sólo-interés y el bullet no tiene pagos intermedios). Se deja documentado.

## H-081 · Bugs de diseño cerrados: piso de banda + semántica de sistemas
**Fecha:** 2026-08-07 · **Módulo:** Créditos → Originar / Configurar
Dos conceptos que quedaron abiertos en el QA (H-077) se cerraron:
- **BUG (relationship pricing perforaba el piso de la banda):** el descuento por relación
  (PREFERENCIAL −2, PREMIUM −4) se aplicaba **después** de validar la banda de negociación, así que
  un cliente PREMIUM podía terminar por debajo del piso `tasa_minima`. **Corregido:** la banda es un
  **piso duro**; el descuento se aplica con `tna = max(piso, 0, tna + bonus)`. El piso se guarda en el
  snapshot (`piso_relacion`) para que el **repricing** de tasa variable también lo respete. Verificado:
  banda 40–60, negociada 40 + PREMIUM → **40** (no 36); negociada 50 + PREMIUM → 46. Test
  `test_relationship_pricing_no_perfora_piso_de_banda`.
- **Semántica de sistemas (aclaración, no era bug de cálculo):** “BULLET” estaba etiquetado ambiguamente.
  El **bullet clásico** (interés periódico + capital al vencimiento) ES el sistema **AMERICANO**; el
  sistema **BULLET** es capitalización total a vencimiento (cupón cero). Se renombraron las etiquetas en
  el configurador y en Sistema de cálculos para que la distinción sea inequívoca. La matemática de ambos
  ya era correcta y distinta; sólo faltaba nombrarla bien.

## H-080 · Sistema de cálculos — transparencia y depurador de cuotas (nueva opción)
**Fecha:** 2026-08-07 · **Módulo:** Créditos → Configurar
**Pedido:** una opción donde ver la fórmula que se aplica, poder “modificarla” y ver cómo se
arman las cuotas estilo debug.
**Entregado:** nueva opción de menú **Créditos → Sistema de cálculos** (`/creditos/sistema-calculos`):
- **Fórmula por sistema** (francés, alemán, americano, bullet): ecuación, variables y orden de armado.
- **Motor certificado**: se muestra el **checksum SHA-256 real del código fuente** del motor
  (`productos_calc`), la regla de redondeo (HALF_UP) y la precisión. Es la misma única fuente de
  verdad que usan la prueba en vivo, la simulación y la originación.
- **Depurador paso a paso**: para monto/plazo/TNA/frecuencia/gracia/tipo de cuota/cargo, muestra los
  **parámetros derivados** (i = TNA/100·per/12, cuota francesa, etc.), las **tasas** (TNA/TEA/CFT) y una
  tabla por cuota; al hacer click en una cuota se despliega el detalle con **números reales**
  (`interés = saldo · i = 100.000,00 · 0.043333 = 4.333,33` → `capital = cuota − interés` → `saldo_final`).
- Endpoints: `GET /api/sistema-calculos`, `POST /api/sistema-calculos/debug`.
**Decisión de diseño (importante):** la **fórmula del motor NO se edita en runtime**. Es código
certificado y versionado por checksum; “modificar el cálculo” se hace cambiando **parámetros** desde
Configurar Créditos, no reescribiendo la fórmula. Así todo el sistema calcula igual y es auditable.
Si en el futuro se quiere versionar el propio motor, existe el mecanismo `pp_calculador_version`.
**Verificado en vivo:** francés cierra saldo en 0,00 en la última cuota; americano paga sólo interés
(4.333,33) y devuelve el capital en la cuota final (104.333,33). Tests: `test_sistema_calculos_*` (3).

## H-079 · Tasas visibles (TNA/TEA/CFT) + vigencia por versión de préstamo
**Fecha:** 2026-08-07 · **Módulo:** Créditos → Configurar / Originar
**Pedido:** (A) mostrar siempre arriba del proceso TNA/CFT/TEA calculándose en vivo (la TNA se guarda);
la prueba en vivo no las mostraba/actualizaba. (B) falta la vigencia desde/hasta; **cada versión tiene
su propia vigencia** — v1 vigente y al crear v2 se activa según la fecha; guardar versiones para trackear
los créditos otorgados sobre versiones anteriores.
**Entregado (A):** barra de tasas en el encabezado del configurador (**TNA · TEA · CFT · 1ª cuota · ● en vivo**),
recalculada por el backend en cada cambio de config (verificado: TNA 52→80 movió TEA 66→117 y CFT 96→171).
El motor `resumen()` ahora devuelve `tna/tea/cft`; la **TNA se persiste** en la versión, TEA/CFT se derivan.
**Entregado (B):** cada versión tiene `vigente_desde`/`vigente_hasta` editables. La **versión efectiva** se
resuelve **por fecha** (`_version_efectiva`): oferta, originación y herencia usan la versión publicada
vigente hoy. Al **publicar** una versión sin fecha entra en vigencia hoy; y se **cierra automáticamente**
la vigencia de la versión publicada anterior (`vigente_hasta = vigente_desde` de la nueva) — así queda el
tracking de qué créditos se otorgaron sobre cada versión.
**Verificado:** `test_version_vigencia_efectiva_a_futuro` — publicar v2 con vigencia a 30 días **no**
reemplaza a v1 hoy (la oferta sigue usando v1), y v1 queda con `vigente_hasta` = fecha de v2. Suite: 204 tests.

## H-043 · Registro de migradores DBF→modelo (re-ejecutable) + módulo Seguridad
**Fecha:** 2026-08-05 · **Módulo:** Seguridad (nuevo) / ETL
A pedido, para poder **re-migrar contra datos reales** cuando el sistema legacy exporte nuevos
`.dbf`. Se creó un **registro declarativo** (`app/etl/registro.py`): 15 migradores, cada uno con
programa VFP de origen, ruta del DBF, tabla destino, **conversiones** (campo DBF → campo del modelo
+ tipo) y la función loader. `estado(db)` devuelve el catálogo con conteos migrados + existencia/
tamaño del DBF; `ejecutar(clave, reset=True)` **trunca la(s) tabla(s) (TRUNCATE … CASCADE en PG) y
recarga** — los loaders traen guard "si ya hay datos, omito", así que el reset es lo que habilita la
re-migración. API `app/api/migradores.py` (restringido a ADMG): `GET /api/migradores` (catálogo),
`POST /api/migradores/{clave}/ejecutar?reset=` y `POST /api/migradores/ejecutar-todo?reset=`, con
corridas en **segundo plano** (hilos) y estado por polling. Pantalla `/seguridad/migradores`
(catálogo + botones Migrar/Reset por fila + "Re-migrar todo"). Se creó el **módulo Seguridad** en el
menú y se movieron ahí **Usuarios, Perfiles y Auditoría** (rutas `/seguridad/*`, con redirect desde
`/general/*`). **Verificado:** catálogo 200 con 15 migradores y **3.430.742 registros** migrados en
total; **re-migración real de `polizas` con reset → truncó y recargó a 207.498** (re-ejecutabilidad
probada); `tsc` sin errores; **155 tests OK**. Este panel deja preparada la re-migración total para
cuando la app reemplace a la actual.
**Ampliación — DER visual:** endpoint `GET /api/migradores/esquema` que arma el esquema para un
diagrama entidad-relación: **modelo actual** (55 tablas + columnas + **26 FKs reales** leídas de la
metadata de SQLAlchemy) y **DBFs legacy** (campos por migrador). Pantalla `/seguridad/modelo-datos`
(Seguridad → Migración de datos) con un **DER propio en SVG** (sin dependencias): cards de entidad
con PK 🔑/FK 🔗 y **líneas de relación curvas medidas del DOM** (con flecha), toggle *Modelo actual /
DBFs legacy* y filtro por módulo. Verificado: Créditos dibuja 4 líneas de FK entre
clientes/creditos/cuotas/lineas_credito/turnos_credito; FKs cross-módulo se muestran como badge
(ej. `solicitud_id → solicitudes`). La vista legacy muestra el mapeo campo DBF → campo del modelo.
**Ampliación — Inventario de DBFs:** tercera vista que **escanea todo el backup por carpeta** y lista
**cada .dbf** con nº de registros y campos (leídos de la **cabecera DBF**, sin abrir el archivo
completo) y marca cuáles se migran (→ tabla) y cuáles no. Endpoint `GET /api/migradores/inventario`.
**Revela lo no migrado:** Contabilidad tiene **23 DBFs y sólo 1 migrado** (`asientos.dbf`; el resto
sin migrar incluye `basectadev.DBF` 2.575.573 reg., `crctacte.dbf` 1.049.892, `cc1.DBF` 236.583);
Caja **21 DBFs / 4 migrados** (con históricos enormes sin migrar: `cj_liqhis.dbf` 1.370.363 reg./760
MB, `cj_paghis.DBF` 652.538); Créditos 45/9, General 41/2, Seguros 31/5, Juegos 1247/3, Mesa 3/3,
Despacho 3/2, Egresos 9/2. Aclara por qué un módulo migrado puede tener pocas tablas: **se migró el/
los DBF núcleo, no los auxiliares/históricos** — que ahora quedan visibles y priorizables.
**Ampliación 2 — propósito/motivo + migración de ccseguros:** el inventario ahora incluye, por cada
DBF, su **propósito** (qué contiene) y, si no se migra, el **motivo** — investigado del código legacy
(`basectadev.prg` = base de devengamiento; `jjimpjue`/`l1pandemia.prg` = importación de jugadas) o
inferido por patrón (`IEJUE\d+` = export diario de jugadas; `cj_*his`/`*his*` = históricos;
`cierre*` = cierres recalculables). Las que no pude catalogar se marcan honestamente "(sin catalogar)
— se puede migrar si se necesita, avisar". Para las migradas, el inventario muestra el **mapeo campo
DBF → campo del modelo**. **Nueva migración real:** `Seguros/ccseguros.dbf` → modelo `CtaCteSeguro`
(cta. cte. de seguros por agente) — **180.501 registros** cargados; migrador `ccseguros` sumado al
registro (ahora 16 migradores / 56 tablas). Verificado: `ccseguros → ctacte_seguros` con mapeo de 7
campos; el detalle expandible de una migrada (cajacreseg) muestra COD_AGENCI→cod_agencia, etc.
**Ampliación 3 — origen por tabla en el DER + migrador de asientos por partida doble.** El DER
del *Modelo actual* ahora muestra en cada tabla **de qué DBF viene** (o "sin origen legacy — la
genera la app"), y se clasificaron las tablas app-generadas en su módulo (Contabilidad pasó de 1 a 4
tablas). Esto surgió de una consulta del usuario: la tabla `asientos` (partida doble) estaba **vacía
y sin origen** — el legacy `asientos.dbf` se había migrado al **mayor plano** `movimientos_contables`
(2M), no a `asientos`. **Hallazgo:** el `asientos.dbf` legacy es un **mayor plano** (una fila por
pierna); `NORDEN` es **único por fila** (no agrupa), pero `CREFERENCI` (referencia) **sí vincula las
piernas**: agrupando por (periodo, fecha, referencia) se obtienen **1.049.890 asientos**, de los que
**960.046 balancean** (debe=haber; 959.510 con exactamente 2 líneas). Nuevo migrador `asientos_pd`
(`cargar_asientos_pd`) que **reconstruye el libro diario por partida doble** desde el mayor ya
migrado → tablas `asientos` + `asientos_lineas`. Ahora el DER muestra `asientos ← asientos.dbf
(reconstruido)`.
**Ampliación 4 — migradores de Contabilidad y Caja (a pedido):** se agregaron 3 migradores para
DBFs reales que faltaban: `Contabilidad/crctacte.dbf` → `CtaCteContableCredito` (cta. cte. contable
de créditos con desglose capital/interés normal-punit-resarc/IVA/gastos/sellado; **1.049.892**);
`Contabilidad/contgral.dbf` → `ContabilidadGeneral` (contab. general de caja/juegos por asiento,
importes por moneda; **106.557**); `Caja/cj_crsghis.dbf` → `CajaCreSegHistorico` (crédito/seguro
cobrado en caja, histórico; **143.640**). Ahora **20 migradores**; Contabilidad pasó de 1 a 3 DBFs
migrados y Caja de 4 a 5. El inventario y el DER se actualizan solos (origen por tabla, mapeo,
propósito). Cada uno re-ejecutable con reset.
**Ampliación 5 — históricos de Caja + trazabilidad "usos en menú".** Se migraron los históricos
grandes de Caja: `cj_liqhis.dbf` → `LiquidacionAgenciaHistorica` (**1.370.363**) y `cj_paghis.dbf`
→ `CajaPagoAgenciaHistorico` (**652.537**). Total **22 migradores** (61 tablas). Además, regla nueva
del usuario: por cada migrador se documenta **en qué opciones de menú se usa cada tabla** (mapa
`USOS_MENU`, tabla → pantallas). Se expone en el DER (cada card muestra "USO EN MENÚ") y en el
catálogo de Migradores. Verificado: `liquidaciones_agencia` → 4 pantallas (Agencias/Fondo gtía/
Aplicativo caja/Deuda agencia); `polizas_agente` → Pólizas + Visión 360; los históricos recién
migrados (`liquidaciones_agencia_hist`, `caja_pagos_agencia_hist`, `ctacte_contable_credito`,
`contabilidad_general`, `ctacte_seguros`) muestran **"aún sin pantalla"** (migradas pero todavía sin
consumidor en la UI — transparencia). Regla guardada en memoria del proyecto.
**Ampliación 6 — pantallas que consumen las tablas migradas.** Se construyeron 3 pantallas para
explotar dato migrado que estaba "sin pantalla": **Cta. cte. contable por crédito**
(`/contabilidad/ctacte-credito`, sobre `ctacte_contable_credito`) con el desglose contable +
totales; **Contabilidad general** (`/contabilidad/general`, sobre `contabilidad_general`) con
filtros y totales por moneda; **Histórico de agencia** (`/caja/agencia-historico`, sobre
`liquidaciones_agencia_hist` + `caja_pagos_agencia_hist`) con liquidaciones y pagos archivados.
Endpoints `GET /contabilidad/ctacte-credito`, `/contabilidad/general`, `/juegos/agencia-historico`.
`USOS_MENU` actualizado (esas 5 tablas ya no figuran "sin pantalla"). Verificado con dato real:
crédito 8933 → 51 movs saldo $567,77; contabilidad general 106.557 movs (pesos $12,3M); `tsc` limpio,
155 tests OK.

## H-078 · QA Configurar Créditos (2ª ronda) — bug contable y bug de herencia corregidos
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos / Contabilidad
- **BUG-2 (CORREGIDO)**: el asiento de pago imputaba **todo** el residual a "IVA débito fiscal", mezclando
  comisiones (otorgamiento 2% + administrativo 1.5%) con IVA/sellado. Fix: `PPCuotaContrato.impuestos` guarda
  la porción de impuestos por cuota (el cronograma la devuelve); `asiento_pp_pago` ahora acredita **comisiones
  a 4.1.04** e **impuestos a 2.1.07** por separado. Nueva cuenta editable `cuentaComision` en el componente
  ACCOUNTING. Verificado: pago de cuota separa $21.629 comisiones + $14.946 IVA (antes $36.575 todo a IVA),
  balanceado. Test `test_asiento_separa_comisiones_de_impuestos`.
- **BUG-3 (CORREGIDO)**: la herencia de un hijo derivado resolvía desde `_ultima(padre)` = la versión de
  mayor número, **incluyendo un borrador nuevo** del padre. O sea: abrir una nueva versión del padre (aún sin
  publicar) alteraba a todos los hijos en catálogo/oferta. Fix: `_version_efectiva(prod)` = última PUBLICADA
  (o la última si no hay publicada), usada en la resolución de herencia. Verificado: con padre v1 publicada
  (50%) + v2 borrador (99%), el hijo hereda 50 (antes heredaba 99). Test
  `test_herencia_usa_version_publicada_no_borrador`.
- **Verificado OK (sin bug)**: el servicing (`_recompute`, pago) usa el **snapshot congelado** y las cuotas
  del contrato, **no relee el producto** → los contratos originados son inmutables ante cambios del producto.
**Suite completa: 200 passed** (tras corregir el enunciado del test — cuatro-ojos requiere 2 usuarios).

## H-077 · QA de Configurar Créditos — bugs encontrados (1 crítico corregido)
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos / Originar Crédito
Pasada de QA escéptica sobre el cálculo y la coherencia. Los **invariantes del cronograma son sólidos**
(en 24 casos borde —plazo 0/1, tna 0/negativa, gracia≥plazo, adelantada×sistemas, financiable, trimestral+gracia—
siempre cierra el saldo en 0, Σcapital = monto, sin negativos ni NaN). Hallazgos:
- **BUG-1 (crítico, CORREGIDO)**: en el wizard de Originar, el paso *Simular* usaba `cfg.tna` (= 0, la tasa
  default) para líneas de **tasa VARIABLE**, mientras que `originar` usa **índice + margen** (LP-VAR-01 = BADLAR
  45 + margen 10 = 55%). El preview mostraba un cronograma **sin intereses** y la card "0%", divergente del
  contrato real. Fix: `_serial_v` expone `cfg.tnaVigente` (resuelve índice+margen para VARIABLE); Originar usa
  `tnaVigente` en el simulador, el default y la card. Caso live `ori-variable` reforzado (verifica tnaVigente=55).
  Verificado: la card muestra "55% (BADLAR)" y el cronograma tiene interés $55.000.
- **BUG-2 (contable, pendiente)**: `asiento_pp_pago` imputa **todo** el residual (cargos + IVA + sellado) a
  "IVA débito fiscal". El cargo de otorgamiento (2%) y el administrativo (1.5%) quedan mal clasificados como IVA
  (sobrevalúa IVA, oculta ingresos por comisiones y el sellado). Requiere desglosar el `cargos` de la cuota por
  tipo (no está persistido); no corregido aún.
- **Concepto de diseño**: "BULLET" está modelado como **pago único capitalizado** (P·(1+i)ⁿ), no el bullet clásico
  (interés periódico + capital al final). Definir cuál espera el negocio.
- **Menor**: el relationship pricing se aplica **después** de validar la banda negociable → puede dejar la TNA por
  debajo del piso de la banda. Y la métrica "Cuota" (francés) muestra la 1ª cuota (que incluye el cargo de
  desembolso), no la cuota nivelada.
**Suite completa 198 passed** tras el fix. `tsc` limpio.

## H-076 · Más casos de prueba live — cobertura de las opciones de préstamo
**Fecha:** 2026-08-07 · **Módulo:** Controles de Versión
Se amplió el catálogo de casos de 19 a **39 (26 live)**, aprovechando que `/productos/preview` es read-only:
se pueden ejercitar TODAS las opciones de cálculo sin tocar la base. Nueva pantalla **"Cálculo de cuotas
(opciones)"** con 15 casos live: cronograma cierra en 0, sistemas **francés** (cuota constante) / **alemán**
(capital constante) / **americano** (capital al final) / **bullet** (pago único), **gracia** (cuotas de sólo
interés), **frecuencia trimestral** (vto cada 3 meses), **cuota adelantada** (1ª sin interés), cargo
**desembolso** (cae en 1ª cuota) vs **prorrateado** (igual por cuota) vs **financiable** (se suma al capital),
**IVA sobre interés/cargos**, **ajuste de fin de semana** (ningún vto en sábado/domingo) y **día de pago**
(cambia fechas). Más casos live de originación: segmentación por **AGENTE_PUBLICO/canal CONVENIO/edad**,
línea **VARIABLE (BADLAR)**, **bundle**; y de maestros: **índice BADLAR** e **impuestos** sembrados.
`POST /controles-version/casos/run` → **26/26 OK**. Base de regresión que crece sin costo (los casos live
salen del preview/oferta/maestros). `tsc` limpio. Verificado en browser.

## H-075 · Controles de Versión — diagrama de relaciones + casos de prueba corribles
**Fecha:** 2026-08-07 · **Módulo:** Controles de Versión
Dos agregados a la pantalla H-074. **(1) Diagrama de relaciones**: nueva tab con un **SVG** que dibuja las 23
tablas como entidades posicionadas por capas (profundidad de FK), con **flechas curvas** hacia la tabla
referenciada, barra de color por grupo, marca ↻ para auto-referencias (pp_producto.padre_id, pp_actividad.reversa_de);
layout calculado en el frontend desde las FK que devuelve el endpoint. **(2) Casos de prueba por pantalla**:
`GET /controles-version` ahora incluye un **catálogo de 19 casos** agrupados por pantalla, cada uno marcado
`auto` (cubierto por la suite pytest, con la función referenciada) o `live` (corrible en el acto). Nuevo
`POST /controles-version/casos/run` corre los **6 casos live** (read-only sobre el sistema en ejecución:
oferta sólo publicadas, segmentación, tablero consistente, catálogos, el preview cierra en 0, el preview
reacciona al IVA) y devuelve ✓/✗ + detalle + ms. Frontend: tab "✅ Casos de prueba" con el catálogo y botón
"▶ Correr pruebas en vivo" (resumen 6/6 OK). Base para ir sumando casos y no perder trazabilidad de regresión.
`tsc` limpio. Verificado en browser: diagrama con 23 entidades + 19 flechas; casos 6/6 OK.

## H-074 · Controles de Versión — documentación viva (modelo de datos + APIs + cambios)
**Fecha:** 2026-08-07 · **Módulo:** Controles de Versión (nuevo)
Nueva opción de menú **Controles de Versión** (`/controles-version`, sidebar top-level, ruta
`/api/controles-version`) que documenta el módulo Configurar Créditos y **se genera introspectando la
realidad** para no quedar desactualizada. Backend `api/controles_version.py`: `GET /api/controles-version`
devuelve (a) el **modelo de datos** — 23 tablas (19 `pp_*` + impuestos/índices + asientos) agrupadas, con
columnas tipadas y PK/FK detectados vía `inspect(engine)`; (b) las **APIs** — 40 endpoints de los routers
del módulo, leídos de `request.app.routes` con método/path/docstring; (c) el **registro de cambios** (20
hitos curados, Fases 1–3 … Devengamiento) y las 4 opciones de menú nuevas. Frontend `ControlesVersion.tsx`
con 3 tabs: **Modelo de datos** (entidades ER en tarjetas, badges PK/FK, relaciones al pie), **APIs**
(agrupadas por router, con filtro y badges de método) y **Registro de cambios** (timeline). `tsc` limpio.
Verificado en browser: 23 tablas graficadas, 40 endpoints, timeline de 20 hitos.

## H-073 · Devengamiento periódico de intereses (asiento de devengo)
**Fecha:** 2026-08-07 · **Módulo:** Originar Crédito / Contabilidad
Réplica del `cb-crasientodevenga` legacy con contabilidad correcta por lo devengado. `PPCuotaContrato.devengada`
(bool). `POST /contratos/{id}/devengar` reconoce el interés de la próxima cuota pendiente no devengada:
asiento **Debe 1.2.02 Intereses a devengar (activo) / Haber 4.1.01 Intereses ganados (ingreso)** + actividad
ACCRUAL; marca la cuota. Clave para no duplicar el ingreso: `asiento_pp_pago` ahora, si la cuota estaba
devengada, acredita el interés a **1.2.02** (salda la cuenta a cobrar) en vez de a 4.1.01 — el ingreso se
reconoce una sola vez (al devengar). Frontend: botón **📈 Devengar interés** en el servicing y marca
"📈 devengada" en el cronograma. **Tests**: +1 (`test_devengamiento_no_duplica_ingreso`: asiento de devengo
balanceado a 1.2.02/4.1.01; el cobro de la cuota devengada acredita 1.2.02 y **no** 4.1.01) → **suite completa
198 passed**. `tsc` limpio. Verificado con dato real: devengo cuota 1 ($43.333,33) y cobro que salda la cuenta
a devengar.

## H-072 · Exportación de contratos (PDF) y cartera (Excel)
**Fecha:** 2026-08-07 · **Módulo:** Originar Crédito
Reutilizando la infra de reportes existente (reportlab / openpyxl): `contrato_pdf(cto)` genera el PDF del
contrato con membrete institucional, bloque de datos (línea, sistema/TNA, monto/plazo, estado, cargos al
desembolso, neto a acreditar, destino/CBU/garante) y el cronograma con totales; `contratos_pp_excel(items)`
exporta la cartera (contrato, cliente, línea, monto, saldo, TNA, plazo, estado, fecha) con totales.
Endpoints `GET /contratos/{id}/pdf` y `GET /contratos/export.xlsx` (declarado antes de `/{contrato_id}` para
no colisionar). Frontend: botón **⬇ PDF** en el detalle del contrato y **⬇ Exportar cartera (Excel)** en la
lista, vía el helper `abrirArchivo` (descarga autenticada con token). **Tests**: +1 (`test_export_pdf_y_excel`:
firma %PDF y PK/zip) → **suite completa 197 passed**. `tsc` limpio. Verificado: PDF de CTO-2026-00002
(cronograma francés con cargos al desembolso en la 1ª cuota, TOTALES) y Excel 2007+ válidos.

## H-071 · Originar Crédito como proceso guiado (wizard 5 pasos) + liquidación/desembolso
**Fecha:** 2026-08-07 · **Módulo:** Originar Crédito
"Originar" pasó de una pantalla suelta a un **proceso guiado**: 1) **Cliente** (validar datos, traer de una
solicitud aprobada real), 2) **Simular** (elegir línea + monto/plazo/tasa con el cronograma del backend, la
única fuente de verdad), 3) **Datos adicionales** (destino, CBU de acreditación, garante, observaciones),
4) **Otorgar** (revisión y alta), 5) **Liquidación y desembolso**. Backend: `PPContrato.datos_adicionales`
(JSON), estado nuevo `A_LIQUIDAR`, `OriginarIn` + `datos_adicionales`/`desembolsar` (default True conserva el
comportamiento previo); `originar` con `desembolsar=False` deja el contrato en A_LIQUIDAR **sin** asiento ni
desembolso; `POST /contratos/{id}/desembolsar` registra el desembolso (asiento de otorgamiento + actividad
DISBURSEMENT → ACTIVO). `_liquidacion` calcula el **neto a acreditar** = monto − cargos cobrados al desembolso;
se expone en el serial junto con `datos_adicionales`. Las actividades quedan bloqueadas (409) hasta desembolsar.
Frontend: `OriginarCredito` reescrito con stepper, cada paso su pantalla, reutilizando búsqueda de solicitud,
oferta segmentada, preview del backend, tablero de cartera y el servicing (el detalle ahora ofrece "Desembolsar"
si el contrato está A_LIQUIDAR). **Tests**: +1 (`test_otorgar_y_desembolsar_por_pasos`: A_LIQUIDAR sin asiento,
409 al pagar antes, desembolso → ACTIVO + asiento, doble desembolso 409) → **suite completa 196 passed**. `tsc`
limpio. Verificado en browser: GOMEZ ANA → Préstamo Personal → destino/CBU → otorgar (A_LIQUIDAR) → liquidación
(neto $1.176.000 = $1.200.000 − $24.000) → desembolso → ACTIVO + asiento en el Libro Diario.

## H-070 · Cronograma unificado — una única fuente de verdad (preview == originado)
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos / Originar Crédito
El simulador del frontend calculaba el cronograma por su cuenta y **divergía** del backend que origina
los contratos (que ignoraba gracia, frecuencia, impuestos, cargos y el componente Cronograma). Además
la cuota adelantada, financiable y el CFT del frontend no eran rigurosos. Se unificó todo en el backend
`services/productos_calc.cronograma`, ahora **completo y correcto**: sistemas francés/alemán/americano/
bullet, período de gracia, frecuencia (tasa proporcional + fechas por período), **cuota adelantada**
(anualidad anticipada real: 1ª cuota amortizante sin interés, cuota francesa descontada un período),
**cargos** (prorrateado = % de cuota / desembolso = 1ª cuota / financiable = al capital), **impuestos**
por base (INTERES/CARGOS/CUOTA/CAPITAL/TOTAL), y fechas (día de pago, 1er vencimiento, ajuste de fin de
semana). CFT = **TIR real** (bisección) anualizada, no la aproximación anterior. Este `cronograma` es la
única fuente: lo usan la **originación** (`_params_cronograma(v)` arma los parámetros desde los
componentes de la versión), la **simulación persistida** y el nuevo endpoint stateless
`POST /productos/preview`. El frontend dejó de calcular localmente: la prueba en vivo consulta
`/productos/preview` (debounced 220ms) y muestra cronograma + métricas + CFT del backend. **Test de
coherencia**: `test_preview_coincide_con_contrato_originado` verifica que el preview y el contrato
originado producen cuota/capital/interés/cargos/fecha idénticos → **suite completa 195 passed**. `tsc`
limpio. Verificado en browser: cuota real $123.828 (incluye IVA+cargos), CFT 96.4% (TIR), y editar gracia
0→3 reacciona vía backend (costo ▲$66.865) igual que antes.

## H-069 · Tablero de cartera de contratos pp
**Fecha:** 2026-08-07 · **Módulo:** Originar Crédito
Tablero agregado de la cartera originada en Configurar Créditos. `GET /contratos/tablero`: cantidad de
contratos, desglose por estado, capital colocado (Σ monto_original), saldo vigente (Σ saldo_capital de
activos), cobrado (Σ pagado), cuotas pagadas/pendientes, contratos en mora (activo con cuota vencida
impaga) y desglose por línea (contratos + saldo, ordenado desc). Frontend: panel **📊 Tablero de cartera**
al tope de Originar Crédito (métricas + chips por estado y por línea), que se refresca al cambiar los
contratos. **Tests**: +1 (`test_tablero_cartera`: agrega tras originar+pagar, saldo baja, cobrado sube) →
**suite completa 194 passed**. `tsc` limpio. Verificado en browser: 2 contratos → Saldo vigente $3M,
Capital colocado $3M, chip "LP-PERS-01: 2 · $3.000.000".

## H-068 · Prueba en vivo — panel flotante reactivo con detección de impacto
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos (simulador)
Dos problemas del "Probar en vivo": (a) el cronograma **no reaccionaba a varios parámetros** (gracia de
capital, frecuencia, ítems de Cargos e Impuestos) y (b) era una columna fija poco visible. Fix:
`calcSchedule` reescrito para reaccionar a **toda** la config — `graciaCapital` (primeras N cuotas sólo
interés, amortiza en n−g), `frecuencia` (mensual/trimestral: tasa y fechas por período), ítems de
**CHARGE** (% sobre cuota) e **impuestos TAX** (% por base INTERES/CAPITAL/CARGOS/CUOTA/TOTAL) plegados
en la columna de cargos. El simulador pasó a un **panel flotante** arrastrable (fixed, esquina inferior,
cerrable) con: datos básicos (monto/plazo), métricas con **delta vs. baseline** (▲/▼ cuota, costo,
intereses+cargos), y una sección **📍 Impacto de tus cambios** que lista qué condiciones cambiaron
respecto del estado al abrir la línea (antes → ahora) — más validación embebida, guardar/listar
simulaciones y el cronograma con **filas resaltadas** donde cambió la cuota. El baseline se congela al
abrir la línea (`abrir()` deep-copia cfg+componentes). `tsc` limpio. Verificado en browser: poner gracia
0→3 muestra "Cuota ▼$30.300 · Costo ▲$66.865 · Gracia capital 0 → 3" con 24 filas resaltadas; subir una
alícuota de impuesto suma "Impuestos · condiciones" y ▲$188.039 al costo (antes no impactaba nada).
**Ampliación**: el cronograma tampoco reaccionaba al componente **Cronograma (REPAYMENT_SCHEDULE)** —
ahora usa `diaPago` (día del vencimiento), `primerVencimientoDias` (1er vto = fecha valor + N días),
`ajusteFinDeSemana` (SIGUIENTE/ANTERIOR hábil sobre sábados/domingos) y `tipoCuota` (VENCIDA/ADELANTADA,
factor annuity-due 1/(1+i)). Las filas del cronograma se resaltan también cuando cambia **la fecha** (no
sólo el monto), con la columna Vto en color. Verificado: día de pago 5→20 y 1er vto 30→60 días mueve los
vencimientos a 20/10, 20/11, 21/12 (ajuste de finde) con 24 filas resaltadas e impacto "Cronograma · condiciones".
**Cargos**: los ítems (%/base) ya reaccionaban, pero `momento` (DESEMBOLSO/PRORRATEADO, del componente y por
ítem) y `financiable` se ignoraban. Ahora un cargo PRORRATEADO se reparte en todas las cuotas, DESEMBOLSO cae
en la 1ª cuota, y FINANCIABLE reparte un cargo de desembolso en vez de cobrarlo en la primera. Verificado:
otorgamiento DESEMBOLSO→PRORRATEADO baja la 1ª cuota de $42.415 a $14.585 con el costo total igual (redistribución).

## H-067 · Simulaciones persistidas — guardar escenarios del simulador con su cronograma
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos (simulador)
El simulador de Configurar Créditos calculaba en vivo sin guardar; ahora las simulaciones se
**persisten** para trazabilidad/auditoría. Modelos `pp_simulacion` (producto+versión, sistema, monto,
plazo, tna, cargo, agregados: total_cuotas/total_interes/primera_cuota, etiqueta, creado_por/en) y
`pp_cuota_simulada` (cronograma completo). Backend (`api/productos.py`, reusa el port `cronograma`):
`POST /productos/{id}/simulaciones` recomputa el cronograma desde la config de la versión (con override
opcional de `tna` para escenarios negociados; valida monto/plazo dentro de rango → 422) y lo guarda;
`GET /productos/{id}/simulaciones` (más reciente primero); `DELETE /productos/{id}/simulaciones/{sid}`.
Rutas anidadas bajo `{id}` para no colisionar con `GET /{producto_id}`. Frontend: en el panel "Simulador
en vivo", input de etiqueta + **💾 Guardar** y lista de **Simulaciones guardadas** (cargar en el simulador
al click, borrar). **Tests**: +1 (`test_simulaciones_persistidas`: guardar con y sin override de tasa,
listar, 422 fuera de rango, borrar) → **suite completa 193 passed**. `tsc` limpio. Verificado en browser:
"Escenario cliente premium" ($1,2M · 24c · 52% · cuota $82.413) persiste tras recargar la página.

## H-066 · Integración con Solicitudes legacy — originar contrato desde solicitud aprobada
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos ↔ Créditos (solicitudes reales)
Permite que un contrato `pp_` **nazca de una solicitud de crédito legacy** (VFP `agjscreditos!solicitud`,
tabla `solicitudes_credito`, 78.443 filas reales; 391 en estado `A` = aprobada). `PPContrato` +
`solicitud_origen` (NO_SOLICIT, indexado). Backend: `GET /contratos/solicitudes?q=&estado=A` lista
solicitudes aprobadas con datos (apellido/CUIL/monto/línea/fecha) **excluyendo las ya originadas**
(busca por apellido o CUIL, ilike); `originar` acepta `solicitud_id` (valida existencia + no reutilización
→ 409) y lo guarda en el contrato; `_serial_contrato` expone `solicitud_origen`. Frontend (OriginarCredito):
panel **🗂️ Originar desde solicitud aprobada** con búsqueda; al elegir una solicitud se prellenan cliente y
monto (clamp al rango del producto); al originar se pasa `solicitud_id` y la solicitud se quita de la lista;
el detalle del contrato muestra el badge **🗂️ Solicitud N° X**. **Tests**: +1
(`test_originar_desde_solicitud_legacy`: aparece en originables, origina y linkea, se excluye tras originar,
doble originación 409) → **suite completa 192 passed**. `tsc` limpio. Verificado en browser con dato real:
solicitud **N° 179675 ARROYO, MARIANA NICOLASA ($300.000)** → contrato CTO con badge de solicitud + asiento
contable generado.

## H-065 · Integración contable — asientos automáticos de originación/servicing de contratos
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos ↔ Contabilidad
Conecta la originación y el servicing de contratos `pp_` con el **Libro Diario** real (tabla `asientos`/
`asientos_lineas`, misma que usa el módulo Contabilidad). Generadores nuevos en
`services/contabilidad.py`: `asiento_pp_otorgamiento` (Debe cuenta de capital / Haber Caja por el
capital desembolsado), `asiento_pp_pago` (Debe Caja / Haber capital+interés+IVA residual),
`asiento_pp_payoff` (Debe Caja / Haber capital cancelado) y `asiento_pp_reversa` (contra-asiento que
invierte debe/haber, no borra el original). El mapeo de cuentas sale del componente **ACCOUNTING** del
producto (`_contab_cfg`, congelado en el snapshot del contrato al originar). En `contratos.py`:
`originar` asienta el otorgamiento y lo enlaza al DISBURSEMENT (`dato.asiento_id`); `actividad`
PAYMENT/PAYOFF asientan la cobranza; `reversar` genera el contra-asiento del asiento vinculado.
`_serial_contrato(c, db)` expone los asientos del contrato (por `concepto LIKE numero_contrato`); FE:
panel **📚 Asientos contables** en el detalle (la tarjeta de contrato ahora carga vía `obtener`).
**Fix de datos reales**: la secuencia de `asientos` estaba detrás de ~1,05M filas migradas con id
explícito (UniqueViolation al insertar) → resync (`setval` sobre `asientos`/`asientos_lineas`) +
`_resync_secuencia_asientos()` defensivo en el lifespan (con guard para SQLite). **Tests**: +2
(`test_asientos_contables_de_originacion_y_pago` verifica asientos balanceados y presencia en el
libro-diario; `test_reversa_de_pago_genera_contra_asiento`) → **suite completa 191 passed**. `tsc`
limpio. Verificado en browser + dato real: contrato CTO-2026-00001 asienta #1049891 (Débito Préstamos
otorgados / Crédito Caja $1.200.000) y aparece en el Libro Diario.

## H-064 · Fase G (plan Temenos AA) — periodic rules + bundles + relationship pricing
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos / Originar Crédito
Última fase del plan Temenos AA, tres características:
- **Relationship pricing**: bonificación de TNA por la relación integral del cliente
  (`RELACION_PRICING` en productos.py: ESTANDAR 0 / PREFERENCIAL −2 / PREMIUM −4 pts). En `originar`
  se aplica al final (piso 0) sobre la tasa efectiva/negociada y se guarda en el snapshot
  (`relacion`, `bonus_relacion`). FE: selector "Relación" en el perfil + hint "🎁 … TNA final ≈".
- **Bundles**: paquetes de productos ofrecidos juntos. Tablas `pp_bundle` + `pp_bundle_item`
  (rol PRINCIPAL/COMPLEMENTO, obligatorio, orden). `GET /contratos/bundles` devuelve el bundle con
  sus miembros (líneas serializadas). Seed: `BND-CAP-01 "Paquete Créditos CaPreSCa"` (LP-PERS-01
  principal + LP-JUB-01 complemento). FE: sección "📦 Paquetes" en Originar con botón por miembro.
- **Periodic rules (repricing)**: componente `PERIODIC` (repricingFrecuencia/capitalizaInteres/
  diaAplicacion) + actividad de servicing `REPRICING` que recalcula la TNA de una línea de tasa
  variable desde el índice vigente (índice+margen+bonus). Nueva línea seed `LP-VAR-01` (VARIABLE
  BADLAR margen 10). El repricing guarda `dato={tasa_anterior,tasa_nueva,...}` y `_recompute`
  reconstruye la tasa (base snapshot + REPRICING no reversados), por lo que la **reversa** restaura
  la TNA. FIJA → 422. FE: botón "🔁 Repricing (índice)" sólo en contratos variables.
**Tests**: +4 (`test_relationship_pricing_descuenta_tna`, `test_bundles_listado`,
`test_repricing_periodico_actualiza_tna_variable`, ya con reversa) → **suite completa 189 passed**.
`tsc` limpio. Verificado en browser: PREMIUM → "TNA final ≈ 48%"; bundle con sus 2 miembros; repricing
de LP-VAR-01 asienta REPRICING (BADLAR 45%+margen 10%) con reversa. **Plan Temenos AA (A–G) COMPLETO.**

## H-063 · Fase F (plan Temenos AA) — servicing: backdating y reversa de actividades
**Fecha:** 2026-08-07 · **Módulo:** Originar Crédito (servicing)
Temenos: *activity-based processing* con fecha valor (backdating) y reversa. El servicing pasó a un
modelo **event-sourced**: `_recompute(c)` reconstruye el estado del contrato reproduciendo las
actividades **no reversadas** en orden de fecha valor sobre el cronograma pristino (los importes de
cada cuota no cambian con los pagos, sólo su `estado`/`pagado` y el `saldo_capital`). Así el backdating
reordena y la reversa es sólo marcar+recomputar. Modelo: `pp_actividad.reversa_de` (auto-FK) + estado
`REVERSADA`; entrada `REVERSAL` que apunta a la revertida. Endpoints: `POST /{id}/actividad` acepta
`fecha` (validada: no futura, no anterior al desembolso) y recomputa; nuevo
`POST /{id}/actividad/{actId}/reversar` (no permite reversar DISBURSEMENT ni REVERSAL, ni reversar dos
veces → 409). Frontend (OriginarCredito): campo **Fecha valor (backdating)** en la barra de servicing,
y en el log de actividades badge `REVERSADA` (tachado) + botón **↩** por actividad reversable.
**Tests**: +2 (`test_backdating_y_reversa`: pago con fecha valor pasada, fecha futura 422, reversa
devuelve la cuota a PENDIENTE + saldo restaurado + doble reversa 409; `test_reversa_de_payoff_reabre_contrato`:
payoff cierra y su reversa reabre el contrato) → **contratos 11 passed**. `tsc` limpio. Verificado en
browser: pago cuota 1 ($82.413) → reversa → PAYMENT REVERSADA + entrada REVERSAL + cuota 1 vuelve a
"pendiente".

## H-062 · Fase E (plan Temenos AA) — disponibilidad / segmentación de la oferta
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos / Originar Crédito
Temenos: la **Availability** de un producto define a quién y por qué canal se ofrece (segmentos,
canales, edad, antigüedad, vigencia). El componente `AVAILABILITY` (ya existía como placeholder) pasó a
ser una condición estructurada: `segmentos`/`canales` como **listas**, `edadMin`/`edadMax`,
`antiguedadMinMeses`, `requiereGarante`, `vigenteDesde`/`vigenteHasta`. Backend (`api/productos.py`):
catálogos `SEGMENTOS_CATALOGO`/`CANALES_CATALOGO`, `_disponibilidad(v)` (normaliza, None si el
componente está inactivo → sin restricción) y `_elegibilidad(disp, ctx)` (motivos por atributo; las
reglas de segmento/canal/edad/antigüedad sólo aplican si el dato viene en el contexto; la vigencia
siempre). `GET /contratos/segmentos` expone los catálogos; `GET /contratos/oferta` acepta
`segmento/canal/edad/antiguedad_meses/solo_elegibles` y anota cada ítem con `elegibilidad`
(elegible + motivos); `POST /contratos/originar` rechaza (422) si el solicitante no cumple. Seed:
LP-PERS-01 (AGENTE_PUBLICO/DOCENTE/MUNICIPAL, 18–65) y LP-JUB-01 (JUBILADO/PENSIONADO, 60–90) con
disponibilidad real. Frontend: editor propio de AVAILABILITY (chips multi-select de segmentos/canales
+ edad/antigüedad/garante/vigencia) en el builder; panel **🎯 Perfil del solicitante** en Originar
Crédito que reevalúa la oferta (cards elegibles ✓ vs ⛔ con motivo, toggle "Sólo elegibles") y pasa el
contexto al originar. **Tests**: +2 (`test_disponibilidad_catalogo_y_filtro_oferta`,
`test_originar_respeta_disponibilidad`) → **contratos+productos 25 passed**. `tsc` limpio. Verificado en
browser: con segmento JUBILADO, LP-JUB-01 elegible y LP-PERS-01 "⛔ Segmento JUBILADO no habilitado".

## H-061 · Fase D (plan Temenos AA) — herencia de productos / familias
**Fecha:** 2026-08-07 · **Módulo:** Configurar Créditos
Temenos: un producto puede **derivar** de un padre (Product Inheritance / familias); el hijo guarda
sólo los **deltas** y hereda el resto, y los cambios del padre **se propagan** a los hijos que siguen
heredando. Implementado: `pp_producto.padre_id` (auto-FK), `pp_producto_version.cfg_heredada` (las
condiciones generales — sistema, tasa, plazo, montos — se heredan como bloque), `pp_producto_componente.heredado`
(por componente). Resolución en `_serial_v`: si hay padre, se resuelve el padre y se rellenan `cfg`
(si `cfg_heredada`) y los componentes marcados `heredado` con los valores vigentes del padre — es
**dinámico** (relee al padre en cada lectura, así el cambio del padre se ve en el hijo). Al crear:
`POST /productos {padre_id}` clona la plantilla del padre marcando todo como heredado; distinto de
`copiar_de`, que es una **copia independiente** (snapshot que evoluciona sola). Tocar cualquier
condición apaga su flag de herencia (queda **propio**); botón **↩ Volver a heredar** (por componente
y para las generales) que guarda con el flag en `true` y re-resuelve del padre. Frontend: modal de
creación con radio **Copia independiente / Derivar (hereda del padre)**, acción de tarjeta "Crear
derivado (hereda)", banner 🧬 "Deriva de …" en el builder, badges **🧬 HEREDADO / PROPIO** e indicador
🧬 en el catálogo. **Tests**: +1 (`test_herencia_deriva_de_padre`: hereda TNA del padre, el cambio del
padre se propaga, personalizar corta la propagación) → **16 passed** (suite productos). `tsc` limpio.
Verificado en browser con dato real: derivado de **LP-JUB-01** (FRANCES 41%) hereda monto/plazo/TNA;
editar Monto marca generales "propias" + botón; "Volver a heredar" restaura 100000 del padre.

## H-060 · Fase C (plan Temenos AA) — propiedades nombradas por componente (Intereses)
**Fecha:** 2026-08-06 · **Módulo:** Configurar Créditos
Temenos: una Property Class (Interés) puede tener varias **Properties** con nombre (compensatorio,
punitorio, comisión). Se generalizó el patrón de "varios ítems" (que ya tenían Cargos e Impuestos)
también a **Intereses**: `INTEREST` ahora edita una lista de **Propiedades de interés adicionales**
(cada una: Nombre · Tipo [COMPENSATORIO/PROMOCIONAL/COMISION] · TNA %), con agregar/quitar. El
interés compensatorio principal + su banda/negociación siguen siendo el núcleo (manejan el
simulador); las propiedades adicionales son parte de la definición del producto. Se guardan en
`config.items` (JSON, sin cambio de esquema). Etiquetas del editor de ítems generalizadas
(`ITEM_TITULO`/`ITEM_SINGULAR`). Validación por componente para las propiedades (nombre requerido,
TNA 0–500%). **Tests**: +1 (propiedades de interés persisten) → **suite 181 passed** (estimado).
`tsc` limpio. Verificado en browser: alta de "Interés promocional 3 meses" persistida en LP-NUEVA-06.

## H-059 · Fase B (plan Temenos AA) — reglas de negociación (banda de TNA) enforzadas al originar
**Fecha:** 2026-08-06 · **Módulo:** Configurar Créditos + Originar Crédito
Inspirado en Temenos AA (condiciones con default + reglas de negociación min/max; si no es
negociable, la condición queda fija):
- **Banda de TNA por producto**: en el componente Intereses (modalidad FIJA) se define
  **¿Tasa negociable?** y, si sí, la **banda TNA mín/máx**. Persiste en `pp_producto_tasa`
  (nuevas columnas `tasa_minima`, `tasa_maxima`, `negociable`); cfg expone
  `tnaNegociable/tnaMin/tnaMax`. Validación por componente: banda coherente y TNA base dentro de
  la banda. La lista de condiciones muestra "Negociación al originar: entre X% y Y% ◈ negociable"
  o "fija (no negociable)".
- **Enforce al originar**: `POST /contratos/originar` acepta `tasa` (opcional). Sólo se permite si
  la línea es negociable (modalidad FIJA); valida `tasa ∈ [tnaMin, tnaMax]` (422 si se sale, 422 si
  la línea no es negociable). Si no se envía, usa la tasa efectiva del producto (fija, o índice+margen
  en variable). La pantalla Originar muestra el input "Tasa negociada" con la banda y bloquea el botón
  fuera de rango.
**Tests**: +3 (banda persiste; originar dentro/fuera de banda; línea no negociable) → **suite 180
passed**. `tsc` limpio. Verificado en browser: builder con banda 40–60; Originar con
70→bloqueado, 47→ok.

## H-058 · Fase A (plan Temenos AA) — biblioteca de condiciones: Impuestos + Índices + tasa variable
**Fecha:** 2026-08-06 · **Módulo:** Configurar Créditos + Contabilidad
Inspirado en el modelo Temenos AA (Product Conditions como "biblioteca" reutilizable que los
productos referencian):
- **TAX ↔ Maestro de Impuestos**: el componente Impuestos de Configurar Créditos ahora elige cada
  ítem de un **impuesto del maestro** (select por código); al elegirlo precarga etiqueta/base/%
  (editable como override). Cierra el "que todo el sistema lo use".
- **Maestro de Índices de referencia** (nuevo, `Contabilidad → Índices`): modelo `indices_referencia`
  (codigo/nombre/valor/fuente/fecha/activo), `app/api/indices.py` (ABM), seed (BADLAR 45%, TPM 40%,
  UVA 30%), pantalla `pages/contabilidad/Indices.tsx`.
- **Tasa variable en INTEREST**: modalidad VARIABLE muestra **índice (del maestro) + margen**; la
  **tasa efectiva = valor del índice + margen** alimenta el simulador y el cronograma. Se persiste en
  `pp_producto_tasa` (nuevas columnas `indice_referencia`, `margen`); cfg expone `indice`/`margen`.
`app/api/productos.py` mapea cfg↔tasas. **Tests**: +3 → **suite 177 passed**. `tsc` limpio. Verificado
en browser: TAX con IVA21/SELLOS del maestro; INTEREST variable BADLAR+8% → "Tasa efectiva 45%+8%=53%";
pantalla de Índices.

## H-057 · Configurar Créditos — 3 arreglos + Maestro de Impuestos (Contabilidad)
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos + Contabilidad → Impuestos
- **Tilde con sentido**: el ✓ ya no es "siempre activo". Estado real por componente: **✓ revisado**
  (visitado o personalizado, sin errores), **○ activo sin revisar** (pendiente), **! error**, **＋
  no agregado**. El subtítulo muestra "Requerido" en los obligatorios; la guía dice "Revisados N de M".
- **Borrar borradores/revisión**: `DELETE /api/productos/{id}` — si la última versión está en
  BORRADOR/EN_REVISION la borra (línea completa si es v1; sólo la versión si hay publicadas debajo);
  409 si está publicada/aprobada/retirada. Acción "Borrar" en el menú de la tarjeta (gateada por perfil).
- **Maestro de Impuestos** (nuevo, `Contabilidad → Impuestos`): modelo `impuestos` (general del
  sistema: codigo/nombre/tipo/alícuota/base/cuenta_contable/jurisdicción/vigencias/activo),
  `app/api/impuestos.py` (ABM list/crear/editar/baja/reactivar), seed de 4 (IVA21, IVA10.5,
  IIBB-CAT, SELLOS), pantalla `pages/contabilidad/Impuestos.tsx` con DataTable + form. Pensado para
  que cualquier módulo lo referencie (próximo: el componente TAX de Configurar Créditos elige de acá).
**Tests**: +3 (borrar, impuestos ABM ×2) → **suite 175 passed**. `tsc` limpio. Verificado en browser.

## H-056 · Configurar Créditos — historial y comparación de versiones (diff)
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos
Backend: `GET /api/productos/{id}/versiones` devuelve **todas** las versiones serializadas
(cfg + componentes + estado + auditoría) — se refactorizó `_serial` a `_serial_v(prod, v)` para
reusarlo. Frontend: botón **"⇄ Comparar"** en el builder abre un modal con dos selectores de
versión (A/B, por defecto las dos últimas) y una **tabla de diferencias** campo por campo:
condiciones (sistema, TNA, montos, plazos, cargo, mora…) y componentes (activado/desactivado, o
config cambiada), con el valor de A en rojo y el de B en verde. Muestra "Sin diferencias" cuando
coinciden. **Tests**: +1 (endpoint de versiones para diff) → **suite 172 passed**. `tsc` limpio.
Verificado en browser: v3 (Publicado) vs v4 (Borrador) → 2 diferencias (TNA 52→61, Disponibilidad
No→Sí). Con esto quedan cubiertas las 4 ideas de mejora del diseño de componentes.

## H-055 · Configurar Créditos — múltiples instancias, validación por componente y "tocado vs default"
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos
- **Múltiples instancias (varios cargos / impuestos)**: los componentes `multiple`
  (CHARGE, TAX) editan una **lista de ítems** (Cargos: etiqueta/%/momento; Impuestos:
  etiqueta/base/%), con agregar/quitar por ítem. Se guardan en `config.items` (JSON), sin
  cambio de esquema. Default de TAX pasó a 3 ítems (IVA interés/cargos, sellado).
- **Validación por componente**: `valida(codigo, config, cfg)` con reglas por tipo (rangos de
  %, día de pago 1–28, montos/plazos, penalidad, etc.). Se muestra un **banner rojo** en el
  editor con los problemas, un **⚠** en la paleta, y **suma a la validación global** (bloquea
  Publicar).
- **Tocado vs. por defecto**: `esDefault(...)` compara la config efectiva con los valores por
  defecto; el header muestra **POR DEFECTO / PERSONALIZADO** y la paleta un **•** en los
  componentes personalizados — para saber de un vistazo qué se cambió respecto de la plantilla.
Frontend puro (la config JSON ya se persistía); sólo cambió el default de TAX/CHARGE en
`app/productos_componentes.py`. **Tests**: +1 (múltiples ítems persisten) → **suite 171 passed**.
`tsc` limpio. Verificado en browser: TAX 3→4 impuestos, % 150 → ⚠ + banner + bloqueo,
badge PERSONALIZADO al editar y POR DEFECTO sin tocar, Cargos con otorgamiento core + ítems.

## H-054 · Configurar Créditos — diseño guiado por componentes + inspector de datos
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos
Profundización del builder (a pedido, foco exclusivo en Configurar Créditos):
- **Crear**: diálogo con **nombre**, **familia** y **copiar configuración de** otra línea (clona
  cfg + tasas + cargos + componentes con su config). Backend `POST /productos` acepta
  `{nombre, familia_id, copiar_de}`; también acción "Duplicar como nueva" en el menú de cada tarjeta.
- **Editores reales por componente**: cada Property Class tiene su editor tipado —
  Cronograma (día de pago, 1er vto, ajuste fin de semana, tipo de cuota), Reglas de pago (orden de
  imputación, tolerancia, pago parcial, adelanto), Impuestos (IVA interés/cargos, sellado, IIBB),
  Cancelación anticipada (permite, penalidad, mín. cuotas, condona interés), Contabilidad (cuentas
  capital/interés/IVA/mora, centro de costo), Disponibilidad (canales, segmentos, garante, vigencias),
  Liquidación, Restricción de actividades, + los core (Importe/plazo, Intereses, Cargos, Mora).
  La config se guarda como JSON en `pp_producto_componente.config` (equivalente a
  esquema_configuracion del modelo).
- **Agregar/quitar componentes**: los que están vacíos aparecen en la paleta con "＋"; el editor
  ofrece "Agregar/Quitar componente" (los requeridos no se pueden quitar). Persiste en PUT /config.
- **Guía**: "Componente X de N" con barra de progreso y botón "Siguiente componente →".
- **Probar en vivo como opción**: el simulador + validación + cronograma ahora se muestran con un
  toggle "▶ Probar en vivo" (no ocupan pantalla mientras diseñás).
- **Inspector de datos (control)**: drawer "🔍 Datos" con dos pestañas: **Datos guardados**
  (`GET /productos/{id}/raw` = filas reales persistidas) y **Modelo de datos**
  (`GET /productos/_modelo` = 15 tablas `pp_*` con columnas, PK/FK).
Módulo compartido `app/productos_componentes.py` (catálogo de 12 componentes + config por defecto).
**Tests**: +3 (config componentes agregar/quitar, copiar_de clona, inspector modelo/raw) →
`test_productos.py` (11). **Suite total: 170 passed.** `tsc` limpio. Verificado en browser: crear
copiando, editor de Impuestos/Contabilidad, agregar Contabilidad y persistir (visible en el inspector),
probar en vivo (24 cuotas), modelo de datos (15 tablas).

## H-053 · Configurar Créditos — Fases 4/5/6: aprobación, oferta y servicing
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos + Originar Crédito
- **Fase 4 — Workflow de aprobación con permisos.** Estados completos
  BORRADOR→EN_REVISION→APROBADO→PUBLICADO→RETIRADO (+ rechazar). Roles: *diseñador*
  (crea/edita/envía) = ADMG o `XCR`; *aprobador* (aprueba/publica/retira) = ADMG. **Cuatro ojos**:
  el aprobador no puede ser quien envió a revisión (409). Auditoría `enviado_por/aprobado_por/
  publicado_por` en `pp_producto_version`. La API gatea con 403 por perfil; el catálogo devuelve
  `permisos`. El frontend muestra botones contextuales (Rechazar/Aprobar/Publicar) gateados y la
  línea de auditoría. Seed: "Adelanto de Haberes" queda EN_REVISION enviado por `creditos` para
  demostrar el cuatro-ojos (admin lo aprueba).
- **Fase 5 — Oferta a clientes + originación.** Nueva pantalla **Originar Crédito**
  (`/creditos/originar`). `GET /api/contratos/oferta` sólo devuelve versiones PUBLICADAS.
  `POST /api/contratos/originar` valida monto/plazo contra la versión, calcula el cronograma
  server-side (`app/services/productos_calc.py`, port del simulador: francés/alemán/americano/
  bullet; la última cuota salda exacto), crea `pp_contrato` con **snapshot congelado** +
  `pp_cuota_contrato` + actividad DISBURSEMENT. Rechaza originar sobre no-publicada (409).
- **Fase 6 — Servicing.** `POST /api/contratos/{id}/actividad`: **PAYMENT** (marca cuota PAGADA,
  baja saldo, cierra si todas pagas), **PAYOFF** (salda remanente, CERRADO), y registro de
  RATE_CHANGE/PREPAYMENT/etc. Un contrato CERRADO no admite más actividades (409). La pantalla
  muestra cronograma + actividades + botones Pagar/Cancelación total.
**Tests**: `tests/test_productos.py` (8) + `tests/test_contratos.py` (4). **Suite total: 167
passed.** `tsc` limpio. Verificado en browser: aprobación cuatro-ojos, oferta sólo publicados (2),
originar CTO con snapshot congelado (24 cuotas), pago de cuota, payoff.
**Roadmap Configurar Créditos: COMPLETO (Fases 1–6).**

## H-052 · Configurar Créditos — Fase 3: persistencia (backend + API + tests)
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos (backend)
Se persistió la plataforma de productos contra tablas reales (antes era in-memory).
- **Modelos** `app/models_productos.py` (tablas namespaced `pp_*`, IDs string uuid4 y tipos
  portables PG+SQLite): moneda, calculador(+version), componente_definicion, linea/grupo/familia,
  producto, producto_version, tasa, cargo, componente. Deriva del DDL del modelo lógico.
- **Seed** `app/seed_productos.py` (idempotente): referencia (ARS/USD, 4 calculadores certificados,
  10 componentes, catálogo LENDING) + 4 líneas de ejemplo con versión/tasas/cargo/componentes. Se
  llama SIEMPRE en el startup (el catálogo aún no tiene ETL) con guard propio; `environment=production`
  por eso el `seed()` legacy no corre solo.
- **API** `app/api/productos.py` (`/api/productos`, con auth): GET catálogo, POST crear, GET detalle,
  **PUT config** (409 si la versión es PUBLICADA/RETIRADA → inmutabilidad), **POST nueva-version**
  (deriva BORRADOR de la vigente, copia tasas/cargos/componentes, `derivada_de`), **POST estado**
  (revisar/publicar/retirar/reactivar; publicar valida integridad → 422).
- **Frontend**: `ConfigurarCreditos.tsx` ahora carga el catálogo del backend y persiste todas las
  acciones (`api.pp*`); las ediciones de cfg se guardan al Guardar borrador / Enviar a revisión /
  Publicar.
- **Tests** `tests/test_productos.py` (5): catálogo sembrado, crear, modificar-publicada-es-inmutable
  (409) + nueva versión, publicar-valida-integridad (422), retirar/reactivar. **Suite: 160 passed.**
`tsc` limpio. Verificado end-to-end en browser: catálogo desde backend (4 líneas), nueva versión
v3→v4 con tna 60 persistida, publicar→[3,4], editar publicada→409, crear UI→LP-NUEVA-05 persistido.

## H-051 · Configurar Créditos — Fase 2: catálogo de líneas (crear / modificar / retirar)
**Fecha:** 2026-08-06 · **Módulo:** Créditos → Configurar Créditos
Se agregó el **catálogo de líneas** como vista inicial del módulo (grilla de tarjetas por
producto con estado, código, versión, TNA/sistema/rangos y menú ⋮), y el ciclo de vida de una
línea ofrecible a clientes, fiel al modelo (inmutabilidad + versionado + snapshot):
- **Crear nueva línea**: nuevo producto BORRADOR v1 → abre el builder.
- **Modificar**: sobre una versión **PUBLICADA/RETIRADA** crea una **versión nueva** (BORRADOR,
  derivada de vN, con banner "v3 sigue vigente hasta publicar la nueva"); sobre BORRADOR edita directo.
- **Retirar aunque esté vigente**: confirm que aclara que **no afecta contratos ya originados**
  (cada contrato conserva `snapshot_producto`); estado → RETIRADO. **Reactivar** vuelve a
  PUBLICADO (si tuvo publicaciones) o BORRADOR.
- Estados con workflow en el builder: Enviar a revisión (BORRADOR→EN_REVISION), **Publicar**
  (habilitado sólo si validación OK y no ya publicada) suma la versión a `publicadas`.
Verificado end-to-end en browser: nueva versión v3→v4, publicar→PUBLICADO ("3 versiones
publicadas"), retirar→RETIRADO, crear→"Nueva línea de crédito" BORRADOR. `tsc` limpio, sin
errores de consola. **Roadmap**: Fase 3 persistencia (migrador + modelos + API), Fase 4 workflow
de aprobación con permisos, Fase 5 conectar producto PUBLICADO con Solicitudes/originación,
Fase 6 servicing.

## H-050 · Configurar Créditos — Product Builder estilo Temenos AA (nuevo módulo)
**Fecha:** 2026-08-06 · **Módulo:** Créditos (nuevo, self-contained)
Nueva pantalla **Créditos → Configurar Créditos** (`/creditos/configurar`,
`pages/creditos/ConfigurarCreditos.tsx`), pedida a partir de la carpeta
`/Users/hernan/Documents/Codex/prestamos/` (modelo lógico + mock "Blu Lending Studio").
Es un **product builder estilo Temenos AA (Arrangement Architecture)** que mapea el modelo
lógico de productos de préstamo: catálogo línea→grupo→familia→producto→**versión**,
**componentes** (Property Classes: TERM_AMOUNT, INTEREST, CHARGE, OVERDUE…) + condiciones
tipadas con **vigencia** y **negociabilidad**, **calculador certificado y versionado**
(Francés/Alemán/Americano/**Bullet**), y **simulación en vivo** reproducible (snapshot +
checksum + expiración) con cronograma proyectado. Mejoras sobre el mock: barra de ciclo de
vida con regla de inmutabilidad, panel de **validación de integridad** en vivo (Σ capital =
monto, saldo final = 0, montos/plazos en rango) que **habilita/bloquea "Publicar"**, y CFT.
Temado con la identidad Capresca (azul institucional) + claro/oscuro; estilos scopeados bajo
`.cfgc` en styles.css. **Etapa 1 = frontend self-contained** (calculadores en JS). **Etapa 2
(pendiente):** persistir contra las tablas del modelo (`producto_version`,
`producto_componente`, `componente_condicion`, `producto_tasa`, `simulacion`, `cuota_simulada`)
— el DDL está en `Codex/prestamos/outputs/schema-productos-prestamos-postgresql.sql`.
`tsc` limpio; verificado en browser (10 componentes, cronograma 24 cuotas, orden/validación en
vivo: montoMin>monto → 1 bloqueo y Publicar deshabilitado; Alemán → capital constante).

## H-049 · Rollout estándar de listas — cierre (tesorería, seguros, mesa, caja, contabilidad, juegos, despacho, general)
**Fecha:** 2026-08-06 · **Módulo:** transversal (resto de la app)
Se completó la propagación del estándar (orden visible ↕/▲▼ · paginado · menú ⋮ de acciones ·
"✕ Limpiar filtros") con `DataTable` + `RowMenu` + `LimpiarFiltros`. `tsc` limpio; sin errores de
consola; verificado MaestroJuegos ("1–25 de 47", orden).
- **Tesorería**: Chequeras (DataTable). Server-paginadas → sólo **Limpiar filtros** (orden es del
  backend): BuscaEgresos, AutorizacionesOP, ChequesEmitidos. ReporteOP no migrada (tiene `tfoot`).
- **Seguros**: Regimenes (beneficiarios). Polizas server-paginada → Limpiar filtros.
- **Mesa**: TramitesIngresados (+Limpiar), Mesa.tsx (llamados/en-espera con menú ⋮ Atender/Cancelar).
- **Caja** (16): migradas ChequesAgencias, CobranzasPeriodo (+Limpiar, saca cap 500), DeudaAgencia
  (+Limpiar), IngresosBrutos, InteresesIva, ReimpresionRecibos (menú ⋮ Reimprimir), PagosRealizados
  (+Limpiar), AgenciaHistorico (2 listas), LiquidacionesCobradas (resumen+detalle), AplicativoQuiniela,
  PremiosQuiniela. No migradas: ControlCaja (agrupada por cajero), RecaudacionAnual (pivot mes×origen),
  PlanillaContable (fila total), PremiosCompensados (grupos), Cobranza (selección con checkboxes).
- **Contabilidad**: ContabilidadGeneral (+Limpiar), CtaCteContable (saldo corrido → paginado + orden
  no-importes), IvaCuotas, BalanceMayor (balance + acción Ver mayor + detalle del mayor), Cierre. No
  migradas: Balance y LibroDiario (totales), IvaPeriodo (sin tabla).
- **Juegos**: MaestroJuegos, FondoGarantia (+Limpiar, acción Ver detalle). IngresosPorJuego no migrada
  (`tfoot` de totales).
- **Despacho**: Modelos (+Limpiar). Anexos no migrada (selección con checkboxes).
- **General**: Parametros.
- **A medida, no migradas**: seguridad/Migradores (dashboard), seguridad/ModeloDatos (DER),
  Simulador (plan de cuotas generado).
**Criterio general:** reportes con fila/`tfoot` de totales, tablas con saldo corrido (sólo paginado),
grillas de selección con checkboxes y matrices pivote se preservan; los importes no se hacen
ordenables donde romperían un acumulado.

## H-048 · Rollout estándar de listas — lote Créditos
**Fecha:** 2026-08-06 · **Módulo:** creditos/*
Aplicado el estándar (orden visible / paginado / menú ⋮ donde hay acciones) con `DataTable`:
- **Listados migrados** (orden + paginado): CuotasMora (saca cap de 100), PendientesCobro, EnviosPadron
  (padrón de débitos), SituacionCliente (créditos del cliente), Jubilados y EstadisticasCartera
  (breakdowns, orden sin paginar).
- **CuentaCorriente**: es un **saldo corrido** → sólo **paginado** (50) y orden por Fecha/Cuota; los
  importes NO son ordenables para no romper el saldo acumulado.
- **ABM/listas con acción → menú ⋮**: LineasCredito (Editar; ahora pagina 398), Solicitudes (Ver detalle).
- **No migradas (con criterio)**: PorCartera (tiene `tfoot` de totales), TurnosAdmin (pantalla de
  acción con preview efímero), CancelacionCredito (detalle de cálculo por cuota), RecalculoCredito
  (comparación Actual/Propuesto con header agrupado). Ya usaban DataTable: ListadoCreditos, SinDebito,
  PagosEnCaja, TurnosOtorgados, InformeCreditos.
`tsc` limpio; verificado LineasCredito (menú ⋮ Editar, orden, "1–25 de 398").

## H-047 · Rollout del estándar de listas — infraestructura + lote general/*
**Fecha:** 2026-08-06 · **Módulo:** transversal (componentes) + general/*
Para aplicar los 3 estándares (orden visible / paginado / limpiar filtros) a toda la app sin
reescribir 60 pantallas a mano, se centralizó en componentes reutilizables:
- **`DataTable`** ahora muestra el indicador de orden en **toda** columna ordenable (↕ inactiva,
  ▲/▼ activa) — antes sólo en la activa; eleva de una vez las 15 pantallas que ya lo usaban.
- **`DataTable` modo cliente**: props `clientSort` + `pageSize` → ordena y pagina en memoria sobre
  `rows` (sin tocar backend). Migrar un maestro chico = reemplazar el `<table>` por `<DataTable
  clientSort pageSize={25}>`. También `sortValue` por columna, `defaultSort`, y `rowStyle(row)`
  para conservar estilos por fila (ej. proveedor anulado).
- **`LimpiarFiltros`** (componente): botón "✕ Limpiar filtros" que sólo aparece cuando hay filtro
  activo; estilo `.btn-limpiar`.
**Lote 1 — Maestros `general/*` migrados a DataTable** (orden + paginado + limpiar donde hay filtro):
Organismos (ya no corta en 50 → pagina **3.686**), Compañías, Perfiles, Oficinas (+limpiar),
Proveedores (+limpiar, conserva anulado), Usuarios. `tsc` limpio; verificado en Organismos
(Nombre▲, "1–25 de 3.686"). **Pendiente:** lotes por módulo (créditos/consultas, tesorería, caja,
seguros, mesa, contabilidad) — en reportes de **agregados** (balances, libro diario, cta cte) se
aplica orden donde tiene sentido pero **no** paginado que rompa subtotales.

## H-046 · Estándar de listas: menú ⋮ de acciones (Opción 3) + orden visible + limpiar filtros + paginado
**Fecha:** 2026-08-06 · **Módulo:** Clientes (piloto) / transversal
Patrón de UX para las listas de la app. Primero se probó la **Opción 1** (barra al seleccionar fila);
el usuario luego pidió cambiar a la **Opción 3**: **menú "⋮" por fila** con las acciones, pero en la
**primera columna**, con el encabezado como **ícono** (no la palabra "Acciones") e **iconos modernos**
(línea, estilo Lucide). Implementado con componentes reutilizables:
- **`RowMenu`** (`components/RowMenu.tsx`): botón ⋮ (`more-vertical`) que abre un menú flotante
  (`position:fixed`, alineado a la izquierda del botón con clamp para no cortarse en el scroll de la
  tabla; cierra con click afuera / Escape / scroll). Cada acción = `{label, icon, onClick, danger, hidden}`.
- **`DataTable` prop `actions`**: agrega una primera columna con el ⋮; header con ícono `row-actions`.
- Iconos nuevos en `Icon.tsx`: `more-vertical`, `edit`, `eye`, `ban`, `rotate-ccw`, `row-actions`,
  `key`, `trash`.
Estándares que el usuario fijó **para toda la app**: (1) **orden con flecha visible** (▲/▼ activa, ↕
ordenables); (2) **"✕ Limpiar filtros"** (`components/LimpiarFiltros.tsx`), visible sólo con filtro
activo; (3) **paginado** con total. Verificado en el **Maestro de clientes**: columna 1 con ícono,
menú ⋮ → Editar (lápiz) / Ver 360° (ojo) / Dar de baja (círculo-tachado rojo) / Reactivar (según
estado); Editar abre el drawer; orden apellido ▲→▼; total 78.050. `tsc` limpio.

## H-045 · Maestro de clientes convertido en ABM real
**Fecha:** 2026-08-05 · **Módulo:** Clientes
El maestro de clientes era de solo lectura (había GET lista/detalle y POST crear sin UI). Se lo
convirtió en **ABM completo** (a partir de un mock). **Backend:** schema `ClienteBase` ampliado
(sexo, fecha_nac, domicilio, barrio, localidad, teléfono, email, débito, categoría, fecha_ingreso,
tipo) + `ClienteUpdate`/`ClienteBaja`; endpoints **`PUT /clientes/{id}`** (modificación),
**`POST /clientes/{id}/baja`** (baja con motivo → `baja`/`fecha_baja`/`motivo_baja`) y
**`POST /clientes/{id}/reactivar`**; filtro **`estado`** (activos/baja/todos) y `organismo_id` en la
lista. **Fix de robustez:** las columnas tienen largos acotados (ej. `categoria_funcion` VARCHAR(10))
y un valor largo daba **500 (StringDataRightTruncation)** → se agregó **truncado defensivo** por
columna en alta/edición (`_truncar`) + `maxLength` en los inputs. **Frontend:** `Clientes.tsx`
reescrita con toolbar (búsqueda + filtro organismo/estado), tabla con acciones por fila
(Editar · 360° · Baja/Reactivar) y **drawer** de alta/edición con secciones (Identidad, Contacto,
Laboral, Bancario) y validación de CUIL. Verificado end-to-end: PUT 200 con truncado; en la UI editar
teléfono de CAMPOS MONTENEGRO → guardó `3835-999888`, drawer cerró y refrescó la lista; baja/reactivar
200. `tsc` limpio.

## H-044 · Visión 360° rediseñada — ficha profesional con todo enlazado
**Fecha:** 2026-08-05 · **Módulo:** Clientes
A partir de un mock aprobado, se rediseñó la Visión 360° con nivel de **ficha profesional**:
cabecera (avatar con iniciales, CUIL/DNI formateados, organismo enlazado, estado), **tira de KPIs**
(créditos activos, deuda, margen, pólizas, egresos históricos), panel **Identidad y contacto**, y
**Situación crediticia** con **barra de afectación del haber** (%, tope, margen). Datos enriquecidos
en el backend: `afectacion_pct`, `creditos_total`, `organismo_id`, y **cta. cte. de seguros**
(`ctacte_seguros` por CUIL) — que estaba migrada sin pantalla y ahora se muestra. **Todo el dato es
navegable por link:** cada crédito → *Cuenta corriente* (`?credito=`) + *Cta. cte. contable*
(`?no_credito=`); pólizas → *Seguros* (`?q=CUIL`); egresos → *Busca egresos* (`?modo=cuil&valor=`);
organismo → *Organismos*; teléfono/email → `tel:`/`mailto:`. Para que los links funcionen, se agregó
**auto-búsqueda por query-param** a las pantallas destino (CtaCteContable, BuscaEgresos, Polizas,
CuentaCorriente). Verificado en vivo con MUÑOZ Y PEREZ (id 36324): ficha completa, cta. cte. seguros
21 cargos $140,95, 7 egresos $52.725,34, y el link "Cta. cte. contable" navega y auto-carga el
crédito 123153. `tsc` limpio.
**Ampliación — navegación bidireccional.** (a) La 360 acepta `?cliente=<id>` y **auto-carga** esa
ficha (URL compartible/deep-link). (b) Cada link a un detalle lleva `&volver=<cliente_id>`, y las
pantallas destino (CtaCteContable, CuentaCorriente, Polizas, BuscaEgresos, Organismos, Tramites)
muestran un banner **"← Volver a la ficha 360° del cliente"** (componente `VolverFicha`) que regresa
a `/clientes/vision-360?cliente=<id>`. (c) Los destinos **filtran al cliente**: p.ej. Busca egresos
abre auto-filtrado por CUIL mostrando sólo sus movimientos. Se arreglaron los anchors anidados de la
fila de crédito (ahora dos sublinks explícitos). Verificado el ida y vuelta con MUÑOZ (id 36324):
360 → egresos (7 mov. filtrados, $52.725,34, con banner) → volver → 360.

## H-042 · Nuevo módulo Clientes con Visión 360° (agrega créditos + seguros + pagos + trámites)
**Fecha:** 2026-08-05 · **Módulo:** Clientes (nuevo)
A pedido: se creó el módulo **Clientes** arriba de todo en el menú (y se quitaron los números de
los módulos, manteniendo el orden). Contiene **Visión 360° del cliente** (`/clientes/vision-360`) y
el **Maestro de clientes (ABM)** movido desde General (`/clientes/maestro`; `/general/clientes`
redirige). La Visión 360 busca por CUIL/DNI/nombre y arma un tablero con **todo lo que el sistema
sabe del cliente**: datos personales/laborales (organismo, sueldo, CBU, débito), situación
crediticia (créditos, saldos, margen — reusa `situacion_cliente`), **pólizas de seguro de vida**
(por CUIL sobre `PolizaAgente`), **pagos en caja** (recibos por `cliente_id`) y **trámites** de mesa
(por DNI/CUIL). Servicio `consultas.vision_360` + endpoint
`GET /creditos/consultas/cliente/{id}/vision-360`. **Verificado con dato real:** cliente ABALLAY
JONATHAN ALEJANDRO → 1 crédito activo (línea AGAP con garante), margen $3.221, 2 pólizas vigentes
(Subsidio Prot. Familia + Sepelio, alta 2010), organismo Adm. Municipal La Puerta de San José.
Endpoint 200 / 404 si no existe. `tsc` sin errores.
**Ampliación (mismo día):** (a) el **84% de las pólizas** del legacy tienen `no_poliza=0` en origen —
se muestra "s/n°" en vez de "—" (fiel); (b) **no hay recibos migrados** (los "pagos en caja" solo
surgen de cobros en la app), así que se agregó el panel **Egresos / liquidaciones** desde el ledger
real (`Egreso` por CUIL) — historial financiero real por cliente; (c) el panel de créditos ahora
muestra **Capital y Cuotas** y una nota: de 3.559 créditos "Activos", **1.384 tienen saldo $0** — en
muchos es un registro **sin detalle financiero migrado** (capital 0, 0 cuotas), no un préstamo
pagado; el estado "Activo" viene tal cual del legacy. Verificado con MONTENEGRO JUAN CARLOS: pólizas
34316/11705 numeradas + 3 egresos por $23.587,52 (liq. 2012-2015).

## H-041 · Rediseño UX/UI aplicado — sistema de tokens claro/oscuro, riel izquierdo e íconos SVG
**Fecha:** 2026-08-05 · **Módulo:** Frontend (transversal)
Se aplicó a toda la app la propuesta de UX/UI (partió de un mock aprobado). Cambios en
`frontend/src/styles.css` + componentes: **sistema de tokens** (color/tipografía/espaciado) con
**tema claro y oscuro** (por `data-theme` + `prefers-color-scheme`, toggle en la topbar que
persiste en `localStorage`); **riel de navegación a la izquierda** (antes a la derecha) con la
marca institucional; **topbar** con búsqueda global, campana y chip de usuario (nombre/perfil
leídos del JWT); cifras con **`tabular-nums`** monoespaciadas; cards, inputs, botones, tablas
(header fijo, hover por fila) y **pills de estado** restilados. Se mantiene el **azul institucional
`#14428a`** como acento; los semánticos (ok/alerta/crítico) quedaron separados del acento. Los
**emojis del menú se reemplazaron por íconos SVG de línea** (nuevo `components/Icon.tsx`, estilo
Lucide) para los 10 módulos + utilidades. Como las ~40 pantallas comparten las clases
(`.card`, `table`, `input`, `button`, `.muted`…), todas heredaron el look sin tocarlas una por una.
Verificado en el navegador (tema claro y oscuro) y `tsc --noEmit` sin errores.

## H-040 · El ledger real de egresos (340 mil) está en el backup — Busca transacciones de egresos (81505) sobre dato real
**Fecha:** 2026-08-05 · **Módulo:** Tesorería / Egresos
**Evidencia:** la pantalla **Busca transacciones de egresos** (menú 81505) corría sobre `OrdenPago`
(3.078 filas). El ledger real de pagos es `Egresos/egresos.dbf` = **339.903 egresos** (140 MB, 53
columnas: liquidación, resolución, crédito, OP, cheque, recibo, importe/retenciones/total, pagado,
anulado). Leyendo el fuente (`frm815050000buscaegresos`, H-026), el form busca por 7 modos
(optiongroup1): **apellido/nombre (subcadena), CUIL, nº recibo, nº resolución, fecha resolución,
nº OP, fecha OP**, y muestra 11 columnas. **Impacto:** nuevo modelo `Egreso` + ETL
(`cargar_egresos_ledger`) → **339.903 egresos migrados**; servicio `buscar_egresos` fiel a los 7
modos; endpoint `GET /egresos/buscar`; pantalla `/tesoreria/egresos` (Tesorería → Consultas).
**Verificado contra la base real:** 339.903 egresos (TOTAL $30.416M; 2.932 anulados; 332.109 pagados);
OP N° 486 → 109 egresos $46.676.339,88; apellido "PEREZ" → 1.405; CUIL 20049991607 → 11;
modo inválido → 400. El `sum(total)` usa `sub.c.total` (evita el producto cartesiano, cf. H-038).
Front sin errores TS.

## H-039 · El backup es un sistema en producción vivo (auditoría a 2026-08-03) — reportes de auditoría por usuario/máquina
**Fecha:** 2026-08-05 · **Módulo:** General
**Evidencia:** revisando **General → Auditoría**, sólo había un log paginado; faltaban los
reportes X3005 (por usuario) y X3010 (por máquina). Al verificar el origen: `General/auditoria.dbf`
= **6.486.913 eventos** (953 MB) y **sus últimas filas son de 2026-08-03** con usuarios reales
(crockb, lobom, Ferreyrar) — o sea, **el backup es de un sistema todavía en producción** (no un
volcado viejo); las fechas 2026 de la muestra migrada **son reales**, no sintéticas. La muestra
cargada (`cargar_auditoria`, últimos 50.000) es dato real fiel. **Impacto:** función `auditoria.resumen`
(agrupa por usuario o máquina: eventos, procesos distintos, primer/último evento) + endpoint
`GET /admin/auditoria/resumen?por=usuario|maquina`; pantalla `/general/auditoria` con pestañas
**Detalle / Por usuario / Por máquina**. **Verificado contra la base real:** 50.098 eventos, 48
usuarios (crockb 12.308 · orellanaa 5.531 · ADAROA 5.306) y 48 máquinas (PB02CAJA 12.477 ·
SP9876COMP 6.307 · PP0506CRED 5.524). Endpoint por HTTP OK. Front sin errores TS. **Nota:** se
informa explícitamente que es una **muestra de los últimos ~50 mil** eventos del log; migrar los
6,5M completos es un ETL aparte si se necesita el histórico total.

## H-038 · Cheques emitidos (73 mil) y egresos (340 mil) están en el backup — Listado de cheques (83040) con dato real
**Fecha:** 2026-08-05 · **Módulo:** Tesorería / Egresos
**Evidencia:** revisando los reportes 830 de **Tesorería**, el **Listado de cheques emitidos**
(menú 83040) no estaba migrado. El modelo de pagos de la app (`OrdenPago`) tiene sólo **3.078**
filas y con los datos de cheque vacíos. El backup tiene las tablas reales: `Egresos/cheques.dbf`
= **73.276 cheques emitidos** (banco, cuenta, nº cheque, fecha, importe, nº OP/resolución/
liquidación, anulado) y `Egresos/egresos.dbf` = **339.903 egresos** (140 MB, la tabla real de
pagos). **Impacto:** nuevo modelo `ChequeEmitido` + ETL (`cargar_cheques`) → **73.276 cheques
migrados**; servicio `cheques_emitidos` (filtra por fecha/chequera/banco, excluye anulados por
defecto, resumen por tipo de chequera + detalle paginado) y endpoint `GET /egresos/cheques`;
pantalla `/tesoreria/cheques` (Tesorería → Reportes). **Verificado contra la base real:** 73.258
cheques no anulados por **$1.573.715.098,62** (control directo idéntico); por chequera → Créditos
38.757 ($1.069M), Seguros 28.805 ($430M), Juegos 5.425 ($62M), Rentas 271 ($12,7M); 18 anulados;
día 2011-03-22 → 70 cheques $319.748. Endpoint por HTTP 200. **Fix de paso:** el `sum()` de totales
usaba `select_from(subquery)` referenciando la tabla externa (producto cartesiano, mismo patrón que
el fix de `mayor_cuenta`); corregido con `sub.c.importe`. Front sin errores TS. **Nota:**
`egresos.dbf` (340 mil) queda como próximo dato real grande para enriquecer 81505 y los 830.

## H-037 · Liquidaciones de agencia históricas (273 mil) están en el backup — Fondo de Garantía (43025) con dato real
**Fecha:** 2026-08-05 · **Módulo:** Juegos
**Evidencia:** revisando los reportes 430 de **Juegos**, el informe de **Fondo de Garantía**
(menú 43025) no estaba migrado. Leyendo el fuente (`frm430250000infor_f_gara`, H-026) su
consulta es `SELECT * FROM jghisliq UNION ALL SELECT * FROM liquidaciones` filtrado por
agencia y rango de fecha, agrupando el `fdo_gtia` por agencia. La tabla vigente
(`liquidaciones`, 60.000) sólo tenía fondo de garantía en **5 agencias** porque el resto está
**archivado**: `Juegos/jghisliq.DBF` = **273.589 liquidaciones históricas** (37 MB, mismo
esquema, generadas por el proceso 42515). **Impacto:** nuevo modelo `LiquidacionHistorica` +
ETL (`cargar_hisliq`) → **273.589 registros migrados**; servicio `fondo_garantia` que **une
histórico + vigentes** (fiel al form), agrupa por agencia con detalle por juego y filtra por
agencia/fecha; endpoint `GET /juegos/fondo-garantia`; pantalla `/juegos/fondo-garantia`
(Juegos → Reportes). **Verificado contra la base real:** total fondo de garantía
**$199.611,71** (control directo: histórico $45.541,01 + vigentes $154.070,70 = $199.611,71,
cuadra exacto); ahora **667 agencias** con fondo (vs. 5 sólo con las vigentes); agencia 20 →
$100.885,12 con detalle por juego (Quiniela $95.005,50, Quini6 $4.010,31, …). Endpoint
probado por HTTP (200). Front sin errores TS. **Nota:** el histórico enriquece también a
futuro cualquier reporte de agencias que quiera abarcar toda la serie, no sólo este.

## H-036 · Pólizas de seguro de vida por agente (207 mil) están en el backup — pantalla de Seguros con dato real
**Fecha:** 2026-08-05 · **Módulo:** Seguros
**Evidencia:** recorriendo **Seguros → Pólizas** en el navegador, el panel **"Pólizas
vigentes"** mostraba **"Sin pólizas"**. El modelo `Poliza` de la app es la póliza *sobre
un crédito* (se genera al otorgar), por eso está vacío. Pero el backup tiene
`Seguros/seguros.DBF` con **207.500 pólizas de seguro de vida colectivo por agente**
(CODIGO=tipo, NO_POLIZA, CUIL, NO_AGENTE, ESTADO 'A'=activa, CANTIDAD). Los tipos salen de
`paraseguros.dbf`: 1 Subsidio Protección Familia, 2 Sepelio, 3 Vida Obligatorio, 4
Incapacidad, 5 Vida Adicional. **Impacto:** nuevo modelo `PolizaAgente` + ETL
(`cargar_polizas`) → **207.498 pólizas migradas**; servicio `polizas_vigentes` (resumen por
tipo + búsqueda por CUIL/agente/nº póliza + paginado) y endpoint
`GET /seguros/polizas-agente`; panel "Pólizas de seguro de vida (por agente)" en
`/seguros/polizas`. **Verificado contra la base real:** 207.239 vigentes (ESTADO 'A', no
baja); por tipo → Sepelio 94.398, Subsidio Prot. Familia 90.119, Incapacidad 13.286, Vida
Adicional 5.011, Vida Obligatorio 3.763 (coincide con la distribución de CODIGO en el DBF);
búsqueda por CUIL 27066503742 devuelve las 5 pólizas del agente. Endpoint probado por HTTP
(200) con filtro `codigo=2` → 94.398. Front sin errores TS.

## H-035 · El libro mayor real (2M movimientos) está en el backup — Contabilidad con dato real
**Fecha:** 2026-08-05 · **Módulo:** Contabilidad
**Evidencia:** recorriendo Contabilidad en el navegador, el **Libro diario** y el
**Balance** estaban **vacíos** — sólo mostraban asientos generados por operaciones de la
app (casi ninguno). Al revisar el backup: `Contabilidad/asientos.dbf` tiene **2.009.400
movimientos** del **libro mayor real** (CUENTA, FECHA, CPERIO, NDEBITO, NCREDITO,
CREFERENCI). **Impacto:** nuevo modelo `MovimientoContable` + ETL (`cargar_contable`);
**2.009.400 movimientos migrados**. Reportes sobre dato real: **balance de sumas y saldos
por cuenta** (`/contabilidad/mayor/balance`) y **mayor por cuenta** con drill-down
(`/contabilidad/mayor/cuenta?cuenta=`). Verificado: PPS/DE = 940.697 movimientos, débito
$204.633.263,87, crédito $139.746.803,31, saldo $64.886.460,56 (coincide con la DB). El
sub-mayor tiene 4 cuentas deudoras (DFOTO, PPS/DE, PPC/DE, PPMPRO); "cuadra=False" es
correcto (no es el set balanceado completo). Pantalla `/contabilidad/mayor`. **154 tests OK.**

## H-034 · Recorrido de Despacho: oficina por código en vez de nombre (fix)
**Fecha:** 2026-08-05 · **Módulo:** Despacho / Mesa
Recorriendo **Despacho** en el navegador: Modelos (338), Resoluciones, Anexo y
Expedientes renderizan con dato real. En **Expedientes** la columna "Oficina" mostraba el
**código** (35, 0, 8) mientras los *pases* ya resolvían el **nombre**. **Corregido** en
`tramites.consultar`: resuelve `oficina_actual → Oficina.denominacion` (mismo mapa que los
pases), mejorando **Expedientes (Despacho) y Trámites (Mesa)** — ahora muestra
"JG - SUBGERENCIA DE JUEGOS.", "SG - SEGUROS", etc. Aclaraciones del recorrido (no bugs):
Resoluciones tiene el **estado bien migrado** (11.337 borrador + 29.932 firmadas; el
listado mostraba las recientes que son borrador) y el **asunto es placeholder** (el texto
real se genera desde los modelos RTF, no está en la tabla migrada). **153 tests OK.**

## H-033 · Recorrido por el navegador: hallazgos de comportamiento real
**Fecha:** 2026-08-05 · **Módulo:** varios (verificación en la app)
Recorriendo las pantallas ya construidas **en el navegador** (con dato real) aparecieron:
- **Titulares de seguro — orden**: la lista ordenaba por `apellido_nombre`, y los **634 de
  122.784 titulares sin nombre** (0,5%) quedaban **primero** (string vacío ordena antes que
  las letras) → la primera página se veía "vacía". **Corregido**: los sin nombre van al
  final (`ORDER BY (apellido_nombre='') , apellido_nombre`). Verificado: ahora aparecen
  SANTILLAN, PAZ, ABACA… primero.
- **Créditos por cartera — saldo > capital**: observado en la app. Al verificar contra la
  DB es **mezcla de dato real y corrupto**: (a) **599 créditos indexados** con saldo
  legítimamente > capital (ratio hasta 3,34×), y (b) créditos con **capital negativo**
  (ej. cartera 20 suma −$3.960M en crudo) — corrupción del backup ya cubierta por H-023
  (la pantalla ya avisa "6 créditos con saldo negativo excluidos"). No es bug de
  agregación; se deja anotado (dato corrupto, no se altera).

## H-032 · Token vencido → pantallas vacías en silencio (fix de UX transversal)
**Fecha:** 2026-08-05 · **Módulo:** Frontend / auth
**Evidencia:** al abrir la app con un token ausente o vencido, el guard `Private` sólo
verifica que **exista** un token (`getToken()`), así que **renderiza** la pantalla; y
`req()` ante un **401 no limpiaba la sesión ni redirigía** — todas las llamadas fallaban
en silencio y el usuario veía pantallas vacías (ej. "0 cupos") sin saber que debía
re-loguearse. Detectado **mirando el comportamiento real en el navegador** (401 en la red).
**Impacto:** `req()` ahora, ante un 401 (salvo en `/auth/login`), hace `logout()` y
redirige a `/login`. Corrige el comportamiento en **todas** las pantallas de la app.
Verificado además que, con token válido inyectado, la pantalla de cupos de OP renderiza el
dato real (29.504 cupos, autorizado $45.642M, saldo $26.769M). **153 tests OK, tsc OK.**

## H-031 · El recálculo de crédito (32535) tiene el reescrito de plan COMENTADO en el fuente
**Fecha:** 2026-08-05 · **Módulo:** Créditos
**Evidencia:** al leer el código completo de `frm325350000reca` (no inferir), el
procedimiento `recaotros` (recálculo estándar) tiene **comentado** (líneas con `*`) todo
el `REPLACE` de capital/interés/IVA (sdo_cap, capital, interes, iva_interes, TOTAL, …);
lo único **activo** es `REPLACE fecha_vto WITH mccalcre.fvto` — es decir, en producción el
recálculo estándar **sólo reprograma la fecha de vencimiento** de las cuotas no pagadas.
El otro modo `recaportes` (jubilatorio) sí regenera el plan pendiente como **capital puro**
(interés=0), con cuota = 10% del haber jubilatorio y última cuota = resto.
**Impacto:** se reconstruyó el 32535 con esos dos modos exactos + **vista previa
obligatoria** (actual vs propuesto) y sin tocar cuotas pagadas. Además **32537** (recalcula
mora) **no aplica**: la mora se calcula en vivo, no se almacena. Lección del usuario: *ser
riguroso, leer el código, no inferir* — el comportamiento real difería de lo asumido.
**149 tests OK.**

## H-030 · `cajacreseg` (cobros reales de créditos/seguros/extra) está en el backup
**Fecha:** 2026-08-05 · **Módulo:** Caja
**Evidencia:** el lado créditos de los reportes de caja (23015 intereses/IVA, etc.)
sale de `cajacreseg` — la cola/cobros de Créditos, Seguros y Extraordinarios. El
backup lo tiene: `Caja/cajacreseg.DBF` (5.629 registros; CRED 4.935, SEGU 511,
EXTR 181), con interés/IVA normal (INTERES/IVAIN), punitorio (INTERESES/IVA),
seguro/adm, ORIGEN, PAGADO, LREVERTIDA, FECHA_PAGO, CAJERO.
**Impacto:** nuevo modelo `CajaCreSeg` + ETL; **5.629 cobros reales migrados**. Con
esto el **Reporte mensual de intereses e IVA (23015)** usa dato real de créditos +
quiniela (verificado 06/2026: interés $106.178.992,04, IVA $14.565.393,20, coincide
con la DB). También habilita a futuro dato real para 22515 (cola histórica), 23025
(pagos realizados) y 23045 (planilla contable de créditos por día). **135 tests OK**.

## H-029 · La cobranza de agencia salda el total (no admite pago parcial)
**Fecha:** 2026-08-05 · **Módulo:** Caja / Juegos
**Evidencia:** un pago parcial a la agencia 3259 ($230.000 sobre una deuda de
$622.625,80) marcaba **todas** las liquidaciones como pagadas — bug. Al revisar el
dato real: de **31.530 recibos de cobro de agencia, 31.529 tienen
`cobrado_total = total` (exacto) y 0 son parciales**; además **ningún** recibo real
tiene `vuelto ≠ 0`. O sea, en producción la cobranza de agencia **siempre salda el
total**.
**Impacto:** `cobrar_agencia` ahora **exige** que lo entregado cubra la deuda de cada
moneda; si no, rechaza con 409 y no marca nada (verificado contra 3259: 409 + deuda
intacta). Lo aplicado a la deuda es el total (`cobrado_total = total`, como el real) y
el **excedente entregado es el vuelto** (cambio a devolver); la UI deshabilita el
botón y pinta el vuelto en rojo si no cubre. Tests: rechazo de parcial + sobrepago con
vuelto. **131 tests OK**. Lección del usuario: *ser más exhaustivo probando y copiando
el comportamiento real* — validar siempre contra el dato migrado.

## H-028 · Los datos del "diskette de quiniela" ya están en el backup (cajaliq/cajapagos)
**Fecha:** 2026-08-05 · **Módulo:** Caja / Juegos
**Evidencia:** el Aplicativo de Caja (22505) leía las liquidaciones de agencias desde
un diskette/pendrive (22005/22010, binario externo que no tenemos). Pero el backup
**ya contiene** `Caja/cajaliq.DBF` (liquidaciones, esquema real de 42 campos:
cod_agenci, moneda $/B, total_gral, pagado, no_recibo…) y `Caja/cajapagos.DBF`
(recibos de cobro de agencia: bonos/pesos, cobrado_*, vuelto_*, premios_*).
**Impacto:** se **desbloquea** la caja de quiniela sin el lector de diskette. Migrados
**60.000 liquidaciones + 31.714 recibos**. Se extendió `LiquidacionAgencia` (moneda,
cod_agencia, total_gral, intereses, iva, fecha_pago, cajero) y se creó
`CajaPagoAgencia`. El cobro (`cobrar_agencia`) reproduce Command1/Command2 de
`aplicaj`: cobrado por moneda, vuelto = adeudado − cobrado, premios, graba `cajapagos`
y marca las liquidaciones. **127 tests OK**. Cargar nuevas liquidaciones (no
históricas) requeriría un import manual/CSV en lugar del diskette.

## H-027 · Lectura de pantallas construidas vs fuente VFP — diferencias detectadas
**Fecha:** 2026-08-04 · **Módulo:** metodología / Caja / Créditos
**Evidencia:** al leer los `.scx/.sct` de las pantallas ya construidas (que se
hicieron **por inferencia del DBF antes de H-026**) aparecen diferencias reales,
registradas en [diferencias-pantallas.md](diferencias-pantallas.md):
- **Caja 🟠**: el "Aplicativo de Caja" (`frm225050000aplicativodeCaja`) real es de
  **agencias de quiniela** (bonos/pesos/vuelto), no de cuotas — **no existe** en la
  app. La cobranza de créditos en caja (`frm225150000cresegu1`, menú 22515) es una
  **cola por persona** (créditos + seguros + juegos extraordinarios) con búsqueda
  por nombre.
- **Caja 🔴→✅**: el cobro real aplica un **piso mínimo de interés** (`vl_minint`)
  que faltaba. **Corregido** en `domain/mora.py` (`minimo_interes`, default 0) con
  test `test_piso_minimo_interes_como_cresegu1`. Pendiente: alimentar mínimo/IVA
  desde la tabla de parámetros y revisar la base (¿incluye seguro/adm?).
- **Créditos 🟠**: "Solicitud" (32010, `frm320100000solcre`) real es una **grilla de
  administración** con estados, garante y vínculo a Nota, + asistente por tipo
  (AGAP/SADOP/productivos/gas); la app tiene un alta simple.
**Impacto:** hoja de ruta de fidelidad para las pantallas núcleo. La equivalencia
de mora sigue verde (863 casos reales + nuevo test). **125 tests OK**.

## H-026 · El código fuente VFP (.scx/.sct) está disponible y es legible
**Fecha:** 2026-08-04 · **Módulo:** metodología / Despacho
**Evidencia:** los formularios VFP viven en `CCyPP-Desarrollo/Formularios/*.scx`
(tabla DBF) + `*.sct` (memo con el código de los métodos). Se leen con el mismo
`DbfReader` apuntando el memo al `.sct`. Ejemplo: el form `120100000anexo_res_dis`
tiene 59 objetos; sus botones "Vista Previa / Confirmar / Imprimir Anexo" traen el
código real (PROCEDURE Click).
**Impacto (doble):**
1. **Metodología**: se puede **reconstruir el comportamiento exacto** de cada
   pantalla leyendo su fuente, en vez de inferirlo. A aplicar en las pantallas
   donde la fidelidad importa.
2. **Corrección (RESUELTA)**: el "Anexo de Resolución" real **no es un texto libre**
   (como se había construido) — es la **asignación de un lote de créditos/beneficiarios
   (solicitudes) a una resolución** por N° correlativo (`REPLACE lote`, marca
   `en_reso`), con impresión del reporte `rpt330851500anexo_disp_a` (listado de
   créditos aprobados con montos y total por lote). **Rehecho**: nuevo modelo
   `SolicitudCredito` (mapea `solicitud.dbf`), **78.443 solicitudes migradas**;
   servicio `solicitudes_para_anexo`/`asignar_anexo` con el mapeo tipo→rango de
   líneas del método `m_obtiene_datos` (AGAP 8050-8051, Microcréditos 6810-6813,
   Productivos 6800-6801, Vivienda 8130-8133, Gas cartera 11, Resto); endpoints
   `/anexo/tipos|solicitudes|asignar|excel`; pantalla `Anexos.tsx` con grilla +
   checkboxes + reimpresión por lote; test de regresión `test_anexo_resolucion_lote`.
   Verificado con dato real: AGAP devuelve 108 candidatas ($15,1M).
- **Expedientes**: la pantalla in-app estaba **vacía**; los expedientes reales son
  los **48.105 trámites tipo E\*** (Seguro Vida/Sepelio/Subsidio) de Mesa. Se
  repuntó Despacho→Expedientes a ese dato real con drill-down de pases.

## H-025 · Campos de texto de los DBF con bytes NUL (0x00) que PostgreSQL rechaza
**Fecha:** 2026-08-04 · **Módulo:** ETL / lector DBF
**Evidencia:** al cargar `titulares.dbf` (122k) el ETL cortó con
`psycopg.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes` — el
campo `DOMICILIO` de algunas filas venía relleno con `\x00`. PostgreSQL prohíbe
NUL en columnas `text`/`varchar` (SQLite no).
**Impacto:** el lector DBF (`app/etl/dbf.py`) ahora **elimina los `\x00`** al
decodificar campos carácter (C) y memos (M). Fix global: previene esta clase de
error en cualquier tabla. Lección: sanear encoding en el borde del ETL, no por
tabla.

## H-024 · El "módulo Notas" es Mesa de Entradas; hay 82k trámites + 428k pases reales
**Fecha:** 2026-08-04 · **Módulo:** Mesa de Entradas / Despacho
**Evidencia:** las pantallas que el inventario agrupaba en "Despacho/Notas" son en
realidad **Mesa de Entradas** (carga de trámite, pases, parte diario). El backup
`bases/Mesa` trae `tramites.dbf` (**82.218** notas/expedientes), `tipotram.dbf`
(**31 tipos**: N=Nota, E1=Seguro Vida, E4=Sepelio…) y `pases.dbf` (**428.051**
movimientos). Un trámite se identifica por tipo+letra+número+año; `I_D`=I marca
ingreso (69.191 ingresados).
**Impacto:** modelos `Tramite`/`TramiteTipo` + ETL; consultas e informe de
ingresados con dato real. **Nota de datos:** `pases.FECHA_PASE` tiene fechas
corruptas (año 1601) — el ETL de pases (pendiente) debe sanearlas como en H-017.

## H-023 · 6 créditos con `saldo_capital` negativo corrupto (miles de millones)
**Fecha:** 2026-08-04 · **Módulo:** Créditos / calidad de datos
**Evidencia:** al construir "Créditos por cartera" un subgrupo (Producir, +$6.900M)
superaba el total neto ($1.212M). Causa: **6 créditos de Vivienda (cartera 20)**
con `saldo_capital` negativo de miles de millones (el peor, crédito **180163 =
−$7.725.301.684**), provenientes de un `nsdonor` corrupto en `crcliact`. Ids:
180163, 174996, 179724, 182081, 181297, 181324.
**Impacto:** el reporte por cartera **clampa saldos negativos a 0** (`case`,
portable SQLite/PG) y expone `anomalias_saldo_negativo` con un aviso en pantalla;
el saldo bruto real de la cartera activa queda en ~$16.986M. **Acción de negocio
pendiente:** corregir esos 6 saldos en origen (o recomputarlos desde las cuotas).

## H-022 · Bug: el detalle de crédito daba 500 para créditos migrados
**Fecha:** 2026-08-04 · **Módulo:** Créditos (API) · Reportado por el usuario
**Evidencia:** al buscar el crédito 188512 en Cobranza "no aparecía nada". No
era falta de índices (la búsqueda es por PK): `GET /api/creditos/{id}` devolvía
**500** para cualquier crédito del ETL porque `CreditoOut.solicitud_id` era `int`
obligatorio y los 3.559 créditos migrados tienen `solicitud_id = None`
(no vienen de una solicitud). Además, 188512 (y ~423 créditos activos) **no tiene
cuotas** en `maecuotas`, por lo que el pendiente legítimamente es vacío.
**Impacto:** (1) `solicitud_id`/`linea_id` pasan a `int | None` en el schema
(test de regresión agregado); (2) la pantalla de Cobranza ahora muestra un aviso
claro que distingue "crédito inexistente" de "sin cuotas pendientes / sin plan
cargado", en vez de no mostrar nada. Pendiente de negocio: decidir de dónde salen
las cuotas de esos ~423 créditos activos sin plan en el backup.

## H-021 · `maecuotas` guarda los datos de pago (fecha/recibo/vía/cajero)
**Fecha:** 2026-08-04 · **Módulo:** Créditos / Caja
**Evidencia:** cada cuota de `maecuotas.dbf` trae `FECHA_PAGO`, `NRECIBO`,
`VIA_PAGO` (CAJA/TRAN/DBHA…) y `USUARIO_PA` (cajero). El ETL etapa 2 original no
los cargaba. De las 202.140 cuotas de créditos activos, **77.567 están pagadas**
(total cobrado histórico ≈ $6.392M).
**Impacto:** se agregaron 4 columnas a `Cuota` (`fecha_pago`, `nro_recibo`,
`via_pago`, `usuario_pago`) y se recargó la tabla desde la fuente. Habilita la
consulta "Pagos de créditos en caja" (`frm315550000pagcrecaja`) con fecha, vía y
cajero reales. Lección: la cuota es el libro de pagos del crédito; no hace falta
una tabla de recibos aparte para la trazabilidad histórica.
**Fecha:** 2026-08-04 · **Módulo:** Seguros
**Evidencia:** `segurosap.dbf` (32.356 filas, snapshot período **092002**) trae por
CUIL: `SEG_OBLIGA` (obligatorio), `SEG_SEPELI` (sepelio), `SEG_CONYUG` (cónyuge)
y `SEG_ADICIO` (**seguro de vida adicional**). 9.276 agentes tienen adicional > 0;
23.080 no.
**Impacto:** habilita los informes `infsegadicional` y
`informeagentessinseguroadicional` con dato real (modelo `SeguroAgente` + ETL).
Es un padrón por período: la fuente actual tiene un solo período cargado; la
pantalla filtra por período para cuando se incorporen más.

## H-019 · Los premios de juegos se guardan como débito (negativo)
**Fecha:** 2026-08-04 · **Módulo:** Juegos/Quiniela
**Evidencia:** en las 60.000 liquidaciones reales, `premios` viene **negativo**
(ej. Quiniela suma −2.347.390.657) porque representa la salida de caja pagada a
ganadores; `Mi Bingo`/`Quini6` tienen premios 0. El `total` de la liquidación
≈ recaudación − comisiones (los premios se saldan por otra vía).
**Impacto:** el "Resumen de ingresos por juego" normaliza a la magnitud
(`abs(premios)`) y calcula **neto = recaudación − |premios| − comisiones**
(Quiniela: 3.745M − 2.347M − 655M = **742M**). Lección: verificar el signo de los
importes del backup antes de agregar; no asumir que "premios" es un crédito.

## H-018 · El menú real es de 1 pantalla por opción; paginación obligatoria
**Fecha:** 2026-08-04 · **Módulo:** UI / arquitectura del frontend
**Evidencia:** el menú extraído de `symdeperf` (perfil ADMG, ver `menu-real.md`)
tiene 11 módulos → 46 submenús → **267 pantallas**, cada una con su propio
`DO FORM FORMULARIOS\...`. El análisis previo agrupaba varias pantallas en un solo
link (ej. "Organismos, compañías y parámetros" contenía Usuarios, Organismos,
Compañías, Parámetros y Auditoría), lo que el usuario marcó como "muy vago".
**Impacto:** se rehízo el `Sidebar` con 9 módulos y una opción de menú por
pantalla, y se dividieron las páginas monolíticas en componentes de una sola
función: `general/{Usuarios,Organismos,Companias,Parametros,Auditoria}`,
`creditos/{SituacionCliente,EstadisticasCartera,ListadoCreditos,CuotasMora,
PendientesCobro,EnviosPadron,Jubilados}`, `caja/{Cobranza,ControlCaja}`,
`contabilidad/{LibroDiario,IvaPeriodo,Cierre}`, `seguros/{Polizas,Regimenes,
Informes}`, `tesoreria/{OrdenesPago,Chequeras}`, `despacho/{Resoluciones,
Expedientes}`. Se agregó paginación + ordenamiento del lado del servidor
(`core/pagination.paginar`, schema genérico `Pagina[T]`) y un `DataTable`
reutilizable (orden por columna + "Anterior/Siguiente"). Lección: el menú del
sistema legado es la especificación funcional más fiel; hay que respetarlo
pantalla por pantalla, no agrupar por conveniencia.

## H-018b · El backend en Docker corría sin `--reload` (código viejo)
**Fecha:** 2026-08-04 · **Módulo:** Docker / operación
**Evidencia:** tras paginar `/api/clientes` (respuesta `{total,limit,offset,items}`),
el frontend rompía en `<Solicitudes>` porque `d.items` era `undefined`: el
contenedor `backend` seguía devolviendo un **array plano**. El servicio usa
`uvicorn app.main:app` (sin `--reload`) con `ENVIRONMENT: production`, así que
montar `./backend:/app` no basta: hay que **reiniciar el contenedor** para que
tome cambios de código (`docker compose restart backend`).
**Impacto:** procedimiento operativo — reiniciar backend tras cambios de API en
dev; a futuro, considerar un override de compose con `--reload` para desarrollo.

## H-017 · Fechas corruptas en los DBF (año 0) + no_benefic de 12 dígitos
**Fecha:** 2026-08-04 · **Módulo:** ETL / Jubilados
**Evidencia:** `jub_ctas` tiene fechas con año 0 (`ValueError: year 0 out of
range`); `sol_jubi.no_benefic` llega a 12 dígitos (170011567000).
**Impacto:** el lector DBF ahora tolera fechas/datetime corruptas (→ None) y
`CreditoJubilado.beneficiario_nro` es BigInteger. Lección recurrente (ver H-015):
enteros grandes + datos sucios son la norma en 20 años de datos.

## H-016 · En `usuarios.dbf` los campos login/nombre están cruzados
**Fecha:** 2026-08-04 · **Módulo:** ETL / Seguridad
**Evidencia:** el campo `nombre` contiene el login corto (ej. "nielsenc") y el
campo `usuario` el nombre completo ("NIELSEN CARLOS"). Además algunos nombres
completos exceden 30 chars.
**Impacto:** mapear login=`nombre`, nombre=`usuario`, con truncado defensivo.
Las **claves reales NO se migran** (seguridad): se asigna una temporal
(`cambiar123`) a los 188 usuarios y deben cambiarla. Lección: no confiar en el
nombre del campo; verificar el contenido real.

## H-015 · Códigos de organismo de 12 dígitos → BigInteger en Postgres
**Fecha:** 2026-08-04 · **Módulo:** ETL / General
**Evidencia:** `organismos.organo` tiene valores como 329020000001 (12 dígitos).
En SQLite (INTEGER 64-bit) entraban; en PostgreSQL (INTEGER 32-bit, máx ~2,1e9)
fallaba con `NumericValueOutOfRange`.
**Impacto:** `Organismo.id` y `Cliente.organismo_id` cambiados a **BigInteger**.
Lección: revisar rangos de enteros al migrar SQLite→PostgreSQL (los códigos de
negocio no son ids secuenciales).

## H-014 · El módulo Caja es mayormente Juegos/Quiniela
**Fecha:** 2026-08-04 · **Módulo:** Caja / Juegos
**Evidencia:** en `bases/Caja` las tablas más grandes son de lotería:
`cj_liqhis` (1,37M), `cajaliq` (222k), `cierrejuegos` (56k), `agenjuegos`,
`cjcontrol` — con `cod_juego`, `no_sorteo`, `no_agencia`, `premios`,
`com_agencia`. La cobranza de créditos es la parte menor: `cajacreseg` (5.629)
+ `cj_crsghis` (143k historia).
**Impacto:** el cajero cobra tanto créditos como recaudación de agencias de
quiniela. Juegos/Quiniela es un módulo grande y transversal (formularios 4xx +
buena parte de Caja). Priorizar su modelado (agencias, juegos, sorteos,
liquidación) como módulo propio.

## H-013 · La línea guarda la TNA actual; el crédito, su tasa de origen
**Fecha:** 2026-08-04 · **Módulo:** Créditos / motor
**Evidencia:** al recalcular créditos históricos con la TNA actual de la línea
(`lineacred.tna`) el motor daba 0% de coincidencia; con la tasa por cuota
(`maecuotas.nitna`) daba 96%. Las tasas cambian en el tiempo.
**Impacto:** para recalcular/reimprimir un crédito histórico se usa **su** tasa
(guardada en la cuota), no la vigente de la línea. Modelar `tasa` a nivel crédito
además de la línea. El motor es correcto; la fuente de la tasa importa.

## H-012 · Backup real completo — 9 módulos, 62,6M registros
**Fecha:** 2026-08-04 · **Evidencia:** `catalogo_real.md`.
**Impacto:** desbloquea ETL, validación a escala y los conceptos faltantes.
Cargados a `ccypp_real.db`: 78.055 clientes, 398 líneas, 3.686 organismos,
3.559 créditos activos, 202.140 cuotas, 1.057 beneficiarios de seguros.

## H-011 · Conceptos faltantes existen en `solicitud` (215 campos) — RESUELTO
**Fecha:** 2026-08-04 · **Módulo:** Créditos · **Estado:** ✅ resuelto
**Evidencia:** `solicitud` real tiene `ngori/nigori/nivaori` (gastos originación
+IVA), `quebranto/ntipoqueb/iquebranto/nivaqeb`, `gastos/igastos/nivaadm`,
`sellado/isellado/nivasel`, `no_credpp/importepp` (previo pago), `cft`, hasta
**4 garantes** (ga_/g2_/g3_/g4_), `indexado`, `ret_fogaca`, `disposicio`.
**Resolución:** `Solicitud` extendida con estos campos + `OrdenPago.iva`. Se
construyeron los 3 informes que estaban 🔷: `/contabilidad/iva-gsoq`,
`/contabilidad/iva-egresos`, `/creditos/consultas/previo-pago` (88 tests verdes).

## H-010 · `maecuotas` real confirma el motor al centavo
**Fecha:** 2026-08-04 · **Módulo:** Créditos / motor
**Evidencia:** sobre ~400k cuotas reales, regla IVA=21% del interés se cumple
396.921/396.922; reconstrucción francesa 96% al centavo (resto: Alemán/gracia/
indexado con su tasa de origen).
**Impacto:** motor financiero validado contra producción real.

## H-009 · Familia de pantallas 4xx = Juegos/Quiniela (no Contabilidad)
**Fecha:** 2026-08-03 · **Módulo:** clasificación de menús
**Evidencia:** títulos reales: agencias, maestro de juegos, jugadas, PRODE,
premios, valor llave, importa jugadas.
**Impacto:** módulo entero (32 pantallas) mal rotulado; reclasificado. Checkpoint
Fox del inventario corregido.

## H-008 · Menú: Tablas/Maestros es de 1er nivel; Líneas pertenece a Créditos
**Fecha:** 2026-08-03 · **Módulo:** navegación
**Impacto:** reorganización del menú lateral; verificación de pertenencia de
cada pantalla a su módulo.

## H-007 · 89% de las pantallas seguían pendientes (registro honesto)
**Fecha:** 2026-08-03 · **Evidencia:** `analisis-brechas.md` (337/377 pendientes).
**Impacto:** se pasó de "backbone construido" a plan iterativo módulo por módulo
con estados ✅/≈/🔷/⏳.

## H-006 · Familia 8xx = Tesorería/Egresos (no Juegos)
**Fecha:** 2026-08-03 · **Evidencia:** chequeras, OP, pagos de seguros, licitaciones.
**Impacto:** módulo Tesorería identificado; el sistema no tiene un "Juegos" en 8xx.

## H-005 · Mora: resarcitorios = 0 en producción; punitorio lineal en días
**Fecha:** 2026-08-03 · **Módulo:** Caja / mora
**Evidencia:** `ivacob.DBF` 29.084 cobranzas: resarcitorios 0/29.084; IVA
punitorio = 21% del punitorio 863/863; `int_pun/días` constante por crédito.
**Impacto:** motor de mora validado; `tasa_resarcitoria` default 0.

## H-004 · Sistema francés CCyPP: la anualidad incluye el IVA del interés
**Fecha:** 2026-08-03 · **Módulo:** motor de cuotas
**Evidencia:** en `tmpdev.DBF` la cuota constante es capital+interés+**IVA-int**;
tasa efectiva r = mensual × (1+IVA).
**Impacto:** corrección del motor francés (antes hacía constante capital+interés).

## H-003 · Tasa mensual = TNA × 30/365 (convención de tasa diaria)
**Fecha:** 2026-08-03 · **Módulo:** motor de cuotas
**Evidencia:** TNA/tasa = 12,1667 = 365/30 en todos los créditos.
**Impacto:** fórmula de tasa mensual del motor.

## H-002 · Credenciales expuestas (seguridad)
**Fecha:** 2026-08-03 · **Módulo:** integración API Catamarca
**Evidencia:** `ClientSecret` en texto plano en `login1.prg`/`set_class.prg`;
`Apis_Consultas_VFP/apis.dbf` con `CLIENT_SEC/TOKEN`.
**Impacto:** rotar credenciales; secretos por variable de entorno (ya aplicado en
el sistema nuevo). Acción independiente y urgente.

## H-001 · Datos sobre file-share; múltiples .exe por usuario/feature
**Fecha:** 2026-08-03 · **Módulo:** arquitectura VFP
**Impacto:** riesgo de integridad/concurrencia; consolidar la lógica en una única
línea de verdad (backend). Justifica la migración a PostgreSQL + API.
