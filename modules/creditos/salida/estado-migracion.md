# Estado de migración — CCyPP (documento vivo)
### Mapa de pantallas/funcionalidades VFP → sistema nuevo

> Se actualiza a medida que se migra. Alcance total (ver
> [inventario_funcional.md](inventario_funcional.md)): **377 formularios + 479 reportes**.
> Última actualización: **Despacho reconstruido desde el fuente VFP** — 53 pantallas,
> 124 tests, cobertura ~113/377 (30%). Se rehízo el **Anexo de Resolución (12010)**
> con la lógica real (asignación de lote de solicitudes; **78.443 solicitudes
> migradas** de `solicitud.dbf`) y los **Modelos de resoluciones** (338). Antes se
> completaron Mesa de Entradas (trámites + pases + oficinas), Tablas/Maestros
> (Perfiles, Oficinas, Proveedores), reportería PDF/Excel y el checkpoint del menú
> real. Ver [checkpoint-menu.md](checkpoint-menu.md) para la foto por módulo y
> H-018→H-028 en hallazgos. **Lectura completa de las 53 pantallas vs su fuente VFP**
> hecha (H-027): diferencias en [diferencias-pantallas.md](diferencias-pantallas.md).
> **Módulo Caja en ejecución** (leyendo el fuente de cada opción): hechos el **piso
> mínimo de interés**, la **Cola de caja por persona (22515)** y el **Aplicativo de
> caja de Quiniela (22505)** — cobro de agencias con bonos/pesos/vuelto/premios sobre
> **60.000 liquidaciones + 31.714 recibos reales** (H-028). Sumados **Control de caja
> con quiniela (22530)**, el **Informe de deuda de agencia (22555)** y el **Cierre de
> caja por moneda (22535)**, el **Informe de cobranzas en período (23065,
> créditos+quiniela)**, el **Informe de Ingresos Brutos (23035)** y la **Recaudación
> anual por origen/mes (23030)**, las **Liquidaciones cobradas por día (23050)** y el
> **Mensual de intereses e IVA (23015)** — este último con `cajacreseg` migrado
> (**5.629 cobros reales de créditos/seguros/extra**, H-030). Fix H-029: la cobranza
> de agencia no admite pago parcial. Sumadas la **Planilla contable de créditos/día
> (23045)**, el **Listado de pagos realizados (23025)** y el **Control de premios de
> quiniela (23020)** y el **Listado de cheques para agencias (23057)**. **139 tests**,
> Sumados el **Listado de compensaciones capital/interior (23055)** y la **Reimpresión
> de recibos (23010/23012)**, más la reimpresión de cierre (23040) y de control por
> cajero (23060). **Caja — reportes 230 completos (13/13) y procesos 225 núcleo
> completos** (cobro quiniela 22505, cola créditos/seguros 22515, anula 22525, control
> 22530, cierre 22535, deuda de agencia 22555). **Quedan por insumos externos** (🟠/⚪):
> los **egresos de pago a agencias** (22542/45/50, layout de transferencia bancaria),
> la **generación A.G.R.** (22560, formato externo) y los **lectores de diskette/
> pendrive** (22005/22010, binario externo; su dato ya está migrado). **143 tests**,
> 67 pantallas.
>
> **Créditos — revisión en curso**: inventario preciso (verificado contra el código):
> 305 ARCHIVOS y 315 CONSULTAS están **casi completos** (líneas ABM, requisitos,
> gasistas, cupos, situación, cartera, sin débito, pagos, turnos, envíos, jubilados). Se
> **enriqueció el ABM de Líneas (30510)** con plazo de gracia, paga interés en gracia,
> suma int.gracia a capital, admite previo pago y cta. contable. Construida la
> **Cancelación anticipada de crédito (32045)** — cuotas vencidas + mora, futuras sólo
> capital (condona interés no devengado); emite recibo y salda el crédito (verificado
> con crédito real 110573) y la **Baja de crédito (32565)** — anulación administrativa
> con motivo, rechaza créditos con pagos (verificado con crédito real 110142). Construido
> el **Recálculo de cuotas (32535)** leyendo el código exacto (H-031): modos *reprogramar
> vencimientos* (sólo fecha_vto, como el fuente activo) y *jubilatorio* (capital puro, 10%
> del haber), con vista previa obligatoria; **32537 no aplica** (mora en vivo). **32015
> Cancela cuotas** queda cubierto por Cobranza. Construida la **administración de turnos
> (32065/67/68)**: generación del mes distribuida por día hábil (con preview) + asignación
> al próximo libre / por N° excepcional (verificado: 100 turnos/21 días). **Créditos queda
> con core + ABMs + consultas + cancelación + baja + recálculo + turnos**; resta sólo
> reportes 330 (que solapan con consultas) y variantes de nicho.
>
> **Tesorería — revisión en curso**: resuelto el hallazgo **H-027** (verificado con dato
> real): la OP real (`maeop`) es un **cupo autorizado** (importe autorizado/usado/saldo,
> vigencia, hasta 10 resoluciones, habilitada/cancelada), no un pago directo. Nuevo modelo
> `AutorizacionOP` + ETL: **35.040 cupos migrados** (29.504 habilitados; autorizado
> $57.211M, saldo $20.227M), con listado paginado + totales + ABM. La pantalla de pagos
> anterior es el registro de **pagos** que consumen el cupo. **Circuito de consumo
> cerrado** (`820100`): el pago valida contra la OP (existe/habilitada/no vencida/sistema/
> saldo) y descuenta `usado`/`saldo` (invariante `saldo=importe−usado` verificado en
> 34.845/35.040 reales); consumo/reintegro reversibles (verificado con cupo real 3271).
> **153 tests**, 72 pantallas. Detalle en [diferencias-pantallas.md](diferencias-pantallas.md).
>
> **Verificación de comportamiento en la app (navegador)**: se recorrieron ~14 pantallas
> con dato real. Fixes hallados así (que los tests no detectaban): **401 transversal**
> (H-032, limpia sesión + login), **orden de Titulares** (H-033, los sin nombre al final)
> y **oficina por nombre** en Expedientes/Trámites (H-034). **Módulo Despacho cerrado**:
> Modelos (338), Resoluciones (estado real 11.337 B / 29.932 F; asunto placeholder desde
> modelos RTF), Anexo (solicitudes reales) y Expedientes (48.105, oficina con nombre)
> verificados en la app.
>
> **Contabilidad — dato real desbloqueado (H-035)**: el módulo estaba vacío (asientos sólo
> de operaciones de la app). El backup tiene el **libro mayor real**: `asientos.dbf` con
> **2.009.400 movimientos** → nuevo modelo `MovimientoContable` + ETL. Reportes reales:
> **balance de sumas y saldos** y **mayor por cuenta** con drill-down (PPS/DE: 940.697
> movimientos, saldo $64.886.460,56, contrastado con la DB). Pantalla `/contabilidad/mayor`.
> Además el **IVA de cuotas cobradas (61005/60505)** se reconstruyó sobre **dato real**
> (`maecuotas`): IVA débito por período (2025: $224.647.446,13, coincide con la DB) — el
> reporte anterior sobre asientos de la app daba $0. **155 tests**, 74 pantallas.

