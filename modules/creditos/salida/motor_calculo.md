# Motor de cálculo de créditos — CCyPP
### Especificación extraída de `set_class.prg` (clase `set_capresca`)

> Ingeniería inversa de la lógica financiera. Base para portar a Python con
> pruebas de equivalencia. Métodos fuente: `det_cuota`, `calcpres`,
> `recalculo`, `paga_pp`, `cancelacre`, `margen`, `valor_hoy`.

---

## 1. Composición de una cuota

Cada cuota se descompone en 7 conceptos:

```
cuota_total = amortizacion            (capital)
            + interes
            + iva_interes
            + seguro
            + iva_seguro
            + gastos_adm
            + iva_gastos_adm
```

Reglas comunes:
- `iva_<concepto> = concepto * lniva * 0.01`  (lniva = alícuota IVA, p.ej. 21)
- Seguro y gastos administrativos se evalúan por fórmula parametrizada de la
  línea (`copeseg`, `copeadm` — expresiones almacenadas, evaluadas por cuota).
- Cada cuota se persiste en `mccalcre`/`maecuotas` con: `ncuota`, `fvto`
  (vencimiento), `sdocap` (saldo de capital), `ntna`, `ncapcta`, `nintcta`,
  `nivaint`, `ngsseg`, `nivagss`, `ngsadm`, `nivagsa`, `total`.
- Vencimiento de cada cuota: `fvto = GOMONTH(fvto_anterior, 1)` (mensual).
- Saldo: `saldo = saldo - amortizacion`.

## 1.bis Calibración contra datos reales (tmpdev.DBF)

Se validó el motor contra **cuotas reales de producción** (`prgs/tmpdev.DBF`,
2,65M registros hasta 2020). Hallazgos confirmados al centavo:

- **Tasa mensual = TNA × 30 / 365** (convención de tasa diaria, no TNA/12).
  Verificado: TNA/tasa = 12,1667 = 365/30 en todos los créditos muestreados.
- **Interés de cuota = saldo × tasa_mensual**; **IVA = interés × 21 %**.
- **Sistema francés CCyPP**: la cuota **constante** es
  `capital + interés + IVA-interés`, por lo que la anualidad usa la tasa
  **efectiva `r = tasa_mensual × (1 + IVA)`** (el IVA entra en la anualidad).
- El `TOTAL` de la tabla suma además **seguro (`ngseg`) y gastos (`ngadm`)**
  por cuota, ajenos a la anualidad.
- **Líneas de tasa ≈ 0** (p.ej. GAS): NO usan anualidad; amortizan **capital
  constante** (`capital / plazo`). Es un `tipo_calculo` distinto del francés.

> 5 créditos franceses reales reproducidos al centavo por el motor Python
> (`tests/test_equivalencia_real.py`). El `tipo_calculo` exacto de cada línea
> debe tomarse de `lineacred` cuando se disponga del backup.

## 2. Sistemas de amortización (`lineacred.tipo_calculo`)

| tipo_calculo | Sistema | Fórmula de interés por cuota |
|---|---|---|
| 1–4 | Variantes (francés / alemán / tasa directa) | `interes = capital * t1 / plazo` sobre saldo, amortización según sistema |
| 5 | **Cuota fija sin interés** (Res. 1903/2010) | `interes = 0`; `plazo = capital / cuota`; `amortizacion = cuota` |

Para el tipo 5: interés e IVA de interés = 0; sólo capital + seguro + gastos.

> El detalle fino de la amortización sistema francés/alemán está en el cuerpo de
> `det_cuota` (líneas ~2673–2750). Al portar, cubrir los 5 casos con datasets de
> referencia corridos en el sistema VFP actual.

## 3. Mora — punitorios y resarcitorios (`recalculo`)

Para cuotas vencidas (`fecha_vto < fecha_pago`):

```
dias      = fecha_pago - fecha_vto
tasa_pun  = lineacred.nmoradia         (si no hay: lineacred.tasa / 30)
int_pun   = ROUND( cuota * tasa_pun * dias / 100 , 2 )
iva_pun   = ROUND( int_pun * tasa_iva * 0.01 , 2 )
int_res   = ROUND( saldo * tasa_res * dias / 100 , 2 )    (tasa_res suele 0)
iva_res   = ROUND( int_res * tasa_iva * 0.01 , 2 )
total_vencido = cuota + int_pun + iva_pun + int_res + iva_res
```

