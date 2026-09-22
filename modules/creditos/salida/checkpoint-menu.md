# Checkpoint — Menú real (symdeperf) vs. sistema nuevo

> Recorrido del menú real (perfil ADMG, ver [menu-real.md](menu-real.md)) módulo por
> módulo, con el estado en la app nueva y la clasificación de los huecos.
> Fecha: 2026-08-04. Cruzar con [analisis-brechas.md](analisis-brechas.md) (conteo
> por inventario) y [estado-migracion.md](estado-migracion.md).

## Resumen

- **App nueva: 53 pantallas en producción** (9 módulos), sobre PostgreSQL con el
  backup real cargado. 124 tests verdes. Incluye **generadores de informes**
  parametrizables (Créditos y OP) que cubren decenas de reportes del menú real, y el
  **Anexo de Resolución reconstruido del fuente VFP** (78.443 solicitudes migradas).
- ⚠️ **Revisión honesta**: aún faltan muchas ventanas operativas del menú real
  (reportes de Créditos/Caja/Tesorería, procesos). Desglose y prioridades en
  [faltantes-menu.md](faltantes-menu.md).
- **Cobertura de formularios VFP: 109/377 (29%)** construido + 4 variantes
  consolidadas (el alcance *efectivo* es menor que 377 por variantes/pickers).
- **Reportería**: 4 Excel (padrón, listado créditos, pagos en caja, turnos) + 6
  PDF (recibo, cierre, IVA, libro diario, cartera, balance).

### Clasificación de los huecos pendientes
- **🟢 Construible ya** — hay datos o modelo; es sumar pantalla/endpoint.
- **🟠 Bloqueado por insumo externo** — necesita un archivo de intercambio que
  **no está en el backup**: imports AFIP/previsional (AGAP), generación de
  diskettes/acreditaciones bancarias, layouts de bancos.
- **🔵 Variante/picker** — se consolida en una pantalla ya hecha (mejora 5.2), no
  se migra 1:1.
- **⚪ Nicho/reporte menor** — bajo uso; reportes muy específicos.

---

## 1 · DESPACHO — completo (salvo editor de modelos)
- ✅ **Modelos de resoluciones** (`/despacho/modelos`) — 338 reales (catálogo).
- ✅ **Resoluciones y disposiciones** (`/despacho/resoluciones`) — 41.269 reales, +Word.
- ✅ **Anexo de resolución** (`/despacho/anexos`) — asignación de lote real por tipo
  (H-026), reimpresión y Excel. **78.443 solicitudes migradas**.
- ✅ **Expedientes y pases** (`/despacho/expedientes`).
- 🟢 Editor/creación de modelos (hoy el catálogo es de solo lectura).

## 2 · CAJA — núcleo hecho
- ✅ **Cobranza** (`/caja/cobranza`) con mora/recibo · ✅ **Control de caja** · Cierre (en Contabilidad).
- 🔵 Variantes del aplicativo de caja (`aplicaj*`) y recibos (`recibo-*`) → consolidadas.
- 🟢 Reimpresiones (histórico) e informes de caja históricos.
- Nota: buena parte del "Caja" del inventario era **Juegos/Quiniela** (ver H-014), ya cubierto.

## 3 · CRÉDITOS — el más avanzado
- ✅ Solicitudes, Simulador, Situación del cliente, Estadísticas de cartera,
  **Créditos por cartera**, **Turnos otorgados**, Listado (+Excel), Cuotas en mora,
  **Sin débito** (+ filtro Línea 25), **Pagos en caja** (+Excel), Pendientes,
  Envíos (padrón +Excel), Jubilados/5094, Líneas de crédito.
- 🔵 Múltiples pantallas de **selección de solicitante/garante** (AGAP, SADOP,
  productivos, garante 2/3) → un selector parametrizado.
- 🟠 **Cancelaciones por banco** (Patagonia), cancelación por transferencias,
  generación de acreditaciones — necesitan layout del banco.
