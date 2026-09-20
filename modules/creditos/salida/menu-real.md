# Menú REAL del sistema CCyPP (perfil ADMG)

> Extraído de `symdeperf` (menú data-driven del VFP). Jerarquía: Módulo → Submenú → Pantalla.
>
> **Estado en el sistema nuevo:** ✅ construido (se anota `[Pantalla nueva]`) ·
> las no marcadas siguen pendientes. El detalle de faltantes por módulo (con
> categorías 🟢/🟠/🔵/⚪) está en [faltantes-menu.md](faltantes-menu.md); el estado
> consolidado en [checkpoint-menu.md](checkpoint-menu.md).

## Cobertura real por módulo (auditoría 2026-08-05)

El conteo de opciones ✅ **individuales** subestima la cobertura porque muchas opciones
se resuelven con **generadores** (una pantalla parametrizable cubre decenas de reportes),
**pantallas consolidadas** (una cubre varias opciones) o son **variantes** del mismo
proceso. Cobertura *funcional* (núcleo operativo del módulo):

| Módulo | Núcleo operativo | Cobertura funcional | Qué falta (genuino) |
|---|---|---|---|
| 1 Despacho | ✅ completo | ~100% | editor de modelos RTF |
| 2 Caja | ✅ completo | ~90% | pagos a agencias (egresos), AGR |
| 6 Contabilidad | ✅ mayor real + IVA real | ~90% | motor de devengamiento |
| 5 Mesa | ✅ completo | ~90% | reportes de nicho |
| 3 Créditos | ✅ core+ABMs+cancel/baja/recálculo/turnos | ~40% opciones / núcleo completo | liquidación por variantes, subsidios, reportes 330 |
| 4 Juegos | ✅ maestro/sorteos/agencias/ingresos/aplicativo/**fondo gtía(hist.273k)** | revisado (H-037) | reportes 430 restantes, import/export (layouts externos) |
| 7 Seguros | ✅ titulares(122k)/**pólizas vida x agente(207k)**/regímenes/adicional | revisado en la app (H-036) | cobro por caja, pagos, control previsional |
| 8 Tesorería | ✅ cupos+chequeras+consumo+cheques(73k)+**egresos ledger(340k)** | revisado (H-038/H-040) | OP por resolución, reimpresiones, archivos banco |
| 9 Adm. y Finanzas | ✅ proveedores | pendiente de revisar | licitaciones/compras |
| X General | ✅ usuarios/perfiles/organismos/compañías/parámetros/auditoría/oficinas | ~completo | — |

**Leyenda de cobertura por línea:** ✅ construido individual · ≈ cubierto por generador /
pantalla consolidada · 🟠 bloqueado por insumo externo · ⚪ variante/nicho pendiente.
**Ningún módulo está vacío**: los núcleos operativos (movimientos de dinero, cobros,
pagos, cupos, mayor real, IVA real) están migrados. Pendiente: revisar en la app
Juegos, Seguros, Adm.y Finanzas y General con la metodología de recorrido.

## Pantallas construidas en la app nueva (52, en el orden del menú real)

El **Sidebar de la app respeta este orden y la estructura de dos niveles**
(Módulo → Submenú Archivos/Datos/Consultas/Procesos/Reportes → Pantalla), igual
que el menú real:

| # | Módulo | Pantallas construidas |
|---|---|---|
| 1 | **Despacho** | Modelos de resoluciones · Resoluciones y disposiciones · **Anexo de resolución** · Expedientes y pases |
| 2 | **Caja** | Cobranza · Control de caja |
| 3 | **Créditos** | Líneas · Solicitudes · Simulador · Jubilados/5094 · Situación del cliente · Cuenta corriente · Estadísticas · Por cartera · Turnos otorgados · Sin débito · Pagos en caja · Envíos/padrón · **Informe de créditos (generador)** · Listado · Cuotas en mora · Pendientes de cobro |
| 4 | **Juegos** | Maestro de juegos · Control de sorteos · Agencias y liquidaciones · Ingresos por juego |
| 5 | **Mesa de Entradas** | Turnos · Consulta de trámites · Trámites ingresados (+ pases) |
| 6 | **Contabilidad** | Libro diario · Balance de sumas y saldos · IVA por período · Cierre de caja |
| 7 | **Seguros** | Titulares de seguro · Pólizas y liquidación · Regímenes especiales · Seguro de vida adicional · Informes |
| 8 | **Tesorería** | Órdenes de pago · Chequeras · Reporte de OP (por tipo) · **Informe de OP (generador)** |
| 9 | **Adm. y Finanzas** | Proveedores |
| X | **General** | Usuarios · Perfiles · Parámetros · Organismos · Oficinas · Compañías · Maestro de agentes/Clientes · Auditoría |

> **Faltan muchas ventanas** de DATOS/PROCESOS/REPORTES (sobre todo Créditos 330,
> Caja 230, Tesorería 830). El detalle está más abajo (sin ✅) y en `faltantes-menu.md`.


<!-- Despacho: recorrido de comportamiento en la app OK (H-034). Modelos (338),
Resoluciones (11.337 borrador + 29.932 firmadas — estado real bien migrado; asunto es
placeholder generado desde modelos RTF), Anexo (solicitudes reales) y Expedientes (48.105,
oficina resuelta a nombre) verificados con dato real en el navegador. -->
## 1 · DESPACHO

### 105 · ARCHIVOS
- ✅ **10505** MODELOS DE RESOLUCIONES  → `DO FORM FORMULARIOS\105050000MODEL` · [Modelos de resoluciones] (338 reales)

### 120 · DATOS
- ✅ **12005** RESOLUCIONES  → `DO FORM FORMULARIOS\120050000RESO_` · [Resoluciones y disposiciones]
- ✅ **12010** ANEXO RESOLUCION  → `DO FORM FORMULARIOS\120100000anexo_res_dis` · [Anexo de resolución: **asignación de lote real**] — reconstruido del fuente VFP (H-026): selector de tipo (AGAP/Microcréditos/Productivos/Vivienda/Gas/Resto → rango de líneas), grilla de solicitudes aprobadas sin resolución, asignación de lote (N° correlativo + fecha → `en_reso`/`no_resol`/`fecha_resol`), reimpresión por lote y Excel. **78.443 solicitudes migradas** de `solicitud.dbf`.

### 130 · REPORTES
- ≈ **13005** LISTADO DE RESOLUCIONES  → `DO FORM FORMULARIOS\FRM130050000RP` · [Resoluciones y disposiciones: listado paginado + Word]

## 2 · CAJA

### 220 · DATOS
- ⚪ **22005** LEE DISKETTE QUINIELA  → `DO FORM FORMULARIOS\FRM220050000LE` — lector de **binario de diskette** (insumo externo). El dato que cargaba (`cajaliq`) ya está migrado del backup, así que la caja opera sobre dato real; para nuevas cargas haría falta un import manual/CSV.
- ⚪ **22010** LEE PEN DRIVE DE QUINIELA NUEVA VERSION WEB  → `DO FORM FORMULARIOS\FRM220050000LE` — ídem (pendrive/web). Bloqueado por el layout externo.

