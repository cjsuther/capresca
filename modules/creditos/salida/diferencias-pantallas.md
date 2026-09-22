# Diferencias: pantallas construidas vs fuente VFP (lectura H-026)

> Lectura de las pantallas ya construidas contra su formulario VFP real
> (`.scx/.sct`, legible según H-026). Objetivo: detectar dónde el comportamiento
> reconstruido **por inferencia** difiere del real. Severidades:
> 🔴 lógica/negocio · 🟠 alcance/función · 🟡 UX/campos · 🟢 fiel (sin diferencias).
>
> La mayoría de las pantallas se construyeron **antes** de descubrir que el fuente
> era legible, o sea por inferencia del esquema DBF. Esta lectura las corrige.

## Tabla-resumen (lectura completa de los 9 módulos)

| Sev | Pantalla | Diferencia con el fuente VFP | Estado |
|---|---|---|---|
| ✅ | Cobro en caja | Faltaba el **piso mínimo de interés** (`vl_minint`) | Corregido + test |
| ✅ | Aplicativo de Caja (22505) | **Agencias de quiniela** (bonos/pesos/vuelto/premios) — construido con dato real | Hecho (60k liq + 31,7k recibos) |
| ✅ | Cobranza créditos (22515) | **Cola por persona** + buscar por nombre/DNI/CUIL, cobro multi-crédito en un recibo | Hecho (falta seg./juegos en la cola) |
| 🟠 | Cobro de seguros por caja | Cola de caja para seguros (se integra a la anterior) | Pendiente |
| ✅ | Orden de Pago (805100) | El real es **cupo autorizado** (importe/usado/saldo/vig./resol.) — construido `AutorizacionOP` (35.040 reales) | Hecho (H-027 resuelto) |
| 🟠 | Solicitud créditos (32010) | El real es **grilla de administración** + asistente por tipo | Alta simple hoy |
| 🟡 | Situación del cliente | El real es **por cuota** con % punit. + panel de situación legal | Resumen por crédito hoy |
| 🟡 | Cuenta corriente | Faltan **T.N.A. y días de atraso** por cuota (resarcitorio=0) | Menor |
| ✅ | Control de caja (22530) | Ahora incluye los **cobros de quiniela** (`cajapagos`) por cajero | Hecho |
| ✅ | Deuda de agencia (22555) | Liquidaciones impagas por agencia/rango de vto. con días de atraso | Hecho (dato real) |
| ✅ | Cierre de caja (22535) | Cierre por moneda (pesos/bonos) sumando créditos/seguros + quiniela | Hecho (dato real) |
| 🟢 | Resto (maestros/consultas/informes) | Fieles o de bajo riesgo | OK |

---

## 2 · CAJA — el módulo con las diferencias más grandes

### ✅ El "aplicativo de Caja" real es de **agencias de quiniela** — CONSTRUIDO
- **Form:** `frm225050000aplicaj.scx` (menú 22505).
- **Real:** cobra **liquidaciones de agencias de quiniela** — *Código de Agencia,
  Total Bonos, Total Pesos, Vuelto B$/$, Total Gral.*; grid `cajaliq`; **dos
  monedas** (bonos/pesos) y **vuelto = adeudado − cobrado** por moneda (verde ≥0 /
  rojo). Command2 graba `cajapagos` (bonos, pesos, cobrado_*, vuelto_*, premios_*,
  cajero) y marca cada `cajaliq` pagada con el `no_recibo`.
- **App nueva (HECHO):** pantalla `AplicativoQuiniela.tsx` (`/caja/quiniela`):
  código de agencia → deuda pendiente separada por moneda → formas de pago
  (bonos/pesos) → vuelto calculado con el mismo color-code → confirmar. Modelos
  `LiquidacionAgencia` (extendido: moneda/cod_agencia/total_gral/…) y nuevo
  `CajaPagoAgencia` (cajapagos). Servicios `deuda_agencia`/`cobrar_agencia`/
  `anular_pago_agencia`; endpoints `/juegos/agencias/{cod}/deuda`,
  `/juegos/agencias/cobrar`, `.../pagos/{id}/anular`. Test
  `test_aplicativo_caja_quiniela_cobro_agencia`. **Dato real: 60.000
  liquidaciones + 31.714 recibos** (verificado: agencia 3259, 7 liq., $622.625,80).
