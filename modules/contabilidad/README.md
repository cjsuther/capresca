# Módulo Contabilidad (:8014)

**Ningún módulo manda asientos.** Los módulos mandan la **transacción** que ocurrió (un desembolso,
una cobranza, un pago) y acá se decide cómo se registra, con la **definición** de ese tipo de
transacción. Si la definición no existe, la transacción queda **PENDIENTE_CONFIGURACION** en este
módulo: no se inventa un asiento ni se pierde el dato, y al definir la regla se contabiliza sola.

```
módulo → POST /internal/contabilidad/transacciones → ¿hay definición para (módulo, tipo)?
                                                     ├── no → PENDIENTE_CONFIGURACION (espera)
                                                     └── sí → se calculan los importes, se valida
                                                              la partida doble y sale el asiento
```

Trazabilidad en los dos sentidos: de la transacción al asiento y del asiento a la operación que lo
originó (con los datos que mandó el módulo).

## Definición de asiento

Se cargan desde **Contabilidad → Definiciones de asiento** (alta, edición y prueba) o directamente
desde una transacción que está esperando, en **Transacciones** (ahí el formulario ya viene con el
módulo, el tipo y los campos que mandó ese módulo, con valores de ejemplo).


Por módulo y tipo de transacción, con vigencia. Cada línea dice cuenta, lado y **cómo se calcula el
importe** con los campos que manda el módulo:

| Lado | Cuenta | Importe | Detalle |
|---|---|---|---|
| DEBE | 1.1.04 Préstamos otorgados | `capital + gastos` | Préstamo otorgado |
| HABER | 1.1.02 Bancos | `capital` | Transferencia al cliente |
| HABER | 4.1.03 Comisiones | `gastos` | Cargo de otorgamiento |

Las expresiones aceptan números, los campos de la transacción y `+ - * /`: **no ejecutan código**.
Las líneas que dan cero no ensucian el asiento. La pantalla permite **probar** la definición con una
transacción real antes de aplicarla.

## Lo que necesita una contabilidad argentina

- **Plan de cuentas** por rubro (activo, pasivo, patrimonio, ingresos, egresos y cuentas de orden),
  con cuentas de agrupación (no imputables), saldo normal, moneda y marca de **ajustable por
  inflación** (RT 6) para las no monetarias.
- **Partida doble obligatoria**: no entra un asiento que no balancee ni en cero.
- **Ejercicios**: un asiento sólo entra en un ejercicio ABIERTO; el **cierre** refunde los resultados
  contra la cuenta de resultado del ejercicio y bloquea el período (no cierra si quedan transacciones
  sin contabilizar).
- **Numeración correlativa** por ejercicio y **libro inalterable**: un asiento no se edita ni se
  borra; se **anula con su contra-asiento** y los dos quedan a la vista.
- **Libros**: Diario, Mayor por cuenta (con saldo anterior y acumulado), **Sumas y saldos**.
- **Estados contables**: situación patrimonial y resultados, con el control de la ecuación contable.
- **Libro IVA Ventas y Compras**: la transacción puede traer su comprobante (tipo, punto de venta,
  número, CUIT, netos, alícuota, IVA, percepciones y retenciones) y se registra junto con el asiento,
  con totales por alícuota.
- **Centros de costo** y **diarios** (Caja, Banco, Ventas, Compras, Varios).
- Ente contable con **CUIT y condición frente al IVA**.

## Además (paridad con el sistema anterior)

- **Conciliación bancaria**: se carga el extracto del banco y se coteja contra el mayor de la cuenta,
  a mano o **automáticamente** (empareja por importe y fecha, con tolerancia de 5 días). La pantalla
  muestra saldo del extracto, saldo del mayor y la **diferencia a explicar**.
- **Asientos en borrador**: se guardan sin entrar en los libros, se revisan y después se publican (o
  se descartan). Un asiento ya registrado no se borra: se anula.
- **Apertura y reapertura de ejercicio**: el ejercicio nuevo se abre con los **saldos patrimoniales**
  del anterior (los resultados no se arrastran: se refundieron al cerrar), y un ejercicio cerrado se
  puede reabrir, lo que anula su asiento de cierre dejando el rastro.
- **Flujo de efectivo**: entradas y salidas por caja y bancos, con la contrapartida de cada
  movimiento y el saldo por cuenta.
- **Posición de IVA del período**: débito contra crédito fiscal, percepciones y retenciones, y cuánto
  queda a pagar o a favor, con el detalle por alícuota.
- **Análisis por centro de costo**: ingresos, egresos y resultado de cada centro.
- **Entes contables**: razón social, CUIT, condición frente al IVA y domicilio.
- **Plan de cuentas** con la misma experiencia del sistema anterior: **árbol jerárquico** plegable con
  buscador a la izquierda y los **datos de la cuenta** a la derecha. Cada rama tiene su "＋" para
  agregarle una subcuenta con el **código ya sugerido** (1.1 → 1.1.03), la cuenta que se está creando
  aparece en el árbol para ver dónde queda, se puede **duplicar** una cuenta y avisa antes de perder
  cambios sin guardar. Una cuenta **en uso** muestra sus movimientos y deja fijos el código, el rubro y
  la imputabilidad (para dejar de usarla, se le saca "Activa"); una cuenta sin movimientos se borra.

## Permisos

`contabilidad:asientos:read` (libros y consulta) · `asientos:write` (asiento manual y anulación) ·
`definiciones:write` (plan de cuentas y definiciones) · `ejercicios:write` (abrir y cerrar).

## Integraciones

Hoy mandan transacciones **Créditos** (desembolso, devengamiento de interés, cobranza de cuota y
cancelación anticipada) y **Tesorería** (pago acreditado). Sumar otro módulo es copiar
`app/services/contabilidad_central.py`, llamar a `registrar(...)` donde ocurre el hecho económico y
definir el asiento desde la pantalla.

## Pendiente

El **ajuste por inflación** está preparado en el plan (marca `ajustable` y cuenta RECPAM) pero el
motor de reexpresión todavía no está.

## Tests

```bash
docker compose run --rm --no-deps -v "$PWD/modules/contabilidad:/app" contabilidad \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```