### 225 · PROCESOS
- ✅ **22505** ABRIR CAJA / APLICATIVO DE CAJA  → `DO FORM FORMULARIOS\FRM225050000AP` (`aplicaj`) · [Aplicativo de caja — Quiniela] — reconstruido del fuente: cobro de liquidaciones de **agencias de quiniela** con **bonos/pesos**, vuelto por moneda (adeudado − cobrado, verde/rojo) y **premios**, graba `cajapagos` y marca las liquidaciones. **Dato real migrado: 60.000 liquidaciones + 31.714 recibos de agencia** (`cajaliq`/`cajapagos`).
- **22510** \-
- ✅ **22515** CRÉDITOS, SEGUROS, ETC.  → `DO FORM FORMULARIOS\FRM225150000CR` · [Cobranza de caja → **Cola por persona**] — reconstruido del fuente (`frm225150000cresegu1`): búsqueda por CUIL/DNI/nombre, cola de cuotas pendientes de TODOS los créditos de la persona con interés punitorio + IVA, cobro multi-crédito en **un solo recibo**, anulación reversible. (Seguros/juegos extraordinarios en la cola: próximo incremento.)
- **22520** \-
- ✅ **22525** ANULA PAGOS/COBROS  → `DO FORM FORMULARIOS\FRM225250000AN` · [anulación de recibo] — revierte cuotas y saldo del crédito (multi-crédito), reactiva crédito cancelado; y anulación de cobro de agencia de quiniela.
- ✅ **22530** CONTROL DE CAJA  → `DO FORM FORMULARIOS\FRM225300000CT` · [Control de caja] — ahora **incluye los cobros de quiniela** (`cajapagos`) además de los recibos de créditos/seguros, detallado por cajero.
- ✅ **22535** CIERRE DE CAJA  → `DO FORM FORMULARIOS\FRM225350000CI` · [Cierre de caja] — cierre del día por cajero + **por moneda** (pesos/bonos, `c_cierremoneda`), sumando créditos/seguros y **quiniela** (`cajapagos`).
- **22540** \-
- 🟠 **22542** PAGO A AGENCIAS TRANSFERIDAS  → `DO FORM FORMULARIOS\FRM225420000PA` — **egreso**: genera la transferencia bancaria a agencias con neto a favor. Depende del **layout de transferencia del banco** (externo). El cálculo del neto ya está (ver 23057 Cheques para agencias).
- 🟠 **22545** PAGO AUTOMÁTICO DE PREMIOS  → `DO FORM FORMULARIOS\FRM225450000PA` — egreso automático de premios; depende del rail de pago externo.
- 🟠 **22550** PAGO AUTOMÁTICO DE AGENCIAS DEL INTERIOR  → `DO FORM FORMULARIOS\FRM225500000PA` — egreso a agencias del interior; depende del layout de transferencia externo.
- ✅ **22555** INFORME DE DEUDA DE AGENCIA  → `DO FORM FORMULARIOS\FRM225550000IN` · [Deuda de agencia] — liquidaciones **impagas** por agencia (o todas) y rango de vencimiento, con días de atraso, sobre dato real (26 impagas, $2,41M).
- 🟠 **22560** GENERACIÓN DE INFORMACIÓN PARA A.G.R.  → `DO FORM FORMULARIOS\AGR` — export para la **A.G.R.** (organismo de control); depende del **formato de intercambio A.G.R.** (externo).

### 230 · REPORTES
- **23005** PENDIENTES/INGRESOS  → `DO FORM FORMULARIOS\FRM230050000RP`
- ✅ **23010** REIMPRESIÓN DE RECIBOS  → `DO FORM FORMULARIOS\frm230100000RP` · [Reimpresión de recibos] — recibos emitidos en un día, unificando quiniela (`cajapagos`) y créditos/seguros/extra (`cajacreseg` por no_recibo), con **botón "Reimprimir" que regenera el PDF** desde el dato (endpoint `/caja/recibos-del-dia/reimprimir`). Verificado 2025-08-26: 308 recibos (278 quiniela = $179,6M coincide con la DB); PDF real del recibo 32935 OK. **Los comprobantes no se guardan como archivo: se regeneran on-demand desde las tablas (igual que el VFP).**
- ✅ **23012** REIMPRESIÓN DE RECIBOS HISTÓRICO  → `DO FORM FORMULARIOS\frm230100000RP` · [Reimpresión de recibos] — misma pantalla sobre dato histórico (el backup ya es histórico).
- ✅ **23015** MENSUAL DE INTERESES E IVA  → `DO FORM FORMULARIOS\FRM230150000RP` · [Intereses e IVA (mensual)] — interés e IVA (normal + punitorio) cobrado en el mes por origen, de `cajacreseg` (créditos/seguros/extra) + `cajaliq` (quiniela). Verificado 06/2026: interés $106.178.992,04, IVA $14.565.393,20 (coincide con la DB). **Migrado `cajacreseg`: 5.629 cobros reales.**
- ✅ **23020** INFORME DE PREMIOS DE QUINIELA  → `DO FORM FORMULARIOS\FRM230200000PR` · [Premios de quiniela] — control de premios (egresos) de un día, modos cobradas/pendientes/ambas, resumen por cajero. Verificado 2025-08-12: 1.083 premios, $51.839.851,83 (coincide con la DB).
- ✅ **23025** PAGOS REALIZADOS  → `DO FORM FORMULARIOS\FRM230250000LI` · [Pagos realizados] — listado de `cajacreseg` en un rango de fechas (no revertidos), filtrable por tipo de ingreso (coding) y por texto/nombre. Verificado 06/2026 coding=80: 276 pagos, $166.844.766,18 (coincide con la DB).
- ✅ **23030** RECAUDACION ANUAL P/ORIGEN-MES  → `DO FORM FORMULARIOS\FRM230300000RE` · [Recaudación anual] — totales por origen (créditos/seguros + quiniela) × mes del año, con premios. Verificado 2025: total $11.359.800.690,13 (coincide mes a mes con la DB).
- ✅ **23035** INFORME DE INGRESOS BRUTOS  → `DO FORM FORMULARIOS\FRM230350000IN` · [Ingresos brutos] — retención de IIBB por agencia sobre las liquidaciones cobradas en un mes/año (recaudación, comisiones, ing_brutos). Verificado 08/2025: 273 agencias, IIBB $2.098.532,15 (contrastado contra la DB).
- ✅ **23040** REIMPRESION CIERRE DE CAJA A UNA FECHA  → `DO FORM FORMULARIOS\FRM230400000RE` · [Cierre de caja → PDF] — reimprime el cierre (22535) de una fecha en PDF (por moneda pesos/bonos + quiniela + conceptos de crédito). Verificado 2025-08-26 (PDF OK).
- ✅ **23045** PLANILLA P/CONTABILIDAD CREDITOS COBRADOS P/DIA  → `DO FORM FORMULARIOS\FRM230450000RC` · [Planilla contable (créditos/día)] — créditos cobrados en un día (`cajacreseg` CRED) descompuestos por concepto contable (capital, interés, IVA, seguro, gastos, punitorio). Verificado 2025-12-10: 87 créditos, total $36.017.476,86 (coincide con la DB).
- ✅ **23050** INFORME DE LIQUIDACIONES COBRADAS EN UNA FECHA  → `DO FORM FORMULARIOS\FRM230500000LI` · [Liquidaciones cobradas (día)] — liquidaciones de quiniela pagadas en un día, resumen por cajero + detalle. Verificado 2025-08-26: 2.648 liq., $200.312.500,67 (coincide con la DB).
- ✅ **23055** LISTADO DE COMPENSACIONES POR CAPITAL/INTERIOR  → `DO FORM FORMULARIOS\FRM230550000PR` · [Premios compensados] — compensación de premios por agencia, separada en Capital e Interior, para una fecha de vto. Verificado 2025-10-20: Capital 136 ag. $185,9M + Interior 31 ag. $16,5M = $202.472.161,68 (coincide con la DB).
- ✅ **23057** LISTADO DE CHEQUES PARA AGENCIAS  → `DO FORM FORMULARIOS\FRM230570000LI` · [Cheques para agencias] — agencias con neto a favor (`sum(total_gral) <= -10000`) en una fecha de vto., que reciben cheque por el neto. Verificado 2025-10-20: 23 agencias, $10.882.720,44 (coincide con la DB).
- ✅ **23060** REIMPRESION CONTROL CAJA DE CAJERO  → `DO FORM FORMULARIOS\FRM230600000RE` · [Control de caja → PDF por cajero] — reimprime el control de caja (22530) de una fecha filtrado por cajero, en PDF. Verificado 2025-08-26 cajero crockb (PDF OK).
- ✅ **23065** INFORME DE COBRANZAS EN UN PERÍODO  → `DO FORM FORMULARIOS\FRMINFORMECOBR` · [Cobranzas en un período] — unifica recibos de **créditos/seguros** + cobros de **quiniela** entre dos fechas, con totales separados (verificado ago-2025: 4.185 cobros quiniela, $2.299.970.143,39).