**Leyenda:** ✅ migrado · 🟡 parcial · ⏳ pendiente · 🔷 requiere datos reales/modelo

## Avance de cierre de brechas (iterativo)
| Iteración | Módulo | Construido | Tests |
|---|---|---|---|
| 1 | Seguros (informes) | cobrados, primas devengadas, pagos | 72 ✅ |
| 2 | Contabilidad | OP devengadas, revisión bajas, IVA egresos | 74 ✅ |
| 3 | Tesorería | chequeras, revisión pendientes/incompletos | 77 ✅ |
| 5a | Créditos (informes) | solicitudes activas, listado, saldos, mora | 80 ✅ |
| 5b | Créditos (config) | requisitos, gasistas, montos por período | 83 ✅ |

**Cobertura global:** 62/377 construido (16%) · 4 requiere datos reales · 309 pendiente.
Checkpoint Fox: familia 4xx re-clasificada como **Juegos/Quiniela** (estaba mal
rotulada Contabilidad/Egresos).

## 🎉 Backup real cargado (2026-08-04) — COMPLETO (9 módulos)
Se recibió el backup completo, **incluido Seguros** (9 módulos, **216 tablas,
62,6M registros**). Esquema real extraído a [catalogo_real.md](catalogo_real.md).
- **Seguros real**: `liqsegur` (10,1M liquidaciones), `seguros`/pólizas (216k),
  `titulares` (123k), `excombate` (excombatientes Malvinas), `subsidio`
  (protección familia), `l5182` (Renta Vitalicia).
- **ETL Seguros**: cargados **172 excombatientes + 885 beneficiarios de subsidio**
  reales a los regímenes especiales de `ccypp_real.db`.
- **ETL etapa 2 (créditos)**: cargados **3.559 créditos activos + 202.140 cuotas
  reales** (`crcliact` + `maecuotas`). La app corre sobre 96 líneas con cartera
  real. Modelo: `Credito.solicitud_id` nullable + `linea_id` denormalizado para
  soportar créditos históricos.
- **Hallazgo de modelado**: la **línea guarda la TNA actual**; cada **crédito
  lleva su tasa de origen** (`maecuotas.nitna`). Recalcular un crédito histórico
  usa su tasa, no la de la línea. El motor validó 96%/IVA 99,9997% usando `nitna`.
- **ETL Despacho**: cargadas **41.269 resoluciones/disposiciones reales**
  (`resoluciones.dbf`). Se agregó **soporte de memos (.FPT)** al lector DBF para
  dereferenciar campos de texto largo.