- ✅ **Cuenta corriente por crédito** (`/creditos/cuenta-corriente`) — 7.088
  movimientos reales, saldo corrido.
- 🟢 Reintegros, determinación de cuota, información de ubicación.

## 4 · JUEGOS/QUINIELA — parcial
- ✅ **Maestro de juegos**, **Control de sorteos**, **Agencias y liquidaciones**
  (cobro/revisión), **Ingresos por juego**.
- 🟠 **Importar/Exportar jugadas a Caja**, **Comisiones para AFIP** — insumos de
  intercambio (archivos diarios `IEJUE`/AFIP).
- 🟢 Premios/cupones (maepremios casi vacío hoy), boletas de vencimiento,
  ingresos brutos, fondo de garantía.

## 5 · MESA DE ENTRADAS — hecho
- ✅ **Turnos**, ✅ **Consulta de trámites** (82.218 reales), ✅ **Trámites ingresados**.
- ✅ Historial de **pases** por trámite (`pases.dbf`, **428.051** reales, fechas
  año 1601 saneadas) — drill-down "ver pases" en la consulta.
- 🟢 ABM de carga de trámite / carga de pase (data-entry).

## 6 · CONTABILIDAD — completo + mejora
- ✅ Libro diario (+PDF), IVA por período (+PDF), OP devengadas, IVA egresos,
  revisión bajas, **Balance de sumas y saldos** (mejora, +PDF), Cierre de caja.
- Asientos de otorgamiento/devengamiento se generan automáticamente.

## 7 · SEGUROS — muy avanzado
- ✅ Pólizas y liquidación, Regímenes especiales (Malvinas/Excombatientes/Subsidio),
  **Seguro de vida adicional** (32.356 agentes), Informes (cobrados/primas/pagos).
- 🟠 **Control previsional AGAP / import** (frm725050/725070) — necesita el archivo
  de control previsional provincial (no está en el backup).
- 🟢 Expedientes de seguros, informe de seguros a Tesorería.

## 8 · TESORERÍA — parcial
- ✅ **Órdenes de pago** (paginado), **Reporte de OP**, **Chequeras**, revisión de
  pendientes/incompletos, pagos con cheque/chequera.
- 🟠 **Generación de diskette de acreditaciones**, anulación/recupero de pagos.
- 🟢 Reimpresiones de recibos (créditos/seguros/premios/varios), retención de
  primas, pagos de subsidios, distribución de utilidades (sin datos → 🟠).

## 9 · ADMINISTRACIÓN Y FINANZAS — parcial
- ✅ Administración de **Proveedores** (ABM, `/general/proveedores`, 1 real + alta).
- 🟢 Transacciones de ingresos/egresos de administración.

## X · GENERAL / Tablas y maestros — hecho el núcleo
- ✅ Clientes/Agentes (78.055, paginado), Usuarios, Organismos, **Oficinas** (151),
  Compañías de seguros, Parámetros, Auditoría (50.011, paginado).
- ✅ **Perfiles** (`maeperfil`, 19 reales, solo lectura). 🟢 Feriados, Maestro de agentes.

## Z · SALIR — n/a

---

## Prioridades sugeridas para la próxima etapa

1. **🟢 Construible de alto uso**: Cuenta corriente por crédito (pantalla),
   historial de pases de trámite (ETL `pases` saneado), ABM de Proveedores.
2. **🟢 Cerrar Tablas/Maestros (X)**: Perfiles, Feriados, Oficinas — habilitan
   autogestión.
3. **🟠 Definir con el organismo los insumos externos** (AFIP, control previsional
   AGAP, layouts de banco para acreditaciones/cancelaciones): sin esos archivos no
   se pueden construir de forma fiel; conviene relevar formatos.
4. **🔵 Consolidar selectores** de solicitante/garante en Créditos (una pantalla
   parametrizada) para "tachar" ~15 variantes de un saque.