## 3 · CRÉDITOS

### 305 · ARCHIVOS
- **30505** Prueba creditos  → `DO FORM FORMULARIOS\0001CRSC`
- **30510** ADMINISTRACIÓN DE LINEAS  → `DO FORM FORMULARIOS\FRM305050000LI`
- **30515** REQUISITOS PARA CRÉDITOS  → `DO FORM FORMULARIOS\FRM305150000RE`
- **30520** MODELOS DE DISPOSICION DE CRÉDITOS  → `DO FORM FORMULARIOS\105050000MODEL`
- **30525** ADMINISTRACION DE GASISTAS  → `DO FORM FORMULARIOS\FRM305250000GA`
- **30530** CUPO MAXIMO A OTORGAR POR PERIODO  → `DO FORM FORMULARIOS\FRM305300000MO`
- **30540** GENERA CUOTAS PLAFORMA  → `DO FORM FORMULARIOS\FRMCUOTAPLAT`

### 310 · LISTADOS
- ✅ **31010** LINEAS DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM310100000LI` · [Líneas de crédito]

### 315 · CONSULTAS
- ✅ **31505** SOLICITUDES DE CRÉDITOS  → `DO FORM FORMULARIOS\consulta_solic` · [Solicitudes]
- ✅ **31515** CRÉDITOS LEY 5094  → `DO FORM FORMULARIOS\FRM315150000CO` · [Jubilados / Ley 5094]
- **31520** DATOS DE CONTROL  → `DO FORM FORMULARIOS\FRM315200000DA`
- ✅ **31525** ORGANISMOS  → `DO FORM FORMULARIOS\FRM315250000OR` · [Organismos]
- ✅ **31530** CONSULTA HISTÓRICO DE ENVIOS REALIZADOS  → `DO FORM FORMULARIOS\FRM315300000CO` · [Envíos / padrón]
- ✅ **31535** ESTADISTICAS VARIAS  → `DO FORM FORMULARIOS\FRM315350000ES` · [Estadísticas de cartera]
- ✅ **31537** CANTIDADES Y SITUACION DE CREDITOS POR CARTERA  → `DO FORM FORMULARIOS\315350000ESTAD` · [Créditos por cartera]
- ✅ **31540** SITUACIÓN DE MARGEN DE CLIENTE  → `DO FORM FORMULARIOS\FRM315400000SI` · [Situación del cliente]
- **31544** \-
- **31545** CONSULTAS VARIAS DE SOLICITUDES (submenú)
-   ✅ **3154505** SOLICITUDES SIN DEBITO AUTOMÁTICO  → `DO FORM FORMULARIOS\FRM315450500SO` · [Sin débito automático]
-   ✅ **3154510** SOLICITUDES SIN DEBITO AUTOMATICO LINEA 25  → `DO FORM FORMULARIOS\FRM315451000SO` · [Sin débito automático + filtro de línea]
-   ✅ **3154515** SOLICITUDES ACTIVAS  → `DO FORM FORMULARIOS\FRM315451500SO` · [Solicitudes / Pendientes de cobro]
- **31546** \-
- ✅ **31555** CONSULTA PAGOS DE CREDITOS EN CAJA  → `DO FORM FORMULARIOS\FRM315550000PA` · [Pagos en caja]
- ✅ **31560** CONSULTA DE TURNOS OTORGADOS  → `DO FORM FORMULARIOS\FRM315620000CO` · [Turnos otorgados]
- ✅ **31565** HISTORIAL DE CREDITOS ACTIVOS DE UN CLIENTE  → `DO FORM FORMULARIOS\FRM315650000HI` · [Situación del cliente]

### 320 · DATOS
- **32003** CRÉDITOS POR SALUD  → `DO FORM FORMULARIOS\FRM_CR_HISCLIN`
- **32005** COBROS POR CAJA  → `DO FORM FORMULARIOS\FRM320050001PA`
- **32007** CANCELA CREDITOS POR BANCO PATAGONIA  → `DO FORM FORMULARIOS\FRM320070000BP`
- **32008** ANEXO DISPOSICION GENERAL  → `DO FORM FORMULARIOS\120100000anexo`
- **32009** DISPOSICIONES DE CREDITOS  → `DO FORM FORMULARIOS\120050000RESO_`
- **32010** SOLICITUD DE CRÉDITO  → `DO FORM FORMULARIOS\FRM320100000SO`
- **32012** SOLICITUD CREDITO ENTIDADES FINANCIERAS  → `DO FORM FORMULARIOS\320999999ENTFI`
- **32014** CANCELA CUOTAS IVA MANUAL  → `DO FORM FORMULARIOS\FRM320150000PA`
- **32015** CANCELA CUOTAS  → `DO FORM FORMULARIOS\FRM320150000PA`
- **32016** CANCELA CUOTAS PRODUCIR  → `DO FORM FORMULARIOS\FRM320160000CA`
- **32018** CANCELA CUOTAS POR TRANSFERENCIAS  → `DO FORM FORMULARIOS\FRM320180000CA`
- **32019** ADMINISTRACION DE VOUCHER'S FOMENTO TURISMO PROV.  → `DO FORM FORMULARIOS\FRM320190000FO`
- **32020** LIQUIDACIÓN DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM320200000LC`
- **32021** LIQUIDACION CREDITOS ESPECIALES  → `DO FORM FORMULARIOS\FRM320200000LC`
- **32022** LIQUIDACION CREDITOS NOTEBOOCK  → `DO FORM FORMULARIOS\FRM320200000LC`
- **32025** CRÉDITOS LEY 5094 (submenú)
-   **3202505** SOLICITUD 5094  → `DO FORM FORMULARIOS\FRM320250500SO`
-   **3202510** PRORROGA 5094  → `DO FORM FORMULARIOS\FRM320251000SO`
-   **3202515** RECALCULO E IMPRESION SOL. Y PAG. 5094  → `DO FORM FORMULARIOS\FRM3202515SOLP`
- **32035** REINTEGRO DE CUOTAS  → `DO FORM FORMULARIOS\frm320350000re`
- **32040** ALTERNAR DESCUENTO ENTRE SOLICITANTE Y GARANTE  → `DO FORM FORMULARIOS\FRM320400000AL`
- ✅ **32045** CANCELACIÓN DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM320450000CA` (`cancre`) · [Cancelación de crédito] — cancelación anticipada: cuotas **vencidas** completas + mora, cuotas **futuras** sólo capital (**condona el interés no devengado**); emite recibo, salda todas las cuotas, `saldo_capital=0`, estado C. Verificado con crédito real 110573 (5 cuotas, total $15.073,32; capital coincide con la DB).
- **32046** CANCELA CREDITO IVA MANUAL  → `DO FORM FORMULARIOS\FRM320450000CA`
- **32050** INFORMACION DE UBICACION DE CREDITOS  → `DO FORM FORMULARIOS\FRM320500000IU`
- **32055** SUBSIDIOS JUBILADOS  → `DO FORM FORMULARIOS\FRM320550000SU`
- **32060** LIQUIDACION DE SUBSIDIOS  → `DO FORM FORMULARIOS\FRM320600000LI`
- **32062** \-
- ✅ **32065** ADMINISTRACION DE DIAS-TURNOS  → `DO FORM FORMULARIOS\FRM320700000TU` (`turnosnuevo`) · [Turnos — generar] — genera los turnos del mes distribuidos por día hábil: `turnos/día = INT(total/días_hábiles)`, el resto se reparte de a uno en los primeros días; numeración secuencial, con **vista previa** de la distribución. (Sin tabla de feriados migrada: excluye sólo fines de semana.) Verificado: 100 turnos / 209905 → 21 días, 4/día, resto 16.
- ✅ **32067** ENTREGA DE TURNOS PARA CARGA DE CREDITOS  → `DO FORM FORMULARIOS\FRM320720000CL` (`clienteturno`) · [Turnos — asignar] — asigna el próximo turno libre del período a un solicitante (CUIL/nombre).
- ✅ **32068** TURNOS EXCEPCIONALES  → `DO FORM FORMULARIOS\FRM320680000TU` (`turnos_e`) · [Turnos — asignar por N°] — asigna un turno puntual por número (mismo endpoint `asignar` con `numero`).

### 325 · PROCESOS
- **32502** CAMBIO AUTOMATICO DE SOL. A GTE. CTAS. EN MORA  → `DO FORM FORMULARIOS\FRM325020000CA`
- **32503** CHEQUEO DE CUOTAS A DESCONTAR EN UN PERIODO  → `DO FORM FORMULARIOS\FRM325030000CH`
- **32504** ARCHIVO BCO PATAGONIA PARA ENVIOS A DIO  → `DO FORM FORMULARIOS\FRM325040000BC`
- **32505** DESCUENTOS PARA ORGANISMOS LIQUIDADORES  → `DO FORM FORMULARIOS\FRM325050000GE`
- **32510** \-
- **32525** ACTUALIZACION DE MAESTROS  → `DO FORM FORMULARIOS\FRM325250000MA`
- **32530** \-
- ✅ **32535** RECALCULO CREDITOS  → `DO FORM FORMULARIOS\FRM325350000RE` (`reca`) · [Recálculo de cuotas] — reconstruido **exacto del fuente** (cero inferencia): dos modos — *reprogramar vencimientos* (`recaotros`: **sólo cambia `fecha_vto`** de las cuotas no pagadas; el reescrito de capital/interés está **comentado** en el fuente) y *jubilatorio* (`recaportes`: regenera el plan pendiente **capital puro**, cuota=10% del haber, última=resto). **Vista previa obligatoria** (actual vs propuesto), nunca toca cuotas pagadas. Verificado con crédito real 110573 (preview no escribe).
- ⚪ **32537** RECALCULA INT. MORA EN CUOTAS VENCIDAS  → `DO 'PRGS\ACTUALIZA INTERESES'` — **no aplica**: en el sistema nuevo la mora se calcula **en vivo** (`domain/mora`), no se almacena en la cuota; no hay valor a refrescar.
- **32538** GENERA PLAN DE CUENTA DE CREDITOS ESPECIALES  → `DO FORM FORMULARIOS\FRM_GENERA_HIP`
- **32539** PAGO DE ADICIONAL DE CREDITOS ESPECIALES  → `DO FORM FORMULARIOS\frm_carga_nuev`
- **32540** GENERA PLAN NUEVO INDEXADO  → `DO FORM FORMULARIOS\frm_genera_cuo`
- **32541** GENERA PLAN CON TASA BADLAR  → `DO FORM FORMULARIOS\frm_genera_cuo`
- **32542** GENERA CUOTAS AMARTIZADAS MANUAL  → `DO FORM FORMULARIOS\frm_genera_cuo`
- **32545** \-
- **32550** APLICA DESCUENTOS  → `DO FORM FORMULARIOS\FRM325500000AP`
- **32555** APLICA DESCUENTOS CRED.PRODUCIR RECIBIDOS DE O.LIQ  → `DO FORM FORMULARIOS\FRM325550000CC`
- **32560** \-
- ✅ **32565** BAJA DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM325650000BA` (`bajacre`) · [Baja de crédito] — anulación administrativa con **motivo obligatorio**; **no** admite créditos con cuotas pagadas (para ésos, cancelación 32045); marca estado B, anula cuotas y libera margen. Verificado con crédito real 110142 (rechazo correcto por tener pagos).

