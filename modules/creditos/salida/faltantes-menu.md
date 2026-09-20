# Faltantes del menú real — pendientes honestos por módulo

> Revisión exhaustiva de [menu-real.md](menu-real.md) contra lo construido
> (2026-08-04). **Corrige el optimismo previo**: aunque el inventario da 111/377,
> el menú real operativo tiene **muchas ventanas de DATOS/PROCESOS/REPORTES sin
> hacer**, sobre todo en Créditos, Caja, Tesorería y Seguros.
>
> Categorías: 🟢 construible con dato del backup · 🟠 bloqueado por insumo externo
> (AFIP / previsional AGAP / layout de banco) · 🔵 variante/picker a consolidar ·
> ⚪ reporte de nicho / proceso puntual.

## 1 · DESPACHO
- ✅ **10505 Modelos de resoluciones** (`/despacho/modelos`, 338 reales, catálogo).
- ✅ **12010 Anexo resolución** (`/despacho/anexos`) — **rehecho con la lógica real**
  (H-026): asignación de un *lote* de solicitudes aprobadas a una resolución, por
  tipo (rango de líneas) + N° correlativo, reimpresión y Excel. **78.443 solicitudes
  migradas**.
- 🟢 **frm120050004rtf Creación/edición de modelo** (el catálogo es de solo lectura).
- ≈ 13005 Listado de resoluciones (cubierto por la pantalla Resoluciones).
- **Despacho queda prácticamente 100%** (solo falta el editor de modelos).
- ✅ **H-026 aplicado**: el fuente VFP (`.scx/.sct`) es legible y se usó para
  reconstruir el Anexo con el comportamiento exacto. **Expedientes** ya se corrigió a
  dato real (48.105 trámites E\*).

## 2 · CAJA — falta el grueso de reportes
- 🟢 **22505 Abrir caja**, **22525 Anula pagos/cobros**, **22555 Informe deuda de agencia**.
- 🟠 22005/22010 Lee diskette/pen quiniela · 22542/45/50 pagos a agencias/premios · 22560 AGR.
- **230 REPORTES (~15 sin hacer)**: reimpresión de recibos (23010/12), mensual de
  intereses e IVA (23015), premios de quiniela (23020), pagos realizados (23025),
  recaudación anual (23030), ingresos brutos (23035), reimpresión cierre (23040),
  planilla contab. cobrados/día (23045), liquidaciones cobradas (23050),
  compensaciones (23055), cheques para agencias (23057), control de cajero (23060),
  cobranzas en período (23065). Mayoría 🟢 (dato cargado), algunas 🟠 (quiniela).

## 3 · CRÉDITOS — el módulo con más deuda
- **305 ARCHIVOS**: 🟢 **30515 Requisitos** y **30525 Gasistas** (hay endpoints
  `/admin`, faltan pantallas), 🟢 **30530 Cupo máximo por período**, ⚪ 30540 genera cuotas plataforma.
- **320 DATOS (~26)**: 🔵 32010 Solicitud (cubierto por Solicitudes) y sus variantes
  (32012 entidades financieras, 5094). 🟢 **32035 Reintegro de cuotas**, **32045/32565
  Cancelación/Baja de crédito**, **32050 Ubicación de créditos**, **32055/60 Subsidios
  jubilados**. 🟠 **32007 Cancela por Banco Patagonia**, **32018 por transferencias**
  (layout banco). ⚪ liquidaciones especiales (32020/21/22), vouchers turismo (32019).
- **325 PROCESOS (~18)**: mayormente ⚪/🟠 — recálculos (32535/37), generación de
  planes (indexado/BADLAR/hipotecarios 32538-42), descuentos a organismos
  liquidadores (32505/50/55), archivo Patagonia (32504 🟠), baja de créditos (32565 🟢).
- **330 REPORTES (~50)**: **parcialmente cubierto por el nuevo Generador de
  informes de créditos** (`/creditos/informe`) — combina estado, línea, cartera,
  organismo, fechas y saldo, con Excel. Resuelve de un saque: estado, saldos,
  vigentes/cancelados, por línea/cartera/organismo, por depto (≈), activos con/sin
  saldo, otorgados por período. Siguen ⏳: deuda (33010), IVA cobrado (33045),
  vencimientos futuros (33097), cta.cte. jubilados (33075), quebrantos por
  fallecimiento, e informes AGAP (33020* 🟠). Mora ya tiene su pantalla.