- **ETL Egresos**: cargadas **3.078 órdenes de pago reales** (agregadas por
  `no_op` desde `egresos.dbf`, con beneficiario y estado).
- **Módulo Juegos/Quiniela (nuevo)**: modelos Agencia y Liquidación; ETL cargó
  **140 agencias + 60.000 liquidaciones reales** (`agenjuegos`, `cajaliq`).
  Pantallas: agencias, liquidaciones (con cobro), resumen. UI + menú.
- **Cuenta corriente del crédito** (`ctacte`): modelo + consulta con saldo
  corrido; ETL cargó **7.088 movimientos** de los créditos activos.

## 🐳 Producción: stack completo en Docker + PostgreSQL (2026-08-04)
- `docker compose up`: **db (Postgres 16) + backend (FastAPI) + frontend (React)**.
- **ETL orquestado** (`app/etl/cargar_todo.py`) carga TODO el backup real a
  PostgreSQL desde `/bases` montado, y resetea secuencias.
- Datos en Postgres: **78.055 clientes, 202.140 cuotas, 41.269 resoluciones,
  60.000 liquidaciones, 3.559 créditos, 3.078 OP, 1.057 benef. seguros**.
- Backend en modo `production` (sin datos demo). Instrucciones en el README.

## 🧭 Refactor de menú granular + paginación (2026-08-04)
Corrección solicitada por el usuario: cada opción del menú debe ser **una sola
pantalla/función**, chequeada contra el menú real del sistema (`menu-real.md`),
no agrupada. Ver [H-018](hallazgos.md).
- **Sidebar rehecho**: 9 módulos (Créditos, Caja, Tesorería, Contabilidad,
  Seguros, Despacho, Juegos, Mesa, General) con **una opción por pantalla**.
- **Páginas divididas** (de monolíticas a 1 función c/u):
  `general/{Usuarios,Organismos,Companias,Parametros,Auditoria}` ·
  `creditos/{SituacionCliente,EstadisticasCartera,ListadoCreditos,CuotasMora,
  PendientesCobro,EnviosPadron,Jubilados}` · `caja/{Cobranza,ControlCaja}` ·
  `contabilidad/{LibroDiario,IvaPeriodo,Cierre}` · `seguros/{Polizas,Regimenes,
  Informes}` · `tesoreria/{OrdenesPago,Chequeras}` ·
  `despacho/{Resoluciones,Expedientes}`. Se borraron las 7 páginas viejas
  agrupadas (Caja, Consultas, Contabilidad, Despacho, Seguros, Tesoreria, Maestros).
- **Paginación + orden del lado del servidor**: `core/pagination.paginar()` +
  schema genérico `Pagina[T]` (`{total,limit,offset,items}`). Aplicado a las
  listas grandes: `/api/clientes` (78.055), `/api/despacho/resoluciones` (41.269,
  orden por fecha/número/tipo/asunto), `/api/juegos/liquidaciones` (60.000) y
  `/api/admin/auditoria` (50.011). Todas 25/pág con "Anterior/Siguiente".
- **DataTable** reutilizable (orden por columna asc/desc, "Anterior/Siguiente",
  "desde–hasta de total") — base para paginar el resto de las listas grandes.
- **Verificación**: `tsc -b` OK, `vite build` OK (65 módulos), **100 tests OK**,
  y validación en vivo en Docker (login admin, menú granular, Clientes paginado
  con orden por "Apellido y nombre ▲").

## 📊 Cierre de brechas — informes con dato real (2026-08-04)
Continuación hacia el 100% con pantallas nuevas respaldadas por datos reales
(cada una con test + hallazgo si corresponde). Cobertura: **100/377 (27%)**.
- **Juegos → Ingresos por juego** (`/juegos/ingresos`): recaudación/premios/
  comisiones/neto agrupado por juego sobre 60.000 liquidaciones reales (Quiniela
  neto **$742M**). Cubre `resrec` + `inf_ingresos_jueg`. Hallazgo **H-019**: los
  premios se guardan como débito (negativo) → se normaliza con `abs()`.
- **Tesorería → Reporte de OP** (`/tesoreria/reporte`): OP por tipo con desglose
  P/G/A sobre 3.078 OP reales (CREDITO $19,2B, PROVEEDOR $12B, total $31,25B).
  Cubre `rptoprb` + `rptop`.
- **Paginación extendida**: `/egresos/ordenes` (3.078) ahora paginado con
  `Pagina[T]`; el listado de OP usa DataTable.
- **Verificación**: `tsc -b` OK, `vite build` OK, **102 tests OK**, validado en
  vivo contra PostgreSQL en Docker.
- **Juegos → Maestro de juegos** (`/juegos/maestro`): modelo `Juego` + ETL de
  `maejuegos.dbf` (carpeta Juegos) → **47 juegos/modalidades reales** con comisión
  de agencia/subagencia y código AFIP (Quiniela 17,5%/12,5%, Quini6 20%/2,5%,
  Loto 15%/2,5%…). Cubre `frm405100000maejuegos`.
