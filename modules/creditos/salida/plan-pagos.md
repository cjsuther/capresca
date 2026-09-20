# Paso 3 — Persistencia del plan de cuotas y situaciones de pago

> Relevamiento + decisión. Contexto: roadmap 1) Solicitudes ✓ · 2) originar/otorgar/desembolsar ✓ ·
> **3) persistencia del plan + situaciones de pago (este doc)** · 4) nueva Caja.

---

## 1. Estado actual (qué ya está persistido y cómo)

**El plan de cuotas YA se persiste completo** en `pp_cuota_contrato` (una fila por cuota):
`numero_cuota, fecha_vencimiento, saldo_inicial, capital, interes, cargos, impuestos, total, saldo_final,
estado (PENDIENTE/PAGADA), pagado, devengada`. Los **importes de cada cuota son inmutables**; lo que cambia
con el servicing es el **estado** de la cuota y el saldo del contrato.

**Servicing event-sourced** (`_recompute`): la verdad son las **actividades** (`pp_actividad`); el estado de
las cuotas y el saldo se **reproducen** desde el cronograma pristino aplicando las actividades no reversadas,
en orden de fecha valor. Por eso el **backdating** reordena y la **reversa** es sólo marcar REVERSADA + recomputar.

**Situaciones ya cubiertas hoy:**

| Situación | Estado |
|---|---|
| Pago de cuota completa | ✅ `PAYMENT` (paga la próxima pendiente, marca PAGADA, baja saldo) |
| Pago de cuota vencida con **mora** | ✅ punitorio + IVA + asiento 4.1.02 (H-086) |
| Cancelación total (**payoff**) | ✅ `PAYOFF` (salda todo, CERRADO) |
| **Reversa** de una actividad | ✅ marca REVERSADA + recomputa + contra-asiento |
| **Backdating** (fecha valor pasada) | ✅ (no futura, no anterior al desembolso) |
| Devengamiento de interés | ✅ `ACCRUAL` (asiento devengo, no duplica ingreso) |
| Repricing tasa variable | ✅ `REPRICING` |

**Stubs registrados pero SIN efecto en el cronograma** (se guardan como actividad, no cambian cuotas):
`PARTIAL_PREPAYMENT`, `PAYMENT_HOLIDAY`, `RENEGOTIATION`, `RATE_CHANGE`.

---

## 2. Mapa de situaciones de pago futuras (gap analysis)

| # | Situación | Hoy | Qué falta | Prioridad |
|---|---|---|---|---|
| 1 | Pago total de cuota | ✅ | — | — |
| 2 | Pago de cuota con mora | ✅ | — | — |
| 3 | Cancelación total (payoff) | ✅ | — | — |
| 4 | Reversa / backdating | ✅ | — | — |
| 5 | **Pago parcial de una cuota** | ❌ | acumular en `pagado`; PAGADA sólo al completar; saldo baja proporcional | **Alta** |
| 6 | **Prepago parcial de capital** | ❌ stub | bajar capital y **recomponer** el tail: menor cuota **o** menor plazo (a elección) | **Alta** |
| 7 | Adelanto de N cuotas de una | parcial | pagar "hasta la cuota K" en un movimiento (hoy: N PAYMENT sueltos) | Media |
| 8 | **Diferimiento / payment holiday** | ❌ stub | correr vencimientos y/o capitalizar el interés del período diferido | Media |
| 9 | **Refinanciación / renegociación** | ❌ stub | nuevo cronograma sobre el saldo (nueva tasa/plazo), cierra el viejo | Media |
| 10 | **Quita / condonación** | ❌ | reducir capital sin ingreso de caja (asiento de pérdida) | Baja |
| 11 | Pago a cuenta / excedente | ❌ | el excedente queda a favor o se imputa a la próxima | Baja |
| 12 | Medios de pago / imputación | ❌ | lo resuelve la **nueva Caja** (paso 4) | (paso 4) |

