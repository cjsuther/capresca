# Módulo Tesorería (:8012)

Recibe **lotes de pagos**, el tesorero los revisa y aprueba, y los **envía por Interbanking**.

| Origen | Cómo llega | Qué se paga | Aviso de vuelta |
|---|---|---|---|
| Créditos | `POST /internal/tesoreria/lotes` al liquidar/desembolsar (`DESEMBOLSO_VIA_TESORERIA`) | Neto del desembolso al CBU de acreditación | `/internal/creditos/tesoreria/resultado`: CONFIRMADO → contrato **ACTIVO** |
| Conciliación | Mismo endpoint, en cada corrida del motor de pagos (`PAYMENTS_VIA_TESORERIA`) | Saldo a favor de cada agencia a su CBU de cobro | `/internal/conciliacion/tesoreria/resultado`: CONFIRMADO → registro PAGADO |
| Carga manual | Pantalla "Nuevo lote manual" (a mano o CSV) | Lo que se cargue | — |

## Circuito

```
PENDIENTE_APROBACION ──aprobar (workflow LOTE_PAGO)──▶ APROBADO ──enviar──▶ ENVIADO ──▶ CONFIRMADO | CON_ERRORES
        │ excluir/incluir pagos (reinicia aprobaciones)
        └──rechazar──▶ RECHAZADO
```

- **Aprobación:** regla `tesoreria / LOTE_PAGO` en Configuraciones → Workflow (niveles, roles APROBAR /
  SUPERVISAR = permisos `tesoreria:aprobaciones:aprobar|supervisar`, cuatro ojos). Quien armó el lote no
  lo aprueba. Si la regla está inactiva, alcanza con el permiso `aprobaciones:aprobar`.
- **Envío:** permiso `tesoreria:lotes:enviar`. Cada pago se toma con un `UPDATE … WHERE estado` atómico:
  dos envíos simultáneos no pagan dos veces.
- **Pagos inciertos:** si se corta la comunicación con Interbanking (timeout, 5xx) no se sabe si la
  transferencia salió: el pago queda **INCIERTO**, nunca se reintenta solo, y el tesorero lo resuelve
  indicando qué verificó en el banco. Los **FALLIDOS** (rechazo explícito) sí se pueden reintentar, salvo
  que el origen ya los haya vuelto a mandar en otro lote.
- **Un pago vivo por referencia:** el mismo contrato / registro no puede estar en dos lotes a la vez.
  El alta es idempotente por `(origen, referencia_origen)`.
- **Simulación:** `ENVIO_SIMULADO=true` (default) registra los envíos como acreditados sin llamar al
  banco. Para mover dinero: `TESORERIA_ENVIO_SIMULADO=false` con la cuenta de pagos configurada en
  Interbanking.

## Permisos (Seguridad)

`tesoreria:lotes:read` · `lotes:write` (cargar, excluir) · `lotes:enviar` · `aprobaciones:aprobar` ·
`aprobaciones:supervisar`. Lo práctico es un rol "Tesorero" asignado a un **grupo** "Tesorería".

## Tests

```bash
docker compose run --rm --no-deps -v "$PWD/modules/tesoreria:/app" tesoreria \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```