- **Juegos → Control de sorteos** (`/juegos/sorteos`): modelo `Sorteo` + ETL de
  `maejugadas.dbf` → **3.143 sorteos reales** (juego, N° sorteo, fecha,
  vencimiento, si se importó a caja), paginado + orden + filtro por juego,
  resolviendo el nombre desde el maestro. Cubre `maejugadas` (2 variantes).
  **104 tests OK**. Cobertura **103/377 (27%)**.
- **Créditos → Listado paginado + búsqueda** (`/creditos/consultas/creditos`):
  el endpoint dejaba de devolver los 3.559 créditos de una; ahora es paginado
  (25/pág), ordenable por columna (crédito/cliente/capital/saldo) y con búsqueda
  por cliente/CUIL. `total_capital`/`total_saldo` se calculan sobre el set
  filtrado completo. Mejora 5.1 del plan (no cuenta como pantalla nueva). Nota:
  el "historial de créditos por cliente" (`frmbus_creditos`) ya está cubierto por
  **Situación del cliente**, que lista los créditos del agente; no se duplica.
- **Seguros → Seguro de vida adicional** (`/seguros/adicional`): modelo
  `SeguroAgente` + ETL de `segurosap.dbf` → **32.356 agentes** con desglose por
  cobertura (obligatorio/sepelio/cónyuge/adicional). Resumen (9.276 con adicional,
  23.080 sin) + tabla paginada con/sin adicional y búsqueda. Cubre
  `frm730250000infsegadicional` + `frm730150000informeagentessinseguroadicional`.
  Ver H-020. **105 tests OK**. Cobertura **105/377 (28%)**.
- **Créditos → Sin débito automático** (`/creditos/sin-debito`): créditos activos
  cuyo cliente no tiene CBU (no entran al padrón de débito, requieren cobro
  manual). Paginado + búsqueda. Sobre dato real: **224 créditos, saldo $254,5M**.
  Cubre `frm315450500solsindeb`. **106 tests OK**. Cobertura **106/377 (28%)**.
- **Créditos → Pagos en caja** (`/creditos/pagos-caja`): se **enriqueció el modelo
  `Cuota`** con los datos de pago reales de `maecuotas` (fecha_pago, nro_recibo,
  via_pago, cajero) y se recargó la tabla (202.140 cuotas, **77.567 pagadas,
  $6.392M cobrados**). Consulta paginada por fecha/crédito con recibo, vía y
  cajero. Cubre `frm315550000pagcrecaja`. Ver H-021. **107 tests OK**. Cobertura
  **107/377 (28%)**.
- **Créditos → Créditos por cartera** (`/creditos/por-cartera`): resumen por
  cartera (activos/cancelados, capital, saldo) usando `CARTERA_NOMBRE`. Cubre la
  opción de menú 31537. Al construirlo salió **H-023**: 6 créditos de Vivienda con
  `saldo_capital` negativo corrupto (uno de −$7.725M) descuadraban los totales; el
  reporte clampa negativos a 0 y avisa las anomalías. **109 tests OK**.
- **Créditos → Turnos otorgados** (`/creditos/turnos`): modelo `TurnoCredito` +
  ETL de `turnos.dbf` → **38.548 turnos reales** de solicitud de crédito (tipo
  TODO/AGAP, período, solicitante, línea, usado/autorizado). Consulta paginada con
  filtros (tipo, usado) y búsqueda. Da respaldo real a las consultas de turnos
  (`frm315600000/315620000consturno`, menú 31560). **110 tests OK**. Cobertura
  **107/377 (28%)** (las consultas ya estaban contadas; ahora con dato real).
- **Reportería (mejora 5.5) → Listado de créditos a Excel**: `GET
  /creditos/consultas/creditos/excel` exporta el **set filtrado completo** (no la
  página) a `.xlsx` con openpyxl (verificado: 3.562 filas para los 3.559 activos +
  totales). Botón "Descargar Excel" en la pantalla de listado. Se agregó el
  parámetro `cap` a `listado_creditos` para no aplicar el tope de paginación en el
  export. **111 tests OK**.
- **Reportería → Pagos en caja a Excel**: `GET /creditos/consultas/pagos-caja/excel`
  exporta los pagos filtrados (77.567 en total). **Optimización de performance**:
  el export completo tardaba 52s → se bajó a **~9s** combinando (1) openpyxl en
  modo *write-only* y (2) `select` de columnas puntuales en vez de objetos ORM
  completos (la consulta paginada también se benefició). Botón "Descargar Excel"
  con los filtros de fecha/crédito activos.
- **Reportería → Turnos otorgados a Excel**: `GET /creditos/consultas/turnos/excel`
  exporta los turnos filtrados (38.548). Aplica el patrón de exports grandes desde
  el arranque (write-only + `select` de columnas): export completo en **~6s**.
  Botón "Excel" en la pantalla de turnos.
