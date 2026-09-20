# Cobertura de migración — CCyPP
### Alcance real vs. construido en el sistema nuevo

> Basado en el inventario funcional extraído de los 377 formularios VFP
> (títulos reales) + 479 reportes. Detalle pantalla por pantalla en
> [inventario_funcional.md](inventario_funcional.md).

---

## 1. Alcance real del sistema (medido, no estimado)

> Estado actualizado (2026-08-04). Detalle por pantalla en `analisis-brechas.md`;
> foto consolidada por módulo real en `checkpoint-menu.md`.

| Módulo | Pantallas | ✅ | Estado en app nueva |
|---|---:|---:|---|
| **Créditos** | 145 | 37 | 🟡 El más avanzado — transaccional + consultas + reportería |
| **Contabilidad** (asientos, IVA) | 11 | 11 | 🟢 Completo + balance de sumas y saldos (mejora) |
| **Tesorería / Egresos** (OP, chequeras, pagos) | 32 | 10 | 🟡 OP/Reporte/Chequeras; falta diskette acreditaciones (🟠) |
| **Utilidades / Tablas** (ABMs) | 28 | 10 | 🟡 Líneas, organismos, compañías, parámetros, oficinas, perfiles, proveedores |
| **Seguros** | 18 | 12 | 🟢 Muy avanzado; falta control previsional AGAP (🟠) |
| **Caja** (operación) | 17 | 6 | 🟢 Núcleo hecho (cobranza/control/cierre) |
| **Caja — listados/reimpresiones** | 14 | 3 | 🟡 Parcial |
| **Despacho / Notas y Pases** (Mesa) | 13 | 8 | 🟢 Trámites + pases + ingresados (82k/428k reales) |
| **Despacho / Resoluciones y Disposiciones** | 5 | 2 | 🟡 Resoluciones (41k) + expedientes |
| **Juegos / Quiniela** | 32 | 10 | 🟡 Maestro/sorteos/liquidaciones/ingresos; import AFIP (🟠) |
| **Mesa de entradas / Turnos** | 3 | 0 | 🟢 Turnos operativos (parte del módulo Mesa) |
| **Sistema / Login** | 2 | 0 | 🟢 Login por perfil hecho |
| **Otros** (contab. varios, anexos, utilidades) | 57 | 2 | 🔴 Mayormente pendiente (variantes/pickers) |
| **TOTAL formularios** | **377** | **111** | **29% construido** |
| **TOTAL reportes (.frx)** | **479** | 🟡 recibo/cierre/IVA/libro-diario/cartera PDF + padrón/listado-créditos/pagos-caja/turnos Excel |

---

## 2. Qué está construido hoy (vertical transaccional)

| Funcionalidad | Pantalla VFP equivalente | Estado |
|---|---|---|
| Login por perfil | `login` | ✅ |
| Alta/consulta de clientes | `frm320…cliente` | ✅ básico |
| Simulación de crédito | F11 – Simulación | ✅ (validado c/datos reales) |
| Alta de solicitud + margen/cartera | `frm320100000solcre` (Administración de Créditos) | ✅ |
| Otorgamiento + plan de cuotas | `calcpres`/`det_cuota` | ✅ (validado al centavo) |
| Cobranza + mora + recibo | `frm225050000aplicativodeCaja`, `frm225150001pagcsj` | ✅ |
| Cierre de caja | `frm225350000cierrec` | ✅ básico |
| Asientos automáticos + libro diario | `cb-crasientootorga`, `cb-crasientodevenga` | ✅ |
| Póliza + liquidación de seguros | `frm720…`, `frm730100000…primas` | ✅ básico |
| Recibo en PDF | `rpt225050000recibo` | ✅ |

**Cobertura estimada: ~10% de las pantallas, pero es el ~núcleo transaccional
que concentra la operación diaria.** El resto son consultas, listados,
configuración y módulos administrativos.

---

## 3. Hallazgos estratégicos (por qué valía hacer el inventario)

1. **Mi mapeo previo por prefijo tenía errores.** El 8xx **no es "Juegos" sino
   Tesorería/Egresos** (órdenes de pago, chequeras, pagos de seguros,
   licitaciones y compras). Un módulo entero de 32 pantallas que no teníamos en
   el radar.
2. **No existe un módulo "Juegos" de ABM propio.** La quiniela/lotería aparece
   **embebida en Caja** (lee diskettes de quiniela, recibos a agencias
   ganadoras, agencias del interior). Es cobranza de agencias, no un módulo aparte.
3. **Fuerte presencia de variantes/duplicados.** Ej.: `aplicaj`,
   `aplicaj-a medias`, `aplicaj_s_interes`, `aplicativodeCaja` son **4 variantes
   del mismo "Aplicativo de Caja"**. Igual en reportes (`recibo-a`, `recibo-b`,
   `recibo-a-sn`…). El alcance *efectivo* es bastante menor que 377/479.
4. **Créditos concentra 145 pantallas**, pero la mayoría son **consultas e
   informes** (situación de cliente, margen, turnos, jubilados, envíos,
   estadísticas), no lógica transaccional nueva. Se migran rápido una vez que el
   modelo de datos está (ya lo está).
5. **Seguros es más amplio de lo esperado**: Renta Vitalicia Héroes de Malvinas,
   Excombatientes, Subsidio de Protección a la Familia, Control Previsional
   (AGAP) — son regímenes especiales, no solo el seguro de vida sobre el crédito.