- **335 PARÁMETROS (~13)**: 🟢/⚪ modificaciones generales (33505/20), correcciones
  (33507=modop), cambia fecha vto (33510), controles con DIO (33515/16/17).

## 4 · JUEGOS
- 🟢 **41505 Premios juegos alternativos**, **43005 Boletas de vencimiento**,
  **43010 Planilla totales para caja**, **43025 Fondo de garantía**, **43015/23035
  Ingresos brutos**, **43020 Cobranzas de un día**, **43035 Chequea titulares c/adm.**
- 🟠 42005 PRODE · 42010/15/20 cobros/pagos de juegos · **42505/10 Import/Export**,
  **42520 Comisiones AFIP** (insumos de intercambio).

## 5 · MESA DE ENTRADAS — casi completo
- 🟢 **52005 Trámites (ABM/carga)** · ⚪ 53010 Trámites pendientes por oficina (≈ con filtro).

## 6 · CONTABILIDAD — casi completo
- 🟢 **61515 Revisión de créditos borrados** · ⚪ 61520 Informe de deuda de un crédito (≈).

## 7 · SEGUROS — falta operatoria
- ✅ **70505 Maestro de Titulares** (`/seguros/titulares`, **122.784** reales,
  paginado + búsqueda). H-025 (bytes NUL saneados en el lector DBF).
- 🟢 **72005 Cobranza de seguros (Caja)**, **72010 Actualiza fichas**, **72510
  Expedientes de seguros**, **72515 Cuotas de subsidios**, **73005 Cobranza de un
  día**, **73010 Deuda por organismo**, **73020 Informe seguros Tesorería**.
- 🟠 **72505 Import previsional**, **72507 Control AGAP** (archivo provincial).
- ⚪ 71505 Dir. asuntos previsionales, 71511 primas históricas.

## 8 · TESORERÍA — falta reimpresión y procesos
- 🟢 **82005 Retención de primas**, **82010 Cobro de licitaciones**, **82050 Carga
  OP a resolución**, **82055 Pagos subsidios jubilados**, **82520 Anula pagos**.
- 🟠 **82515 Generación diskette de acreditaciones** (layout banco).
- **830 REPORTES**: ✅ **Informe de OP (generador)** (`/tesoreria/informe`) cubre
  8301505/8301510 (filtros estado/tipo/beneficiario/fechas + Excel). Siguen ⏳: 🟢
  83005 Liquidaciones de créditos, 83010 Seguros pendientes, **83025 Reimpresión
  de recibos (×8)**, 83030 Sellados, 83040 Cheques emitidos. ⚪/🟠 83020
  Distribución de utilidades (sin datos).

## 9 · ADMINISTRACIÓN Y FINANZAS
- 🟢 **92005 Datos de cobranzas (ingresos)**, **92010 Datos de pagos (egresos)** ·
  ⚪ 90505/92015 modelos/disposiciones.

## X · GENERAL
- 🟢 **X0550 Maestro de Agentes Públicos** (dato), **X1505 Consulta Maestro DIO**,
  **X1510 Consulta padrón conformado**, **X3010 Auditoría por máquina**, **X3015
  Transacciones vencidas** (auditoría ya cargada).
- ⚪ X0515 Feriados (no está el DBF), X0535 Admin opciones de menú, X2010 Inventario
  informática, X2505 Actualiza organismos.

---

## Lectura honesta

- El **núcleo transaccional y los maestros** están; lo que falta en volumen son
  **reportes/listados** (Créditos 330, Caja 230, Tesorería 830) y **procesos**
  (recálculos, generación de planes, cancelaciones por banco).
- **Construible ya (🟢)**: del orden de **50–60 ventanas** con dato del backup —
  sobre todo informes de Créditos, reportes de Caja/Tesorería, operatoria de Seguros.
- **Bloqueado (🟠)**: imports AFIP, previsional AGAP y layouts de banco.
- Muchos **330/230/830** comparten estructura → conviene un **motor de informes
  parametrizable** (una pantalla que arma listados por filtros) en vez de 50 pantallas.

### Próximo lote sugerido (🟢, alto uso)
1. **Seguros**: Maestro de Titulares (122k) — *en curso*; Cobranza de seguros; Deuda por organismo.
2. **Créditos — Informes varios (330/33085)**: estado, saldos, por depto, cancelados,
   mora, por caja — con un **generador de informes** común (backend + una pantalla).
3. **Caja/Tesorería**: reimpresión de recibos (visor único por tipo) y cheques emitidos.
4. **General**: Maestro de Agentes Públicos, consultas de padrón, auditoría por máquina.