- **Nota:** la **entrada** de nuevas liquidaciones venía del diskette/pendrive
  (22005/22010, binario externo); el histórico ya está en `cajaliq.DBF`, así que la
  caja opera sobre dato real. Cargar nuevas requeriría un import manual/CSV.
- **Corrección (H-029):** la cobranza de agencia **salda el total** — no admite pago
  parcial (verificado: 31.529/31.530 recibos reales exactos, 0 parciales). Si lo
  entregado no cubre la deuda de cada moneda se **rechaza (409)** sin marcar nada; el
  excedente queda como **vuelto**. Antes un parcial marcaba toda la deuda pagada (bug
  detectado por el usuario probando la agencia 3259).

### ✅ La cobranza de créditos en caja es una **cola** por persona — CONSTRUIDA (créditos)
- **Form:** `frm225150000cresegu1.scx` (menú **22515** "CRÉDITOS, SEGUROS, ETC.").
  Título real: *"Cobranza de Créditos, Seguros y Extraordinarios"*.
- **Real:** opera sobre un cursor/cola `cajacreseg` con columnas *Origen, F.Alta,
  DNI, Apellido y Nombres, N°Crédito, N°Cta, Importe, Interés, IVA, Total* y un
  buscador por **Nombre**. El cajero cobra **todo lo encolado para una persona**
  (varios créditos + seguros + juegos extraordinarios juntos), no un crédito por
  vez. La cola se arma desde otras pantallas (ej. selección de solicitante).
- **App nueva (HECHO):** `Cobranza.tsx` ahora tiene **dos modos**: *Por crédito*
  (el anterior) y *Cola por persona* — busca por CUIL/DNI/nombre, muestra la cola de
  cuotas pendientes de **todos** los créditos de la persona (Origen, DNI, Nombre,
  N°Créd., N°Cta, Importe, Interés, IVA, Total) y cobra la selección **multi-crédito
  en un solo recibo** (`/caja/cola`, `/caja/cola/cobrar`). Servicios
  `cola_de_caja`/`cobrar_cola` + `_imputar_credito` reutilizado; `anular_recibo`
  corregido para revertir varios créditos. Test `test_cola_de_caja_por_persona_
  multicredito`. Verificado con dato real (PEREZ: 50 clientes, 33 cuotas, $6,87M).
- **Pendiente:** sumar a la cola los ítems de **seguros** (`cobrasegu`) y **juegos
  extraordinarios** para completar "Créditos, Seguros y Extraordinarios".

### ✅ Fórmula de mora: **piso mínimo de interés** (`vl_minint`) — RESUELTO
- **Fuente (cresegu1, PROCEDURE del grid):**
  ```
  vl_interes = ROUND( TOTAL * vl_dias * vl_porint * 0.01, 2 )
  IF vl_interes < vl_minint AND vl_interes > 0
      vl_interes = vl_minint          && piso mínimo
  vl_iva  = ROUND( vl_interes * vl_poriva * 0.01, 2 )
  total   = TOTAL + vl_interes + vl_iva
  ```
- **App nueva (`domain/mora.py`):** calcula `int = base × tasa × días / 100` e
  `iva = int × iva%` — **estructura correcta**, pero **no aplica el piso `vl_minint`**.
- **Base del interés:** el fuente usa `TOTAL` (importe de línea, incluye
  seguro/adm); mi base es `capital + interes + iva_interes − total_pagado`
  (excluye gastos de seguro/adm). Revisar si el punitorio real corre también
  sobre seguro/adm.
- **IVA:** `vl_poriva = c_trae_valor_param(1,4,'nValor1')` — la alícuota sale de
  la tabla de parámetros (grupo 1, ítem 4). Mi código toma `linea.iva`. Verificar
  que coincidan.
- **Hecho:** se agregó el piso `minimo_interes` a `calcular_mora`
  (`domain/mora.py`, default 0 = sin cambio en el histórico) con test
  `test_piso_minimo_interes_como_cresegu1`. **Pendiente**: alimentar el mínimo y la
  alícuota de IVA desde la tabla de parámetros (grupo 1, ítems 4) y revisar si la
  base del punitorio debe incluir seguro/adm (`TOTAL` de línea) como en cresegu1.

### Otras pantallas de Caja
- **Control de caja** (`ControlCaja.tsx`) ↔ `frm225300000ctrlcaj.scx` — pendiente
  de lectura fina.