### 330 · REPORTES
- **33005** VARIOS (submenú)
-   **3300502** SOLICITUDES CARGADAS  → `DO FORM FORMULARIOS\FRM330050000SO`
-   **3300504** REIMPRESIÓN DE LIQUIDACIONES  → `DO FORM FORMULARIOS\330100000REIMP`
-   **3300505** REIMPRESION DE LIQUIDACION 1  → `DO FORM FORMULARIOS\330100000REIMP`
-   **3300506** COBROS MANUALES DEL DÍA  → `DO FORM FORMULARIOS\FRM330150000RP`
-   **3300508** CREDITOS CARGADOS ENVIADOS A AUDITORIA  → `DO FORM FORMULARIOS\FRM330170000EN`
- **33010** INFORME DE DEUDA  → `DO FORM FORMULARIOS\FRM330200000IN`
- **33015** CONTROL DE CREDITOS  → `DO FORM FORMULARIOS\FRM3302600CNTR`
- **33017** CREDITOS LEY 5059 (submenú)
-   **3301704** CRÉDITOS LEY 5094  → `DO FORM FORMULARIOS\FRM330250500SO`
-   **3301706** CRÉDITOS LEY 5094 P/DEPTO.  → `DO FORM FORMULARIOS\FRM330251000SO`
-   **3301708** CLIENTES LEY 5094  → `DO FORM FORMULARIOS\FRM330251500CL`
-   **3301710** TOTALES PAGADOS LEY 5094  → `DO FORM FORMULARIOS\FRM330252000TO`
- **33020** INFORMES AGAP (submenú)
-   **3302002** INFORME DE PREVIOS PAGOS (P/LINEA)  → `DO FORM FORMULARIOS\CB-PREPAG-LINE`
-   **3302004** RESUMEN DE ENVIOS DE AGAP P/DESCONTAR  → `DO FORM FORMULARIOS\FRM330702000RE`
-   **3302006** INFORME DE CRÉDITOS POR LINEAS  → `DO FORM FORMULARIOS\FRM330650000CR`
- **33030** TRIBUNAL DE CUENTAS - REPORTES (submenú)
-   **3303005** CREDITOS PAGADOS  → `DO FORM FORMULARIOS\FRM330300500TD`
-   **3303010** CREDITOS CANCELADOS  → `DO FORM FORMULARIOS\FRM330301000TD`
- ✅ **33035** CRÉDITOS VIGENTES  → `DO FORM FORMULARIOS\FRM330350000LI` · [Informe de créditos: estado=Activo]
- **33040** RECUPERACIÓN DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM330400000LI`
- **33045** REPORTES DE IVA (submenú)
-   **3304505** IVA COBRADO  → `DO FORM FORMULARIOS\FRM330450500LI`
- ✅ **33050** CRÉDITOS PAGADOS  → `DO FORM FORMULARIOS\FRM330500000CR` · [Informe de créditos: estado=Cancelado]
- **33055** VENCIMIENTO DE CRÉDITOS PARTICULARES  → `DO FORM FORMULARIOS\FRM330550000CR`
- **33060** REPORTE DE CUOTAS EN MORA  → `DO FORM FORMULARIOS\FRM330600000CT`
- **33067** CONTROL MARCA DEBITO AUTOMATICO  → `DO FORM FORMULARIOS\FRM330670000CT`
- **33068** CONTROL DE CREDITOS PAGADOS  → `DO FORM FORMULARIOS\FRM330680000CT`
- **33069** \-
- **33070** REIMPRESIONES (submenú)
-   **3307005** REIMPRESIÓN PAGARÉ JUBILADOS LEY 5094  → `DO FORM FORMULARIOS\FRM330700500JU`
-   **3307010** REIMPRESION DE APLICACIONES  → `DO FORM FORMULARIOS\frm330701000re`
-   **3307015** REIMPRESION DE ENVIOS  → `DO FORM FORMULARIOS\FRM330701500RE`
- **33072** \-
- **33075** REPORTE DE CTA.CTE. JUBILADOS  → `DO FORM FORMULARIOS\FRM330750000CT`
- **33080** PAGOS REALIZADOS EN UNA FECHA  → `DO FORM FORMULARIOS\FRM330800000CU`
- **33082** \-
- **33085** INFORMES VARIOS (submenú) — *mayormente cubierto por [Informe de créditos]*
-   ✅ **3308505** INFORME DE ESTADO DE CREDITOS  → `DO FORM FORMULARIOS\FRM330850500IN` · [Informe de créditos]
-   ✅ **3308510** INFORME DE SALDOS DE CREDITOS  → `DO FORM FORMULARIOS\FRM330851000IN` · [Informe de créditos: con saldo]
-   **3308515** INFORME DE UBICACION DE CREDITOS  → `DO FORM FORMULARIOS\FRM330851500UI`
-   ≈ **3308520** CREDITOS ACTIVOS POR DPTO.  → `DO FORM FORMULARIOS\FRM330852000CR` · [Informe de créditos: filtro organismo]
-   ✅ **3308525** INFORME DE CREDITOS CANCELADOS  → `DO FORM FORMULARIOS\FRM331000000IN` · [Informe de créditos: estado=Cancelado]
-   **3308530** INFORME DE CREDITOS POR SALUD OTORGADOS  → `DO FORM FORMULARIOS\FRM330990000CR`
-   **3308535** INFORME PAGOS CR. GAS DESDE-HASTA  → `DO FORM FORMULARIOS\FRM330853500IN`
-   **3308537** INFORME DE PAGOS DE ANTICIPOS DE GAS  → `DO FORM FORMULARIOS\FRM330853700IN`
-   **3308540** INFORME CRÉDITOS EN MORA SIN PAGOS EN UN  PERIODO  → `DO FORM FORMULARIOS\FRM330854000CR`
-   **3308545** INFORME DE CRÉDITOS QUE SE PAGAN POR CAJA  → `DO FORM FORMULARIOS\FRM330854500CR`
-   **3308550** INFORME DE APLICACIONES P/PERIODO Y ORGANISMO  → `DO FORM FORMULARIOS\FRM330855000IN`
-   **3308555** INFORME DE QUEBRANTOS POR FALLECIMIENTOS  → `DO FORM FORMULARIOS\frm330855500in`
- **33087** \-
- **33090** LISTADO DE REINTEGROS DE CUOTAS  → `DO PRGS\PRG330900000REINTEGROS`
- **33092** CREDITOS CON MARCA DE BAJA  → `DO FORM FORMULARIOS\FRM330920000MA`
- **33095** REPORTE DE CUOTAS NO ENVIADAS  → `DO FORM FORMULARIOS\FRM330950000NO`
- **33096** PRODUCIR CTAS. IMPAGAS 10 MESES  → `REPORT FORM REPORTES\RPT330960000I`
- **33097** REPORTE DE FUTUROS VENCIMIENTOS  → `DO FORM FORMULARIOS\FRM330970000FU`
- **33098** REPORTE DE DEVENGAMIENTO  → `DO FORM FORMULARIOS\FRM330980000DE`

### 335 · PARÁMETROS
- **33505** MODIFICACIÓN GRAL. DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM335050000MO`
- **33506** MODIFICACION SOL-PRE-CTA  → `DO FORM FORMULARIOS\FRM335060000MO`
- **33507** CORRECCIÓN DE O.P. EN CRÉDITOS Y TESORERÍA  → `DO FORM FORMULARIOS\MODOP`
- **33508** \-
- **33510** CAMBIA FECHA VTO. A CUOTAS  → `DO FORM FORMULARIOS\FRM335100000CA`
- **33511** \-
- **33515** CONTROL DE SOLICITUDES CON DIO (SOLICITANTE)  → `DO FORM FORMULARIOS\FRM335150000CO`
- **33516** CONTROL DE SOLICITUDES CON DIO (GARANTE 1)  → `DO FORM FORMULARIOS\FRM335150001CO`
- **33517** CONTROL DE SOLICITUDES CON DIO (GARANTE 2)  → `DO FORM FORMULARIOS\FRM335150002CO`
- **33519** \-
- **33520** MODIFICACIÓN GRAL. LEY 5094  → `DO FORM FORMULARIOS\FRM335200000MO`
- **33521** \-
- **33526** CONTROL DE CUOTAS EN CAJA  → `DO FORM FORMULARIOS\FRM335260000CO`
- **33529** \-
- **33535** PARAMETROS DE CREDITOS  → `DO FORM FORMULARIOS\FRM335350000PA`