---

## 3. Decisión de persistencia (recomendación)

**Mantener el modelo event-sourced** (actividades = fuente de verdad, cuotas recomputadas). Es limpio,
auditable y la reversa ya funciona. **No hay que "materializar" más de lo que hay** para los casos 1–4.

Para las situaciones que **alteran el cronograma** (5, 6, 8, 9), la extensión correcta dentro del mismo
modelo es que `_recompute` sepa **regenerar el tramo restante** de cuotas cuando encuentra una actividad que
lo altera, en vez de sólo marcar estados. Dos ajustes concretos:

- **Pago parcial (5):** `PAYMENT` acepta `importe`; se acumula en `pagado` de la cuota; la cuota pasa a
  PAGADA sólo cuando `pagado ≥ total`; el saldo de capital baja por la porción de capital efectivamente
  cubierta. (Hoy `PAYMENT` ignora el importe y paga la cuota entera.)
- **Prepago de capital (6) / refinanciación (9) / holiday (8):** la actividad guarda en `dato` los parámetros
  del recálculo (monto aplicado a capital, modo "baja cuota"/"baja plazo", nueva tasa/plazo…) y `_recompute`,
  al llegar a esa actividad, **reconstruye las cuotas siguientes** con el motor (`cronograma`) sobre el saldo
  vigente. Así se conserva la auditabilidad (todo deriva de las actividades) y la reversa sigue siendo
  "marcar + recomputar".

**Alternativa descartada:** persistir un cronograma nuevo por cada evento (materialización total). Rompe la
elegancia event-sourced, duplica datos y complica la reversa. No se recomienda.

**Regla de oro que se mantiene:** el motor `cronograma` sigue siendo la **única fuente de verdad** del cálculo
(la misma de preview/originación); los eventos sólo le dan nuevos inputs (saldo, tasa, plazo) al regenerar.

---

## 4. Orden de implementación propuesto (paso 3)

1. **Pago parcial de cuota** (5) — ✅ HECHO (H-090): `PAYMENT` con importe + acumulación en `_recompute`,
   asiento proporcional, reversa, UI. Tests + casos CV.
2. **Prepago parcial de capital** (6) — EN CURSO. Actividad `PARTIAL_PREPAYMENT` con `dato{importe, modo}`;
   `_recompute` regenera el tramo restante con el rate periódico congelado; asiento (capital); UI.
   Sub-decisión: modo **BAJA_PLAZO** (misma cuota, menos plazo) y **BAJA_CUOTA** (mismo plazo, menor cuota),
   elegido por el operador en cada movimiento.
3. **Adelanto de N cuotas** (7) — atajo sobre pago (pagar hasta cuota K).
4. **Payment holiday / diferimiento** (8) y **refinanciación** (9) — nuevo cronograma; requieren definición de
   negocio (¿capitaliza interés? ¿nueva tasa?) → los dejo para confirmar reglas antes de codear.
5. **Quita** (10) y **pago a cuenta** (11) — baja prioridad.

---

## 5. Conexión con la nueva Caja (paso 4)

La nueva Caja será la **UI de cobro** que orquesta estas situaciones: elige el contrato, muestra la próxima
cuota + mora al día, permite pago total/parcial/prepago, imputa el medio de pago y **registra la actividad**
(que ya asienta al Libro Diario). El servicing de este paso 3 deja todas las situaciones listas para que la
Caja sólo las invoque. La Caja NO recalcula nada: usa las actividades + `_recompute` existentes.

---

**Para confirmar antes de codear el paso 3:**
- Prepago (6): al aplicar capital extra, ¿el default es **bajar la cuota** (mismo plazo) o **bajar el plazo**
  (misma cuota)? ¿Lo elige el operador por movimiento?
- Payment holiday (8) y refinanciación (9): ¿las incluimos ahora o después de la Caja? (necesitan reglas de negocio).