Donde `cuota = capital + interes + iva_interes - total_pagado`.

Regla de imputación:
- Si `año-mes(fecha_vto) == año-mes(fecha_pago)` → se cobra capital+interés (cuota completa).
- Si el vencimiento fue en meses anteriores → se cobra sólo capital (o saldo si `total > saldo`), más punitorios/resarcitorios.
- Sólo se procesan cuotas en estado `A` (activa) o `M` (mora): `estado $ "AM"`.

**Validación contra datos reales (`ivacob.DBF`, 29.084 cobranzas):**
- `IVA_PUNI = round(INTERES_PU × 21%)` se cumple en **863/863** cuotas con mora.
- **Resarcitorios = 0** en los 29.084 registros → confirma `lntasres = 0`.
- El punitorio es **lineal en los días** (`INTERES_PU / días` constante por
  crédito) → confirma la forma `base × tasa × días / 100`.
- Pendiente de cierre al centavo: la **tasa punitoria diaria** exacta
  (`lineacred.nmoradia`), que no está en `ivacob` y requiere el backup de los DBC.

## 4. Margen de afectación (elegibilidad — `calcpres`)

El descuento por planilla no puede superar un porcentaje del sueldo:

```
margen_disponible = ROUND( sueldo * (por_afecta * 0.01) - total_afectado , 0 )
```

- `por_afecta` = `lineacred.por_afecta` (% máximo de afectación del haber).
- `total_afectado` = suma de cuotas de créditos activos que ya afectan el haber.
- Si `margen_disponible < 200` → **el cliente no puede tomar el crédito**.

## 5. Matriz de carteras (compatibilidad de créditos activos)

Un cliente puede tener créditos activos en distintas **carteras**; ciertas
combinaciones se permiten y otras se bloquean. Códigos de cartera:

| Código | Cartera |
|---|---|
| 1 | Personales |
| 2 | Consorcios |
| 4 | Personales AGJS |
| 5 | Sismo |
| 6 | Policías retiro obligatorio |
| 7 | Producir / Min. Producción |
| 8 | Jubilados |
| 9 | Turismo Santa María |
| 10 | Fortalecimiento y promoción regional/municipal |
| 11 | Gas |
| 12 | Municipios |
| 14 | AGAP |
| 17 | Deuda salarial |

Reglas destacadas (de `calcpres`):
- Si existe crédito activo en la **misma cartera** que admite *previo pago (PP)*
  y `nctacan*100/npzotot >= porcent_pp` → se ofrece cancelar el crédito anterior
  (`paga_pp`) y continuar; si no está en condiciones, se bloquea.
- Carteras {1,4,7,8,9,10,12} son compatibles con nueva cartera 5 (Sismo) y 2 (Consorcios).
- Cartera 6 (Policías) + 2 (Consorcios) pendiente → **bloquea**.
- Carteras 6, 10, 17 **no descuentan margen** (excepción al cálculo de margen).
- Carteras 1 y 14 con motivo salud → requieren **N° de Historia Clínica** válido y no usado.

## 6. Previo pago (`paga_pp`) y cancelación (`cancelacre`)

- `paga_pp(no_credito, fecha)` → importe a cancelar del crédito anterior al día.
- `cancelacre` → cancelación total de un crédito (recalcula saldos, aplica mora).

## 7. Utilidades relacionadas

- `valor_hoy` → valor presente / actualización a la fecha.
- `det_cuil` / `valida_cuil` → determinación y validación de CUIL (dígito verificador).
- `c_norecibo` → numeración correlativa de recibos.
- `margen` → cálculo del margen (detalle).

---

## Estrategia de portado (Python)

1. Modelar `LineaCredito` con `tipo_calculo`, `por_afecta`, `tasa`, `nmoradia`,
   `cartera`, `porcent_pp`, expresiones de seguro/gastos.
2. Implementar `generar_plan_cuotas(capital, plazo, linea, fecha_inicio)` →
   lista de cuotas (los 5 tipos).
3. Implementar `recalcular_mora(cuota, dias, linea, tasa_iva)`.
4. Implementar `margen_disponible(sueldo, por_afecta, total_afectado)`.
5. Implementar la matriz de carteras como tabla de reglas declarativa.
6. **Pruebas de equivalencia**: correr créditos reales en VFP, exportar el plan
   de cuotas, y validar que Python coincide al centavo (`pytest`).