## 4 · JUEGOS

### 405 · ARCHIVOS
- **40502** MODELOS DE DISPOSICIONES DE JUEGOS  → `DO FORM FORMULARIOS\105050000MODEL`
- ✅ **40505** AGENCIAS  → `DO FORM FORMULARIOS\FRM405050001MA` · [Agencias y liquidaciones]
- ✅ **40510** JUEGOS  → `DO FORM FORMULARIOS\FRM405100000MA` · [Maestro de juegos]
- ✅ **40515** SORTEOS  → `DO FORM FORMULARIOS\FRM405150000MA` · [Control de sorteos]

### 410 · LISTADOS
- **41005** AGENCIAS  → `DO FORM FORMULARIOS\FRM410050000RP`

### 415 · CONSULTAS
- **41505** PREMIOS JUEGOS ALTERNATIVOS  → `DO FORM FORMULARIOS\FRM415050000PR`

### 420 · DATOS
- **42002** DISPOSICIONES DE JUEGOS  → `DO FORM FORMULARIOS\120050000RESO_`
- **42005** SORTEOS PRODE  → `DO FORM FORMULARIOS\FRM420050000CA`
- **42010** COBRO JUEGOS EXTRA.  → `DO FORM FORMULARIOS\FRM420100000PA`
- **42015** COBRO VALOR LLAVE  → `DO FORM FORMULARIOS\FRM420150000PA`
- **42020** PAGOS DE JUEGOS  → `DO FORM FORMULARIOS\FRM420200000PA`