- **Reportería → Créditos por cartera a PDF**: `GET /creditos/consultas/por-cartera/pdf`
  genera un **resumen ejecutivo** (1 carilla, reportlab) con la tabla por cartera,
  totales y la nota de anomalías H-023 en el subtítulo. Reusa el helper genérico
  `tabla_pdf`. Botón "Descargar PDF" en la pantalla. Total activos 3.559, saldo
  bruto $16.986M.

## 🗂️ Mesa de Entradas / Trámites — dato real (2026-08-04)
- **Modelos** `Tramite` + `TramiteTipo` + ETL (`cargar_tramites`) desde
  `Mesa/tramites.dbf` y `tipotram.dbf` → **82.218 trámites reales** (notas y
  expedientes) + **31 tipos** (NOTA, Expte. Seguro Vida, Sepelio, Subsidio…).
- **Consulta de trámites** (`/mesa/tramites`): paginada, con filtros por tipo y
  estado y búsqueda por iniciador/asegurado/referencia. Da respaldo real a las
  consultas de trámites (515050/515100/520100003, ya ✅ pero vacías).
- **Trámites ingresados** (`/mesa/ingresados`): informe de ingresos por tipo
  (69.191 ingresos; NOTA 29.533, Seguro de vida 12.762…). Cubre `tramitesdiarios`
  (530050) + `imprimeparte` (parte diario). **113 tests OK**. Cobertura
  **109/377 (29%)**.
- **Historial de pases** (`pases.dbf`): modelo `TramitePase` + ETL → **428.051
  pases reales** (fechas año 1601 saneadas a None). Drill-down "ver pases" en la
  Consulta de trámites: recorrido de oficinas (origen→destino), fecha, proveído y
  activo. Cubre `pasesexptes` (52010/520100000). Validado: trámite E1 R-967/2012
  con 37 pases. **115 tests OK**. Cobertura **110/377 (29%)**.
- **Maestro de Oficinas** (`/general/oficinas`): modelo `Oficina` + ETL de
  `General/oficinas.dbf` → **151 dependencias reales** (Directorio, Gerencias,
  Mesa de Entradas, Tesorería…). Además **enriquece los pases**: ahora muestran
  el **nombre** de la oficina (origen→destino) en vez del número. Cubre
  `admofi` (X0545). **116 tests OK**. App: **45 pantallas**.
- **Maestro de Perfiles** (`/general/perfiles`): modelo `Perfil` + ETL de
  `maeperfil.dbf` → **19 perfiles reales** del sistema legado (ADMG, CAJA, CR01,
  JU01…) como catálogo de solo lectura (no toca el RBAC nuevo en
  `core.security.PERFILES`). Endpoint `/admin/perfiles-maestro`. Cubre X0510/X1005.
  **117 tests OK**. App: **46 pantallas**.
- **ABM de Proveedores** (`/general/proveedores`): modelo `Proveedor` + ETL de
  `proveedores.dbf` (1 real: LA DIFERENCIA SANDWICHERIA) + alta de nuevos con
  razón social, CUIT, tipo IVA, contacto/domicilio. Búsqueda por razón social/CUIT.
  Beneficiario de OP de Tesorería (licitaciones/compras). Cubre `admprov` (90510).
  Cierra el módulo **Administración y Finanzas**. **118 tests OK**. App: **47
  pantallas**.

## 🔎 Revisión honesta del menú real + Titulares de seguro (2026-08-04)
Tras revisar `menu-real.md` en detalle se documentó que **faltan muchas ventanas
operativas** (Créditos 330 reportes, Caja 230, Tesorería 830, operatoria de
Seguros): ver el desglose por módulo y categorías en
[faltantes-menu.md](faltantes-menu.md). Se retomó el cierre de huecos con dato real:
- **Seguros → Titulares de seguro** (`/seguros/titulares`): modelo `TitularSeguro`
  + ETL de `titulares.dbf` → **122.784 titulares reales** del seguro de vida
  colectivo, paginado + búsqueda por apellido/CUIL. **Hallazgo H-025**: campos de
  texto con bytes NUL (0x00) que Postgres rechaza → el lector DBF ahora los
  elimina (fix global). **119 tests OK**. App: **48 pantallas**.
- **Créditos → Informe de créditos (generador)** (`/creditos/informe`): una sola
  pantalla con **filtros combinables** (estado, línea, cartera, organismo, fechas
  de otorgamiento, con/sin saldo, búsqueda) + orden por columna + **Excel**.
  Reemplaza a decenas de reportes del submenú 330/33085 (estado, saldos,
  vigentes/cancelados, por línea/cartera/organismo/depto). Verificado: activos con
  saldo 2.169, cartera Producir 551. **120 tests OK**. App: **49 pantallas**. Es la
  mejora "generador de informes" del plan (5.x) — evita hacer 50 pantallas casi
  iguales.