6. **Integración provincial**: `frm725050000importardatosdecontrolprevisional`
   confirma la importación desde el sistema de RRHH/previsional provincial.

---

## 4. Recomendación de priorización (backlog)

Orden sugerido por valor operativo y dependencias, ahora **con fundamento**:

1. **Completar Créditos** (consultas e informes clave) — barato sobre el modelo ya hecho.
2. **Tesorería / Egresos** (32 pantallas) — es el otro pilar financiero, hoy ausente.
3. **Reportería** priorizada: recibos (varios), pendientes, cierre, IVA por período,
   libro diario/mayor. Muchos son variantes → consolidar.
4. **Utilidades / Tablas** (ABMs de parámetros, líneas, requisitos, organismos) —
   habilitan la autogestión del sistema.
5. **Despacho** (resoluciones/disposiciones/pases) y **Mesa de entradas** (turnos).
6. **Seguros — regímenes especiales** (Malvinas, subsidios, previsional).

> Nota (resuelto): el árbol de menú definitivo ya se extrajo de `symdeperf`
> (perfil ADMG) → ver [menu-real.md](menu-real.md). El menú del sistema nuevo se
> reconstruyó pantalla por pantalla contra esa fuente (ver H-018).

---

## 5. Mejoras de arquitectura y roadmap (post-inventario)

> Decisiones tomadas sobre la marcha que elevan la calidad de la migración más
> allá del "1 pantalla Fox = 1 pantalla nueva". Se registran como mejoras del plan.

### 5.1. Estándares transversales (aplicar a toda pantalla nueva)
- **Paginación + orden del lado del servidor** en toda lista grande: helper
  `core/pagination.paginar()` + schema genérico `Pagina[T]` (`{total,limit,
  offset,items}`) + componente `DataTable` (orden por columna + Anterior/
  Siguiente). Ya aplicado a clientes (78k), resoluciones (41k), liquidaciones de
  juegos (60k), auditoría (50k) y OP (3k). **Regla:** ninguna lista devuelve
  todo el set sin paginar.
- **Menú granular = 1 opción por pantalla/función**, ordenado contra
  `menu-real.md`. Nada de agrupar varias funciones bajo un link (ver H-018).
- **Cada pantalla nueva entra con test** (pytest) y, si revela algo del dato
  real, con su **hallazgo** en `hallazgos.md`.

### 5.2. Consolidación de pickers y variantes (no migrar 1:1)
De las ~275 pantallas pendientes, una porción grande **no debe migrarse como
pantalla independiente**:
- **Pickers / diálogos de búsqueda embebidos** (`frm_bus_dio`, `frm_bus_org`,
  `frm_bus_par`, `frm_bus_linea`, `frmlooksol`, `frm_vergarante`…): se resuelven
  como **componentes de selección reutilizables** dentro del flujo que los usa
  (ej. autocompletar de cliente en la solicitud), no como rutas del menú.
- **Variantes casi idénticas** (`…clienteagap`, `…clientesadop`,
  `…clientesproductivos`, `…garante2/3`, `aplicaj*`, `recibo-a/b/sn`): una sola
  pantalla parametrizada por línea/tipo/segmento, no N pantallas.
- **Reimpresiones** (`reimp*`): un único visor de comprobantes con filtro por
  tipo (crédito/seguro/premio/varios), no una pantalla por tipo.
- **Pantallas "OLD"/duplicadas** (`…OLD`, `loginold`, `reimpacred-old`): se
  descartan; se deja registro en el análisis de brechas.

> Efecto: el alcance *efectivo* es bastante menor que 377. La métrica de
> cobertura se mantiene honesta (se cuenta la pantalla Fox como cubierta cuando
> su función vive en el sistema nuevo, aunque sea vía componente/variante).

### 5.3. Backlog de funciones distintas con dato real (orden sugerido)
Priorizar lo que agrega función nueva y se puede respaldar con el backup:
1. **Juegos**: Maestro de Juegos, Premios por agencia, control de sorteos.
2. **Créditos**: historial de créditos por cliente, determinación de cuota,
   informe de cobros.
3. **Seguros**: informe de seguros de vida adicional, agentes sin seguro
   adicional, control previsional (import AGAP).
4. **Tesorería**: distribución de utilidades, retenciones/sellados, generación
   de acreditaciones (diskette → archivo).
5. **Reportería a PDF/Excel** de las consultas ya construidas (recibos varios,
   informes de seguros, ingresos brutos). **Patrón para exports grandes** (>10k
   filas): openpyxl en modo `write_only=True` + `select` de columnas puntuales
   (no objetos ORM completos). Bajó el export de 77k pagos de 52s a ~9s. Los
   endpoints de export pasan `cap` alto para saltear el tope de paginación.
6. **Anexos de resoluciones** (RTF/Word) y modelos parametrizables.
7. **Reportes contables modernos que el legado no tenía** (aportan valor, no son
   1:1): **Balance de sumas y saldos** (hecho, `/contabilidad/balance` + PDF, con
   verificación de cuadre), y a futuro libro mayor por cuenta.

### 5.4. Mejoras técnicas pendientes (deuda)
- **Backend en Docker sin `--reload`** (ver H-018b): agregar un override de
  compose para desarrollo, o script de reinicio, para no perder cambios de API.
- **Migrar claves reales** de forma segura (hoy los 188 usuarios tienen clave
  temporal `cambiar123`, ver H-016) o forzar cambio en primer login.
- **Índices** en columnas de orden/paginado de las tablas grandes (fecha,
  beneficiario) al pasar a producción.