### 425 · PROCESOS
- **42505** IMPORTAR JUEGOS  → `DO FORM FORMULARIOS\FRM425050000IM`
- **42510** EXPORTAR A CAJA  → `DO FORM FORMULARIOS\FRM425100000EX`
- **42515** PASA LIQUIDACIONES A HISTÓRICO  → `DO FORM FORMULARIOS\FRM425150000HI`
- **42520** GENERACION DE COMISIONES AGENCIAS P/AFIP  → `DO FORM FORMULARIOS\FRM425200000GE`

### 430 · REPORTES
- **43005** BOLETAS DE VENCIMIENTO  → `DO FORM FORMULARIOS\FRM430050000RP`
- **43010** PLANILLA DE TOTALES PARA CAJA  → `DO FORM FORMULARIOS\FRM430100000RP`
- **43015** MENSUAL DE ING. BRUTOS  → `DO FORM FORMULARIOS\FRM430150000RP`
- **43020** COBRANZAS DE UN DÍA  → `DO FORM FORMULARIOS\FRM430200000RP`
- ✅ **43025** RESUMEN DE FONDO DE GTÍA.  → `DO FORM FORMULARIOS\FRM430250000IN` · [Fondo de garantía] — une liquidaciones **históricas (jghisliq, 273.589) + vigentes** y suma `fdo_gtia` por agencia con detalle por juego (H-037). Verificado: total $199.611,71 (cuadra con el control directo), 667 agencias, ag.20 $100.885,12.
- ✅ **43030** RESUMEN DE CUENTA AGENCIA  → `DO FORM FORMULARIOS\FRM430300000RE` · [Ingresos por juego]
- **43035** CHEQUEA TITULARES DE AGENCIAS CON ADM.PUBLICA  → `DO FORM FORMULARIOS\FRM430350000CH`
- ✅ **43045** INFORME DE INGRESOS DE JUEGOS  → `DO FORM FORMULARIOS\FRM430450000IN` · [Ingresos por juego]

## 5 · MESA DE ENTRADAS

### 515 · CONSULTAS
- ✅ **51505** TRÁMITES PENDIENTES  → `DO FORM FORMULARIOS\FRM515050000TR` · [Consulta de trámites]
- ✅ **51510** HISTORIAL DE UN TRÁMITE  → `DO FORM FORMULARIOS\FRM515100000HI` · [Consulta de trámites]

### 520 · DATOS
- **52005** TRÁMITES  → `DO FORM FORMULARIOS\FRM520050000CA`
- ✅ **52010** PASES  → `DO FORM FORMULARIOS\FRM520100000PA` · [Consulta de trámites → ver pases]

### 530 · REPORTES
- ✅ **53005** TRÁMITES INGRESADOS  → `DO FORM FORMULARIOS\FRM530050000TR` · [Trámites ingresados]
- **53010** INFORME DE TRAMITES PENDIENTES EN UNA OFICINA  → `DO FORM FORMULARIOS\FRM530100000LI`

## 6 · CONTABILIDAD

### 605 · EGRESOS
- ✅ **60505** REPORTE DE IVA DE CREDITOS PAGADOS  → `DO FORM FORMULARIOS\CB-EGIVAEGRESO` · [IVA por período]
- ✅ **60510** REPORTE DE O.P. DEVENGADAS EN UN PERÍODO  → `DO FORM FORMULARIOS\CB-OP-DEV-PERI` · [OP devengadas]
- ✅ **60515** REPORTE DE IVA DE GS.ORIG. Y QUEB. EN PERIODO  → `DO FORM FORMULARIOS\CB-IVA-GSOQ-PE` · [IVA egresos]
- ✅ **60550** REVISION TRANSACCIONES DE EGRESOS  → `DO FORM FORMULARIOS\CB-EGREVIEGRES` · [Revisión egresos]

### 610 · INGRESOS
- ✅ **61005** REPORTE DE IVA DE CUOTAS COBRADAS  → `DO FORM FORMULARIOS\CB-CJCREDITOSC` · [IVA de cuotas cobradas (real)] — reconstruido sobre **dato real** (`maecuotas`): IVA débito (interés+seguro+gastos) de las cuotas con `fecha_pago` en el rango, por período. Verificado 2025: $224.647.446,13 (coincide con la DB). El reporte anterior sobre asientos de la app quedaba en $0.