- **Tesorería → Informe de OP (generador)** (`/tesoreria/informe`): mismo enfoque
  para el submenú 830 — filtros combinables (estado, tipo, beneficiario/CUIT,
  fechas) + orden + **Excel**. Cubre `8301505/8301510`. Verificado: tipo PROVEEDOR
  1.438 OP. **121 tests OK**. App: **50 pantallas**.
- **Despacho → Modelos de resoluciones** (`/despacho/modelos`): modelo
  `ModeloResolucion` + ETL de `rtf.dbf` → **338 modelos/plantillas reales** de
  resolución/disposición (Ayudas sociales, Acta volante, Actualiza deuda…), con
  búsqueda. Cubre 10505 (105 Archivos). Con esto Despacho queda casi completo
  (faltan anexo 12010 y el editor de modelos). **122 tests OK**. App: **51 pantallas**.
- **Despacho → Anexo de resolución REHECHO** (`/despacho/anexos`, H-026): reemplaza
  el `AnexoResolucion` de texto libre (incorrecto) por la lógica real del fuente VFP
  `120100000anexo_res_dis`. Nuevo modelo `SolicitudCredito` (`solicitud.dbf`,
  **78.443 migradas**); se elige un **tipo** (AGAP/Microcréditos/Productivos/
  Vivienda/Gas/Resto → rango de líneas del método `m_obtiene_datos`), se listan las
  solicitudes **aprobadas sin resolución** (estado A, cubica C/DC, `no_resol`=0) y
  se **asigna un lote** (N° correlativo + fecha → `en_reso`/`no_resol`/`fecha_resol`),
  con reimpresión por lote y **Excel** del anexo. Endpoints `/anexo/tipos|solicitudes
  |asignar|excel`; test `test_anexo_resolucion_lote`. Verificado con dato real
  (AGAP: 108 candidatas, $15,1M). Cubre 12010. **124 tests OK**. App: **53 pantallas**.
- **Despacho → Expedientes con dato real** + **H-026**: se detectó que la pantalla
  de Expedientes usaba un flujo in-app **vacío**; los expedientes reales son los
  **48.105 trámites tipo E\*** de Mesa. Se repuntó `/despacho/expedientes` a ese
  dato (filtro `solo_expedientes`) con drill-down de pases. Además se comprobó que
  el **fuente VFP (.scx/.sct) es legible** → permite reconstruir el comportamiento
  exacto; reveló que el **Anexo de Resolución** real es asignación de un *lote* de
  créditos a una resolución (no texto libre) — **ya rehecho** (ver bullet anterior).
  **124 tests OK**.

## 📒 Contabilidad → Balance de sumas y saldos (mejora, 2026-08-04)
- **Reporte contable estándar que el CCyPP legado no tenía** (su menú de
  Contabilidad solo trae IVA + asientos + deuda). Se construye sobre los asientos
  que el sistema genera automáticamente (otorgamiento/cobranza).
- Por cuenta: total debe, total haber y saldo deudor/acreedor, con **totales que
  deben cuadrar** (sumas iguales y saldos iguales → indicador "Cuadra ✓").
  Filtro por fecha. Pantalla `/contabilidad/balance` + **PDF** (reusa `tabla_pdf`).
- En producción está vacío hasta que se registren operaciones (comportamiento
  correcto); el test lo valida generando un asiento de otorgamiento (cuadra).
  **114 tests OK**. Es una **mejora** (5.x), no suma al conteo de pantallas VFP.

## 💳 Créditos → Cuenta corriente por crédito (2026-08-04)
- **Pantalla** `/creditos/cuenta-corriente` sobre el endpoint ya existente:
  movimientos (débitos/créditos) de un crédito con **saldo corrido**, mostrando
  capital/interés/IVA/punitorio/recibo. Sobre **7.088 movimientos reales** (3.000
  créditos, tabla `ctacte`). Validado en vivo (crédito 123211, 106 movimientos).
  Prioridad 1 del checkpoint. La app llega a **43 pantallas**.
- **H-015 resuelto**: códigos de organismo de 12 dígitos → BigInteger
  (`with_variant` Integer en SQLite para el modo desarrollo).

## Iteración Utilidades/Despacho (2026-08-04)
- **ABM de Usuarios**: alta, cambio de clave, baja, listado + catálogo de
  perfiles. ETL cargó **188 usuarios reales** (H-016: campos login/nombre
  cruzados; claves reales no se migran, temporal `cambiar123`).
- **Despacho**: expedientes/trámites por oficina; historial y pendientes
  cubiertos por los pases.
- **Auditoría**: modelo `EventoAuditoria` + registro en vivo (login) + consulta
  con filtros. ETL cargó **50.000 eventos reales** (muestra de los 6,5M). La
  auditoría combina histórico real + eventos nuevos del sistema.