- **Cierre de caja** (`Cierre.tsx` en Contabilidad) ↔ `frm225350000cierrec.scx`.
- ✅ **Anula pagos/cobros** (22525) ↔ `frm225250000anupago.scx` — **ya construido**
  (`/caja/recibos/{id}/anular`, revierte cuotas y reactiva crédito cancelado;
  `test_caja_anulacion`).

---

## 3 · CRÉDITOS

### 🟠 "Solicitud" (32010) real es una **grilla de administración**, no un alta simple
- **Form:** `frm320100000solcre.scx` — título *"Administración de Créditos"*.
- **Real:** grilla de solicitudes con **leyenda de estados** (Activo / Baja-Anulada
  / Cancelado / Liquidado / Pagado / Otros), vínculo a **Nota** (Nro/Fecha — trámite
  de Mesa) y **N° Solicitud**, botón *Disposición*, checkbox *Al Gasista*, y columnas
  solicitante **+ garante** (CUIL Gar., Nombres Garante, N° Agente, Organismo),
  Pzo.Total, Tasa, DBA, F.Pago, N° Recibo, Letra. El alta es un **asistente**
  (línea → cliente → garante → crédito → prenda/hipoteca) con **variantes por tipo**
  (`...clienteagap/clientesadop/clientesproductivos/clienteg` gas).
- **App nueva:** `Solicitudes.tsx` es un formulario único sin la grilla de gestión
  por estado, sin garante ni vínculo a Nota, y sin las variantes por tipo.
- **Acción:** ampliar a grilla de administración con filtro por estado y datos de
  garante/nota; el asistente por tipo es un desarrollo mayor (evaluar prioridad).

### 🟡 Situación del cliente — falta el detalle por cuota y el panel de situación
- **Form:** `frm325800000situacion_cr.scx`.
- **Real:** grilla **por cuota** con *N° Cta, Fecha Vto, Total Cta, % Int.Punit.,
  Int.Punit., IVA s/Int.P., Total Vdo, Estado, N°Recibo, Vía Pago, Usuario, AqC* y
  un **panel "Situación"** (Fecha, Oficina, Usuario, N°Resol., Fecha Resol.,
  Observaciones) = situación legal/mora del crédito.
- **App nueva:** `SituacionCliente.tsx` es un **resumen por crédito** (Capital,
  Saldo, Cuotas pend., Próx.vto, Estado). Falta el detalle por cuota con % punitorio
  y el panel de situación/resolución.
- **Acción:** agregar drill-down por cuota (ya está el dato de mora) y, si existe,
  el panel de situación legal.

### 🟡 Cuenta corriente — faltan Resarcitorio, T.N.A. y días de atraso por cuota
- **Form:** `frm320160001ctaactual.scx` ("Cuota actualizada").
- **Real (por cuota):** Capital, Interés, IVA, Total, Fecha Pago, **Int. Punitorio,
  Int. Resarcitorio, IVA s/Int, Total Vencido, Pagado, Días de atraso, T.N.A.**
- **App nueva:** `CuentaCorriente.tsx` tiene Capital/Interés/IVA/Punit./Saldo, pero
  **sin Resarcitorio** (=0 en producción, H), **sin T.N.A. ni días de atraso**.
- **Acción:** menor — sumar columnas TNA/días; resarcitorio queda en 0.

### 🟢 Simulador — sin equivalente VFP (mejora propia)
`Simulador.tsx` no mapea a un `.scx`; es una ayuda de simulación de la app nueva.
No hay diferencia que corregir.

---

## 7 · SEGUROS

### 🟠 Cobro de seguros por caja (720050) — no construido como pantalla operativa
- **Form:** `frm720050000cobrasegu.scx` ("Cobro de Seguros por Caja").
- **Real:** grid *N°Liquida, N°Docum, Nombre/Razón Social, Fecha, Importe, Tipo,
  Intereses, IVA, Total_gral* + detalle por cuota (Tasa, Monto Cuota, Interés
  s/Cuota, IVA s/Interés, Mes, Año). Es el equivalente de la cola de caja para
  **seguros** (se suma a la cola `cresegu` junto con créditos y juegos).
- **App nueva:** Seguros tiene **informes** (cobrados, primas, deuda), no la
  pantalla de **cobro por caja**. Consistente con el hallazgo de Caja (la cola
  combina créditos + seguros + juegos).