### 615 · DATOS ASIENTOS
- ✅ **61505** ASIENTO DE OTORGAMIENTO  → `DO FORM FORMULARIOS\CB-CRASIENTOOT` · [Libro diario / automático]
- ✅ **61510** ASIENTO DE DEVENGAMIENTO  → `DO FORM FORMULARIOS\CB-CRASIENTODE` · [Libro diario / automático]
- **61515** REVISION DE CREDITOS BORRADOS  → `DO FORM FORMULARIOS\CB-CREVICREDBO`
- **61520** INFORME DE DEUDA DE UN CREDITO  → `DO FORM FORMULARIOS\FRM330200000IN`

## 7 · SEGUROS

### 705 · ARCHIVOS
- ✅ **70505** MAESTRO DE TITULARES LEY 5182  → `DO FORM FORMULARIOS\FRM705050000MA` · [Titulares de seguro] (122.784 reales)
- **70510** MODELOS DE DISPOSICIONES DE SEGUROS  → `DO FORM FORMULARIOS\105050000MODEL`

### 715 · CONSULTAS
- **71505** DIR. ASUNTOS PREVISIONALES  → `DO FORM FORMULARIOS\FRM731CONSSEG`
- **71510** PRIMAS DEVENGADAS  → `DO FORM FORMULARIOS\FRM715100000CO`
- **71511** PRIMAS DEVENGADAS HISTORICAS -2013  → `DO FORM FORMULARIOS\FRM715100000CO`
- **71515** CONSULTA EXPEDIENTES DE SEGUROS  → `DO FORM FORMULARIOS\FRM520100003CO`

### 720 · DATOS
- **72002** DISPOSICION DE SEGUROS  → `DO FORM FORMULARIOS\120050000RESO_`
- **72005** COBRANZA DE SEGUROS (CAJA)  → `DO FORM FORMULARIOS\FRM720050000CO`
- **72010** ACTUALIZA FICHAS DE SEGUROS  → `DO FORM FORMULARIOS\FRM720100000AL`
- **72015** LIQUIDACIÓN DE SEGUROS  → `DO FORM FORMULARIOS\FRM720150000PA`
- **72020** PENSION HEROES DE MALVINAS  → `DO FORM FORMULARIOS\FRM720200000EX`

### 725 · PROCESOS
- **72505** IMPORTAR INF. PREVISIONAL  → `DO FORM FORMULARIOS\FRM725050000IM`
- **72507** CONTROL DE INFORMACION PREVISIONAL AGAP  → `DO FORM FORMULARIOS\frm725070000co`
- **72510** EXPEDIENTES DE SEGUROS  → `DO FORM FORMULARIOS\FRM725100000EX`
- **72515** CUOTAS DE SUBSIDIOS  → `DO FORM FORMULARIOS\FRM725150000CU`

### 730 · REPORTES
- **73005** COBRANZA DE SEGUROS DE UN DIA  → `DO FORM FORMULARIOS\FRM730050000RP`
- **73010** DEUDA POR ORGANISMO  → `DO FORM FORMULARIOS\FRM730100000IN`
- ✅ **73015** AGENTES SIN SEGURO ADICIONAL  → `DO FORM FORMULARIOS\FRM730150000IN` · [Seguro de vida adicional]
- **73020** INFORME SEGUROS TESORERIA  → `DO FORM FORMULARIOS\FRM730200000IN`
- ✅ **73025** INFORME SEGURO ADICIONAL Y CONYUGE  → `DO FORM FORMULARIOS\FRM730250000IN` · [Seguro de vida adicional]

## 8 · TESORERÍA

### 805 · ARCHIVOS
- ✅ **80505** ADMINISTRACION DE LIBRETAS DE CHEQUES  → `DO FORM FORMULARIOS\frm805050000AL` · [Chequeras]
- ✅ **80510** ADMINISTRACION DE ORDENES DE PAGO  → `DO FORM FORMULARIOS\FRM805100000AL` (`altaop`) · [Cupos de OP (maestro)] — **corrección H-027 verificada con dato real**: la OP real (`maeop`) es un **cupo autorizado** (importe autorizado / usado / saldo, vigencia máxima, hasta 10 resoluciones, habilitada/cancelada/anulada), no un pago directo. Modelo `AutorizacionOP` + ETL: **35.040 cupos migrados** (29.504 habilitados; autorizado $57.211M, saldo $20.227M). Listado paginado + totales + ABM (alta con saldo=importe, edición recalcula saldo). La pantalla de "Órdenes de pago" anterior sigue siendo el registro de **pagos** (que consumen el cupo). **Circuito de consumo cerrado** (`820100 pagostesoreria`): un pago valida contra la OP — **existe, habilitada, no vencida (`fvigencia>hoy`), `csistema` coincide, `nsaldo>=importe`** — y descuenta (`usado+=importe`, `saldo=importe−usado`); reintegro reversible. Invariante `saldo=importe−usado` verificado en el dato real (34.845/35.040). Endpoints `/egresos/autorizaciones/{nop}/consumir|reintegrar` (verificado con cupo real 3271).

### 815 · CONSULTAS
- ✅ **81505** BUSCA TRANSACCIONES DE EGRESOS  → `DO FORM FORMULARIOS\FRM815050000BU` · [Busca transacciones de egresos] — **ledger real `egresos.dbf` (339.903)**, 7 modos de búsqueda (apellido/CUIL/recibo/resolución/fecha res/OP/fecha OP), fieles al form (H-040). Verificado: OP 486 → 109 egresos $46,7M, PEREZ → 1.405.

### 820 · DATOS
- **82005** RETENCIÓN DE PRIMAS DE SEGURO  → `DO FORM FORMULARIOS\FRM820050000AP`
- **82010** COBRO DE LICITACIONES  → `DO FORM FORMULARIOS\FRM820100000RE`
- **82015** PAGOS DE ADMINISTRACION  → `DO FORM FORMULARIOS\FRMpagostesore`
- **82020** PAGOS DE SEGUROS  → `DO FORM FORMULARIOS\FRMpagostesore`
- **82022** CARGA O.P. DE SEGUROS (SUBSIDIOS)  → `DO FORM FORMULARIOS\FRM78CUOTASDES`
- **82025** PAGOS DE CRÉDITOS  → `DO FORM FORMULARIOS\FRMpagostesore`
- **82040** PAGOS VARIOS  → `DO FORM FORMULARIOS\FRMpagostesore`
- **82045** PAGOS DE JUEGOS  → `DO FORM FORMULARIOS\FRMpagostesore`
- **82050** CARGA DATOS DE OP A RESOLUCION  → `DO FORM FORMULARIOS\FRM820500000OP`
- **82055** PAGOS SUBSIDIOS JUBILADOS  → `DO FORM FORMULARIOS\FRM820550000PA`