- **Jubilados / Ley 5094**: modelos + consultas (listado, cuotas, resumen, por
  departamento). ETL cargó **2.210 solicitudes + 11.873 cuotas reales**. UI en
  Consultas. H-017: fechas corruptas toleradas, no_benefic BigInteger.
- Cobertura: **96/377 (25%)**.
- **Modelo extendido (H-011 resuelto)**: `Solicitud` con gastos originación,
  quebranto, sellado, CFT, 4º garante, previo pago; `OrdenPago` con IVA.
  Desbloqueados los 3 informes que estaban 🔷.
- **H-014**: el módulo Caja es mayormente **Juegos/Quiniela** (ver hallazgos).
- **ETL etapa 1 (maestros)**: cargados **3.686 organismos, 398 líneas, 78.055
  clientes reales** a `ccypp_real.db`. La app corre sobre datos reales.
- **Validación del motor a escala**: sobre ~400k cuotas reales (`maecuotas`),
  la regla IVA=21% del interés se cumple **396.921/396.922**; reconstrucción
  francesa al centavo en el 96% (el resto son líneas Alemán/gracia/indexado que
  requieren aplicar el `tipo_calculo` real por línea — etapa 2).
- Los conceptos que estaban 🔷 (gastos originación, quebranto, previo pago, cft)
  **existen en el `solicitud` real (215 campos)** → desbloqueados para etapa 2.

---

## Resumen por módulo

| Módulo | Pantallas VFP | Estado |
|---|---:|---|
| Sistema / Login | 2 | ✅ |
| Créditos | 145 | 🟡 núcleo + consultas + ABM |
| Caja | 17 (+14 listados) | 🟡 núcleo + cierre |
| Contabilidad (+Egresos) | 43 | 🟡 asientos + libro diario |
| Tesorería / Egresos | 32 | 🟡 órdenes de pago |
| Seguros | 18 | 🟡 pólizas + liquidación + regímenes especiales |
| Despacho (Resol.+Notas) | 18 | 🟡 resoluciones + expedientes |
| Utilidades / Tablas | 28 | 🟡 ABMs núcleo |
| Mesa de entradas | 3 | ✅ turnos + tablero |
| Reportería | 479 `.frx` | 🟡 recibo, libro diario, cierre, padrón |

---

## Detalle: pantallas migradas

### Sistema / Login
| VFP | Nuevo | Estado |
|---|---|---|
| `login` | `POST /api/auth/login` (JWT + RBAC por perfil) | ✅ |

### Créditos
| VFP | Nuevo | Estado |
|---|---|---|
| F11 – Simulación de crédito | Simulador (`POST /creditos/simular`) | ✅ validado c/datos reales |
| `frm320100000solcre` — Administración de Créditos | Solicitudes + otorgamiento | ✅ |
| `calcpres` / `det_cuota` (motor) | `domain/cuotas.py` | ✅ al centavo |
| `recalculo` (mora) | `domain/mora.py` | ✅ validado c/`ivacob` |
| `frm320050001pagacred` — Cobranza de créditos | Caja / cobranza | ✅ |
| `frm315650000hiscre` — Situación de un cliente | `consultas/cliente/{id}/situacion` | ✅ |
| `frm315400000sitmar` — Situación de margen | (incluido en situación) | ✅ |
| `frm315350000estadvar` — Estadísticas | `consultas/estadisticas` | ✅ |
| `lst32carteras` / cartera por línea | `consultas/estadisticas/pdf` (informe cartera) | ✅ |
| `frm315300000consenvios` — Envíos de cuotas | `consultas/envios` (+Excel padrón) | ✅ |
| `frm305050000lineas` — Administración de Líneas | ABM de líneas (`/admin/lineas`) | ✅ |
| `frm315050000consoli` / `consulta_solicitudes` | Listado de solicitudes | ✅ |
| `frm305150000requisitos` — Requisitos | — | ⏳ |
| `frm315150000consjub` — Consulta jubilados | — | ⏳ |
| `frm315600000consturno` — Turnos | — | ⏳ |

### Caja
| VFP | Nuevo | Estado |
|---|---|---|
| `frm225050000aplicativodeCaja` — Aplicativo de Caja | Cobranza de cuotas | ✅ |
| `frm225150001pagcsj` — Cobranzas | Cobranza + recibo | ✅ |
| `frm225350000cierrec` — Cierre de Caja | Cierre de caja (+PDF) | ✅ |
| `frm230050000rptpend` — Pendientes/Ingresos | `/caja/pendientes-cobro` (+PDF, con mora) | ✅ |
| `frm225250000anupago` — Anula pagos | — | ⏳ |
| `frm225300000ctrlcaj` — Control de caja | `/caja/control` (detallado por cajero, +PDF) | ✅ |
| `rpt225050000recibo` — Recibo | Recibo PDF | ✅ |
| `frm230100000rptreci` — Reimpresión de recibos | `GET /caja/recibos/{id}/pdf` | ✅ |