- **Acción:** entra dentro del rediseño de la cola de caja (ver Caja 22515).

### 🟢 Titulares / Informes de seguros — fieles
`Titulares.tsx` (122k reales) ↔ `frm705050000maetit`; los informes ↔ familia
`frm730xxx`. Sin diferencias de lógica detectadas (son maestro + consultas).

---

## 8 · TESORERÍA

### ✅ La Orden de Pago real es una **autorización con techo** — CONSTRUIDA (H-027 resuelto)
- **Form:** `frm805100000altaop.scx` ("Administración del Maestro de órdenes de Pago").
- **Real:** una OP es un **cupo autorizado**: *N°OP, Fecha, Vig.Máx, Importe OP,
  **Imp. Utilizado, Saldo**, Sistema, Habilitada, Cancelada, N°Res/Fecha Res (×2),
  Importe Res*. Los **pagos** (`frm820100000pagostesoreria`/`recibos`) se libran
  **contra** esa OP consumiendo su saldo; los **cheques** se cargan aparte
  (`cargachetra`).
- **App nueva:** `OrdenesPago.tsx` modela la OP como **pago directo a un
  beneficiario con cheque** (numero, beneficiario, importe, estado P/G/A, cheque).
  Conflaciona la **autorización** (OP maestro) con el **pago** (recibo de tesorería).
- **Acción:** separar conceptos — OP como cupo (importe/utilizado/saldo/vigencia/
  resolución) y pagos que la consumen; o documentar la simplificación asumida.

### 🟢 Chequeras / Reporte OP — razonables
`Chequeras.tsx` ↔ `frm805050000altachequeras`; `ReporteOP`/`InformeOP` son informes.
Sin diferencias de negocio detectadas más allá de la definición de OP de arriba.

---

## 6 · CONTABILIDAD
### 🟡 Cierre de caja (225350) es "de Supervisor"
- **Form:** `frm225350000cierrec.scx` ("Cierre de Caja (Supervisor)") — emisión del
  cierre por fecha, rol supervisor. `Cierre.tsx` cubre el cierre; verificar que
  totalice por cajero/vía y respete el rol supervisor.
- **Libro diario / IVA por período**: informes contables portados de `cb-*`;
  sin diferencias de negocio detectadas en esta lectura (revisar fórmulas de IVA
  contra `cb-iva-a-pagar-periodo` en una pasada futura si hace falta).

---

## 3 · CRÉDITOS — revisión completa (metodología, en curso)

Revisión de lo construido vs el menú real (145 opciones). El **motor financiero**
(simular → otorgar) y la **mora** están validados contra dato real (863 casos de mora;
las cuotas de créditos existentes **son** el dato real migrado, ver crédito 110142:
línea GAS tipo_calculo=2, amort = capital/plazo = 638,89 ✓).

**Construido y fiel (consultas/informes):** 31010 Líneas (listado) · 31505 Solicitudes ·
31515/5094 · 31525 Organismos · 31530 Envíos · 31535 Estadísticas · 31537 Por cartera ·
31540/31565 Situación cliente · 3154505/10/15 Sin débito/Activas · 31555 Pagos en caja ·
31560 Turnos · + Listado, Cuotas en mora, Pendientes, Cuenta corriente, Informe generador.

**Diferencias detectadas (a corregir):**
- ✅ **30510 Administración de Líneas**: **ya estaba el ABM completo** (backend
  `/admin/lineas` POST/PUT + frontend con alta/edición) — la revisión lo dio como
  "sólo listado" por error. **Enriquecido** con los campos que faltaban del form real:
  **plazo de gracia, paga interés en gracia, suma int.gracia a capital, admite previo
  pago, cta. contable**. Pendiente menor: bonificaciones por tramos de haberes.
  *(Lección: verificar contra el código antes de asumir un hueco.)*
- 🟠 **32010 Solicitud** (ya en H-027): el real es **grilla de administración** por
  estado + garante + vínculo a Nota, con **asistente por tipo** (AGAP/SADOP/productivos/
  gas). La app tiene alta simple.
- 🟡 **Situación / Cuenta corriente** (ya en H-027): sumar detalle por cuota (% punit.,
  TNA, días) y panel de situación.