### 825 · PROCESOS
- **82505** DEPURACION DE EGRESOS  → `DO FORM FORMULARIOS\FRM825050000DE`
- **82510** CHEQUEA PAGOS C/Nº OP = 0  → `DO FORM FORMULARIOS\FRM825100000OP`
- **82515** GENERACION DISKETTE ACREDITACIONES  → `DO FORM FORMULARIOS\FRM825150000GE`
- **82520** ANULA PAGOS  → `DO FORM FORMULARIOS\FRM825200000AN`

### 830 · REPORTES
- **83005** LIQUIDACIONES DE CRÉDITOS  → `DO FORM FORMULARIOS\FRM830050000RP`
- **83010** SEGUROS PENDIENTES  → `DO FORM FORMULARIOS\FRM830100000RP`
- **83015** ORDENES DE PAGO (submenú)
-   ✅ **8301505** ORDENES DE PAGO/RECIBOS  → `DO FORM FORMULARIOS\FRM830150500RP` · [Reporte de OP · Informe de OP]
-   ✅ **8301510** ORDENES DE PAGO POR N°  → `DO FORM FORMULARIOS\FRM830151000RP` · [Informe de OP: búsqueda/filtros + Excel]
- **83020** DISTRIBUCIÓN DE UTILIDADES  → `DO FORM FORMULARIOS\FRM830200000RP`
- **83025** REIMPRESIÓN DE RECIBOS (submenú)
-   **8302505** RECIBOS DE UTILIDADES  → `DO FORM FORMULARIOS\FRM830250500RE`
-   **8302510** RECIBOS DE SUBSIDIOS LEY 5094  → `DO FORM FORMULARIOS\FRM830251000RE`
-   **8302515** RECIBOS DE ADMINISTRACION  → `DO FORM FORMULARIOS\FRMREIMPRESION`
-   **8302520** RECIBOS DE CRÉDITOS  → `DO FORM FORMULARIOS\FRMREIMPRESION`
-   **8302525** RECIBOS DE SEGUROS  → `DO FORM FORMULARIOS\FRMREIMPRESION`
-   **8302530** RECIBOS DE VARIOS  → `DO FORM FORMULARIOS\FRMREIMPRESION`
-   **8302535** RECIBOS DE PREMIOS  → `DO FORM FORMULARIOS\FRMREIMPRESION`
-   **8302540** REIMPRESION LISTADO DE ACREDITACIONES  → `DO FORM FORMULARIOS\FRM830254000RE`
- **83030** INFORME DE SELLADOS  → `DO FORM FORMULARIOS\FRM830300000RP`
- **83035** INFORME DE ESTADO SUBSIDIOS LEY 5094  → `DO FORM FORMULARIOS\FRM830350000AR`
- ✅ **83040** LISTADO DE CHEQUES EMITIDOS EN UNA FECHA  → `DO FORM FORMULARIOS\FRM830400000CH` · [Cheques emitidos] — 73.276 cheques reales (`cheques.dbf`), filtro por fecha/chequera/banco, resumen por tipo (H-038). Verificado: 73.258 no anulados $1.573.715.098,62 (cuadra), 2011-03-22 → 70 cheques.

### 835 · PARÁMETROS
- **83505** MODIFICACIÓN GENERAL JUBILADOS LEY 5094  → `DO FORM FORMULARIOS\FRM835050000MO`

## 9 · ADMINISTRACIÓN Y FINANZAS

### 905 · ARCHIVOS
- **90505** MODELOS DE DISPOSICIONES DE ADMINISTRACION  → `DO FORM FORMULARIOS\105050000MODEL`
- ✅ **90510** ADMINISTRACION DE PROVEEDORES  → `DO FORM FORMULARIOS\LYC905100000AD` · [Proveedores]

### 920 · DATOS
- **92005** DATOS DE COBRANZAS (INGRESOS)  → `DO FORM FORMULARIOS\LYC920050000IN`
- **92010** DATOS DE PAGOS (EGRESOS)  → `DO FORM FORMULARIOS\LYC920100000EG`
- **92015** DISPOSICIONES DE ADMINISTRACION  → `DO FORM FORMULARIOS\120050000RESO_`

## X · GENERAL

### X05 · ARCHIVOS
- **X0505** USUARIOS  → `DO FORM FORMULARIOS\FRM905050000AB`
- ✅ **X0510** PERFILES DE USUARIOS  → `DO FORM FORMULARIOS\FRM905100000AB` · [Perfiles] (19 reales, solo lectura)
- **X0515** FERIADOS  → `DO FORM FORMULARIOS\FRM905150000AB`
- **X0520** PARÁMETROS GENERALES  → `DO FORM FORMULARIOS\FRM905200000AB`
- **X0525** ORGANISMOS  → `DO FORM FORMULARIOS\FRM905250000AB`
- **X0530** \-
- **X0535** ADMINISTRACIÓN DE OPCIONES DEL MENÚ GENERAL  → `DO FORM FORMULARIOS\FRM905350000AB`
- **X0540** \-
- ✅ **X0545** ADMINISTRACION DE OFICINAS  → `DO FORM FORMULARIOS\FRM905450000AD` · [Oficinas] (151 reales)
- **X0550** ADMINISTRACION MAESTRO DE AGENTES PUBLICOS  → `DO FORM FORMULARIOS\FRM915100000CO`

### X10 · LISTADOS
- ✅ **X1005** LISTADO DE PERFILES  → `DO FORM FORMULARIOS\FRM910050000LI` · [Perfiles]

### X15 · CONSULTAS
- **X1505** CONSULTA MAESTRO DIO  → `DO FORM FORMULARIOS\FRM915050000CO`
- **X1510** CONSULTA PADRON CONFORMADO  → `DO FORM FORMULARIOS\FRM915100001CO`

### X20 · AUDITORIA
- **X2005** AUDITORIA DE CREDITOS  → `DO FORM FORMULARIOS\FRM920050000AU`
- **X2010** ADMINISTRACION INVENTARIO INFORMATICA  → `DO FORM FORMULARIOS\FRM920100000AD`

### X25 · PROCESOS
- **X2505** ACTUALIZA ORGANISMOS  → `DO FORM FORMULARIOS\FRM925050000AC`

### X30 · REPORTES
- ✅ **X3005** AUDITORÍA POR USUARIO  → `DO FORM FORMULARIOS\FRM930050000AU` · [Auditoría → Por usuario] — agrupa eventos por usuario (H-039). Verificado: 48 usuarios, crockb 12.308.
- ✅ **X3010** AUDITORÍA POR MÁQUINA  → `DO FORM FORMULARIOS\FRM930100000AU` · [Auditoría → Por máquina] — 48 máquinas, PB02CAJA 12.477.
- **X3015** TRANSACCIONES VENCIDAS  → `DO FORM FORMULARIOS\FRM930150000TR`

## Z · SALIR

### Z05 · SALIR DEL SISTEMA

### Z10 · CAMBIAR DE USUARIOS