### Contabilidad
| VFP | Nuevo | Estado |
|---|---|---|
| `cb-crasientootorga` — Asiento de otorgamiento | Asiento automático | ✅ |
| `cb-crasientodevenga` — Asiento de devengamiento | (cobranza) | 🟡 |
| Libro diario | `/contabilidad/libro-diario` (+PDF) | ✅ |
| `cb-iva-a-pagar-periodo` — IVA a pagar por período | `/contabilidad/iva-periodo` (+PDF) | ✅ |
| `cb-op-dev-periodo` — OP devengadas por período | `/contabilidad/op-devengadas` | ✅ |
| `cb-crevicredborra` — Revisión solicitudes baja | `/contabilidad/solicitudes-baja` | ✅ |
| `cb-egreviegresos` — Revisa transacciones egresos | `/egresos/ordenes` (revisión) | ✅ |
| `cb-egivaegresos` — IVA de egresos | `/contabilidad/iva-egresos` | ✅ (modelo extendido) |
| `cb-iva-gsoq-periodo` — IVA gs.orig/quebranto | `/contabilidad/iva-gsoq` | ✅ (modelo extendido) |
| `cb-prepag-linea` — Previo pago | `/creditos/consultas/previo-pago` | ✅ (modelo extendido) |

### Tesorería / Egresos
| VFP | Nuevo | Estado |
|---|---|---|
| `frm805100000altaop` — Maestro de OP | Órdenes de pago (`/egresos/ordenes`) | ✅ |
| `frm820150000cargachetra` — Paga transacciones | `POST /egresos/ordenes/{id}/pagar` | ✅ |
| `frm805050000altachequeras` — Chequeras | (cheque en la OP) | 🟡 |
| `frm820100000recibos` — Licitaciones y compras | OP tipo PROVEEDOR | ✅ |

### Seguros
| VFP | Nuevo | Estado |
|---|---|---|
| `frm720100000altatitular` — Alta de titulares | Pólizas | 🟡 |
| `frm730100000…primas` — Liquidación de primas | `/seguros/liquidacion` | ✅ |
| `frm720050000cobrasegu` — Cobro de seguros | (seguro en la cuota) | ✅ |
| `frm730050000rptcobseg` — Seguros cobrados de un día | `/seguros/cobrados` | ✅ |
| `frm715100000cons_primas` — Primas devengadas | `/seguros/primas-devengadas` | ✅ |
| `frm720150000pagosseguros` — Pagos de seguros | `/seguros/pagos` (OP tipo SEGURO) | ✅ |
| `frm705050000maetit` — Renta Vitalicia Malvinas | Regímenes especiales (beneficiarios + generación de cuotas) | ✅ |
| `frm720200000excombatientes` — Excombatientes | Régimen especial (`/seguros/regimenes`) | ✅ |
| `frm725150000cuotasdesubsidio` — Subsidio familia | Régimen especial + O.P. automática | ✅ |
| Generar Cuotas Tesorería | `POST /seguros/regimenes/{id}/generar-cuotas` → OP | ✅ |

### Despacho
| VFP | Nuevo | Estado |
|---|---|---|
| `120050000reso_disp` — Resoluciones/Disposiciones | `/despacho/resoluciones` (alta+firma) | ✅ |
| `105050000modelos` — Generación Word de resoluciones | `/despacho/resoluciones/{id}/word` (.docx) | ✅ |
| `frm14enexo_res` / `_dis` — Anexos | — | ⏳ (documento base ya generable) |
| `520100000pasegral` — Pases | Expedientes + pases | ✅ |
| `520100003paseinicial` — Pase inicial | (pase inicial automático) | ✅ |

### Utilidades / Tablas
| VFP | Nuevo | Estado |
|---|---|---|
| `frm305050000lineas` — ABM Líneas | `/admin/lineas` (CRUD) | ✅ |
| `frm315250000organismos` — Organismos | `/admin/organismos` | ✅ |
| Parámetros generales (`paramgral`) | `/admin/parametros` | ✅ |
| Compañías de seguros | `/admin/companias` | ✅ |

### Mesa de entradas
| VFP | Nuevo | Estado |
|---|---|---|
| `frm315600000consturno` — Consulta de turnos | `/mesa/turnos` + tablero | ✅ |
| `frm315620000consturno` — Turnos entregados | Generación de turnos (`/mesa/turnos`) | ✅ |
| Cola / llamado / atención | `/mesa/llamar`, `/mesa/turnos/{id}/atender` | ✅ |
| Trámites / recepción | (deriva a Expedientes de Despacho) | 🟡 |

---

## Cobertura de reportes (479 `.frx`)
✅ Recibo de cobranza · Libro diario · Cierre de caja · Padrón de débito (Excel) ·
IVA a pagar por período · Pendientes de cobro (con mora) · **Control de caja
detallado** · **Cartera de créditos por línea**.
⏳ Pendientes priorizados: resúmenes de agencias (quiniela), informes de seguros
por organismo, anexos de resoluciones (Word).