**Inventario preciso (verificado contra el código, no asumido):**
- ✅ **305 ARCHIVOS — completo**: 30510 Líneas (ABM), 30515 Requisitos, 30525 Gasistas,
  30530 Cupo/montos por período (todos en `/admin/*`). Falta menor: 30540 genera cuotas
  plataforma.
- ✅ **315 CONSULTAS — casi completo**: situación, estadísticas, por cartera, sin débito,
  pagos en caja, turnos, envíos, jubilados, previo pago (consulta), cuenta corriente.
- **Core**: `simular` (motor 4 sistemas) + `solicitudes` (alta/otorgar = genera plan) +
  detalle de crédito — construido.

**Faltantes GENUINOS (verificados — no hay servicio), por prioridad:**
1. ✅ **32045 Cancelación de crédito** — **construido**: cancelación anticipada
   (`simular_cancelacion`/`cancelar_credito`): cuotas vencidas completas + mora, futuras
   sólo capital (condona interés no devengado); emite recibo, salda todo, estado C.
   Endpoints `/creditos/{id}/cancelacion` y `/creditos/{id}/cancelar`, pantalla
   `/creditos/cancelacion`. Verificado con crédito real 110573.
2. ✅ **32565 Baja de créditos** — **construido**: anulación administrativa con motivo
   obligatorio, rechaza créditos con pagos (→ cancelación), estado B. Endpoint
   `/creditos/{id}/baja`, pantalla `/creditos/baja`. Verificado con crédito real 110142.
3. ≈ **32015 Cancela cuotas** — cubierto por Cobranza "por crédito" (pago manual de
   cuotas con mora → recibo). No se duplica.
4. ✅ **32535 Recálculo de créditos** — **construido** (H-031, leyendo el código exacto):
   dos modos — *reprogramar vencimientos* (sólo `fecha_vto`, como el fuente activo) y
   *jubilatorio* (capital puro, 10% del haber). Vista previa obligatoria; no toca cuotas
   pagadas. **32537** (recalcula mora) **no aplica** — mora en vivo. Endpoints
   `/creditos/{id}/recalculo` (GET preview / POST aplicar), pantalla `/creditos/recalculo`.
5. ✅ **32065/67/68 Turnos** — **construido**: generar turnos del mes (distribución por
   día hábil, con preview), asignar al próximo libre (32067) y por N° excepcional (32068).
   Endpoints `/creditos/turnos/generar[/preview]` y `/creditos/turnos/asignar`, pantalla
   `/creditos/turnos-admin`.
6. **330 REPORTES**: solicitudes cargadas, reimpresión de liquidaciones, cobros del día,
   informe de deuda, control de créditos (≈ solapan con consultas existentes).

---

## 4 · JUEGOS · 5 · MESA · X · GENERAL — fieles / de bajo riesgo
- **Maestro de Juegos** (`MaestroJuegos.tsx`) ↔ `frm405100000maejuegos`: **fiel**
  (Código, Modalidad, Denominación, Com. Agencia, Com. SubAgencia).
- **Control de sorteos / Ingresos por juego**: consultas sobre dato real; sin
  diferencias de negocio.
- **Mesa (Trámites / Ingresados)**: ya reconstruidas con dato real (82k trámites,
  428k pases) — ver H-024.
- **General** (Usuarios, Organismos, Oficinas, Perfiles, Proveedores, Compañías,
  Parámetros, Auditoría): maestros/ABM; Oficinas/Perfiles/Proveedores se hicieron
  **desde el fuente** recientemente. Sin diferencias mayores.

---

## Resumen de la lectura
- **Fidelidad alta** en maestros, consultas e informes (la mayor parte de las 53).
- **Diferencias de negocio a resolver** concentradas en el eje **Caja ↔ cobro**:
  1. ✅ Piso mínimo de interés (`vl_minint`) — **corregido**.
  2. 🟠 Cola de caja por persona (créditos + seguros + juegos) con búsqueda por nombre.
  3. 🟠 Aplicativo de caja de **quiniela** (bonos/pesos/vuelto) — inexistente.
  4. 🟠 OP de Tesorería como **cupo autorizado** vs pago directo.
  5. 🟠 "Solicitud" de créditos como **grilla de administración** + asistente por tipo.
- **Ninguna** de estas invalida el dato migrado ni la equivalencia de mora
  (125 tests verdes). Son ampliaciones de alcance/fidelidad, priorizables.
