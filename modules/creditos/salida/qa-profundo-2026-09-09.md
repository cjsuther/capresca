# QA profundo — CCyPP (backoffice + portal) · 2026-09-09

Alcance: revisión **por pantalla, por APIs y por datos** del backoffice y del portal ciudadano,
más análisis de **casos de uso faltantes** por pantalla/circuito. Método: 4 revisiones estáticas de
código en paralelo (créditos, seguridad/IAM, portal, APIs) + verificación dinámica en vivo (navegador +
APIs contra Postgres + datos). Todo hallazgo cita `archivo:línea`.

Estado base: **345/345** pytest en verde antes de empezar; app limpia (2 clientes, 5 productos, 0
contratos/solicitudes tras el reset). 316 endpoints en 24 routers; 45 archivos de test; 101 páginas front.

---

## 1. Verificado EN VIVO (dinámico, contra Postgres)

Circuito de dinero completo ejecutado por API sobre datos reales y **verificado en la DB**:

| Paso | Resultado | Evidencia en Postgres |
|---|---|---|
| Liquidación por lote → desembolso | 2 contratos A_LIQUIDAR → ACTIVO | 2 asientos, `Σdebe=Σhaber=5.000.000`, desbalance 0 |
| Pago de cuota (PAYMENT) | saldo 1.000.000 → 976.271,40 | `pp_actividad` EJECUTADA |
| **Idempotencia** (mismo `Idempotency-Key`) | reintento no duplica | `count(PAYMENT EJECUTADA)=1` |
| **Reversa** del pago | HTTP 200, recompute | actividad REVERSADA, saldo vuelve a **1.000.000 exacto** |
| **Payoff** (cancelación total) | saldo → 0, contrato CERRADO | todas las cuotas PAGADA |
| Contabilidad en cada paso | siempre balanceada | desbalance `0.00` |

Portal (`:5174`), simulador en vivo: wizard 3 pasos OK, **validación de margen/afectación** funciona
(muestra "la cuota supera tu margen; probá un plazo más largo"), bounds de monto/plazo por producto,
elegibilidad informativa. Diálogos in-app (H-152) verificados: modal centrado, foco al input, **Esc cierra
sin mutar**. Datos demo del circuito **limpiados** tras la prueba (0 contratos/solicitudes/asientos).

> Observación a confirmar: en el simulador del portal, con sueldo declarado alto y monto bajo/plazo largo,
> el hint de pre-aprobado siguió mostrando "supera tu margen". Puede ser dato de entrada de la prueba o un
> borde del cálculo de afectación; **revisar** `preAprobado` / `afectacion_max`.

---

## 2. Hallazgos por severidad

### 2.1 CORREGIDOS en esta pasada (H-153)

- **[ALTA] Aprobar/rechazar sin permiso con el workflow inactivo.** `solicitudes.py` (rama aprobar/rechazar)
  y `productos.py` (rama aprobar) delegaban todo en el motor de workflow; con la regla sembrada **INACTIVA**
  (app single-admin, H-141), `aprobar_paso`/`puede_aprobar` devuelven ok **sin mirar rol** → cualquier
  usuario autenticado resolvía. **Fix:** si no hay workflow activo, se exige `_req_aprueba` (rol aprobador de
  la pantalla, H-150); con workflow activo sigue gateando el motor por rol de nivel + cuatro-ojos (no rompe
  cadenas N-niveles con roles intermedios). Tests nuevos: `test_aprobar_exige_rol_aun_con_workflow_inactivo`
  (solicitudes), `test_aprobar_linea_exige_rol_aun_con_workflow_inactivo` (productos).
- **[ALTA] Grupo desactivado seguía otorgando acceso.** `roles_de` (`permisos.py`) filtraba vigencia pero
  nunca miraba `Grupo.activo` → desactivar un grupo no cortaba roles ni capacidad de aprobar de sus miembros.
  **Fix:** `roles_de` sólo toma roles de grupos `activo=True`. Test nuevo: `test_grupo_inactivo_no_otorga_acceso`.

### 2.2 ALTA — pendientes (recomendado atacar próximo)

1. **Reversa de refinanciación duplica capital.** `contratos.py:1075` (`reversar`) sólo bloquea
   DISBURSEMENT/REVERSAL; reversar la `RENEGOTIATION` reactiva el contrato viejo (recompute → ACTIVO,
   saldo=monto original) mientras el nuevo sigue vivo → **mismo capital colocado dos veces**. El front habilita
   el botón (`SituacionClientePP.tsx:302`). Fix: bloquear reversa de RENEGOTIATION (o revertir en cascada el
   contrato nuevo).
2. **`liquidar_lote` no idempotente ni serializado.** `contratos.py:391-416` itera y desembolsa sin
   Idempotency-Key / `FOR UPDATE` / recheck en el loop → doble desembolso + doble asiento ante doble-clic o
   concurrencia (el endpoint unitario sí está protegido).
3. **Idempotencia ausente en cobros/pagos.** `caja.py` (`/cobrar`), `egresos.py` (`/pagar`,
   `/pagar-chequera`), `juegos.py` (cobros) y `creditos.py:243` (payoff `/cancelar`) no pasan por
   `con_idempotencia` → doble-POST = doble recibo. Sólo lo frena `postIdem` en el front.
4. **Alta de cliente sin unicidad concurrente.** `clientes.py:crear` hace check-then-insert sin
   `_commit_unico`/SAVEPOINT y `Cliente.cuil` **no tiene unique constraint** → carrera crea CUIL duplicado
   (viola "la DB es árbitro"). Sin Idempotency-Key. `id_cliente` unique pero su colisión da 500.
5. **Lockout del último admin (2 vías).** `editar_usuario` y `set_usuario_perfiles` (`admin.py`) cambian el
   perfil principal sin el guard de "último ADMG" que sí tiene la baja; y `editar_perfil` puede
   `habilitado=False` sobre ADMG → `auth.py:33-35` bloquea el login de todos.
6. **IAM sin auditoría.** `admin.py` no llama `registrar_cambio` en ninguna mutación (usuarios/roles/grupos/
   permisos/workflow). Sólo se audita LOGIN. Grave para un módulo de seguridad.
7. **RBAC fino sólo decorativo en backend.** El nivel por pantalla que configura `Perfiles.tsx` sólo se
   enforca en 1 endpoint (`contratos.py:316`); el resto confía en el gateo del front (Contabilidad/Clientes/
   Feriados sólo `get_current_user`; Caja/Tesorería usan `requiere_perfil` coarse por principal).
8. **Portal — UI de documentos inexistente.** El backend de documentos está completo pero `App.tsx` no tiene
   pantalla (helpers muertos en `api.ts:80-87`) → el ciudadano no puede subir/declarar docs.
9. **Migradores sin cobertura ni test de permiso.** `POST /{clave}/ejecutar` y `/ejecutar-todo` **mutan la DB**
   y no tienen ni un test de permiso (no-admin → 403) ni de persistencia.

### 2.3 MEDIA (selección)

- **CBU nunca validado/exigido en backend.** Sólo front y sólo canal web; el wizard de "Nueva solicitud" de
  backoffice ni captura CBU → origina/desembolsa con `cbu=""`. Falta también dígito verificador (front y back).
- **`pp_contrato` sin FK al maestro** (`cliente_nombre` string, sin `cliente_id`) → homónimos colisionan en la
  Situación del cliente (agrupa por nombre).
- **CUIL/DNI sin dígito verificador** en el circuito de solicitudes/promoción (Clientes.tsx sí lo tiene).
- **Grupo→rol sin vigencia; rol adicional/heredado deshabilitado no corta acceso** (sólo el principal).
- **Permiso directo NINGUNO no revoca** (se borra la fila y el efectivo toma el MAX de la unión) — definir si
  es intención o hace falta un DENY explícito.
- **Portal: token vencido a mitad de sesión no expulsa a Login** (sin interceptor global de 401 ni refresh).
- **Portal: "cuota congelada" no lo está** — el envío recomputa con `date.today()` y TNA variable; puede
  diferir de lo que vio el ciudadano.
- **Overrides INCLUIR/EXCLUIR del workflow son config muerta** (el evaluador no los consulta; la UI ya no los
  muestra tras H-150 pero el API los sigue aceptando). El rol-picker del workflow no ofrece SUPE/OPER.
- **`requiere_perfil`/`_req_admin` usan `user.perfil` (principal), no `roles_de`** → inconsistente con H-150
  (un ADMG heredado por grupo aprueba créditos pero no entra al panel admin).
- **Dos motores de cálculo coexisten** (`productos_calc.cronograma` vs `domain/cuotas.generar_plan`) sin guarda
  cruzada — `motor-unico` es "por circuito".
- **`RecalculoCredito`** sin auditoría, sin idempotencia, sin confirmación ni `soloLectura`.
- **Portal: state OIDC sin nonce one-time** (state firmado mitiga CSRF, pero sin anti-replay dentro de 10 min).

### 2.4 BAJA (selección)

- Routers con cobertura CERO de test: `controles-version`, `migradores`.
- Diálogos danger: el foco inicial cae en el botón destructivo (un Enter reflejo confirma) — considerar
  enfocar Cancelar en `danger`.
- Portal: dark sólo por media-query (sin toggle); badge de notis cuenta total, no "no leídas"; sin
  rate-limiting en `/login`/`/simular`; filename de descarga sin sanitizar (formatos peligrosos ya excluidos).
- Migradores usa `<table>` cruda en vez de `DataTable` (desviación de diseño consciente).
- 0 tests de frontend (backoffice y portal).

---

## 3. Casos de uso FALTANTES de probar (backlog priorizado)

Consolidado de las 4 revisiones (dedup). Totales: **Alta ~20 · Media ~30 · Baja ~25**.

### Alta (los que faltan sí o sí)
- Aprobar/rechazar solicitud y línea sin rol, con workflow inactivo → 403. **(ya cubierto por H-153)**
- Grupo inactivo deja de otorgar rol/permiso. **(ya cubierto por H-153)**
- Reversa de refinanciación (no debe duplicar capital).
- Doble liquidación de lote / concurrencia de lote (no duplica desembolso ni asiento).
- Idempotencia de `caja/cobrar`, `egresos/pagar`, `juegos/cobrar`, `creditos/cancelar` (payoff).
- Alta de cliente concurrente con mismo CUIL (unicidad, la DB árbitro) — hoy sin constraint.
- Último admin: `editar_usuario`/`set_usuario_perfiles`/`editar_perfil` no deben dejar el sistema sin admin.
- H-150 vigencia: rol heredado con `vigente_hasta` pasada NO aprueba (403).
- H-150 rol aprobador **no-ADMG** (SUPE) heredado por grupo aprueba; cadena N-niveles con rol intermedio heredado.
- Migradores: `POST /{clave}/ejecutar` no-admin → 403 + persistencia contra Postgres.
- Portal: expiración de token a mitad de sesión expulsa a Login; borrar documento propio/ajeno (403).
- Postgres: colisión de número concurrente en `originar` y `caja/cobrar` (SAVEPOINT + constraint real).

### Media (destacados)
- `cronograma` tna=0, plazo=1, montos grandes (redondeo, última cuota absorbe, `Σcapital==P`).
- Reversa/contra-asiento balanceado explícito en caja/egresos/juegos anular (`Σdebe==Σhaber`, signo opuesto).
- `despacho`: firmar/archivar en estado inválido → 409; pase a oficina inexistente → 404/422.
- `mesa`: atender/cancelar turno en estado inválido → 409.
- Enforcement RBAC fino por pantalla en Contabilidad/Clientes/Feriados (hoy sólo front).
- Wizard backoffice: capturar y validar CBU antes de originar; DV de CUIL/CBU.
- Portal: discrepancia simulado vs persistido con TNA variable (definir si se congela la vista).
- `borrar_perfil` no debe dejar un nivel de workflow apuntando a un rol borrado (nivel huérfano).

### Baja (destacados)
- Smoke de `controles-version` y `sistema-calculos`; informes de contabilidad (`/mayor/*`, `/iva-*`).
- `feriados/importar` idempotente; `indices/{id}/baja` y `/reactivar`; `seguros/generar-cuotas` idempotente.
- Endpoints `*/excel` y `*/pdf`: content-type + no-500.
- `aprobaciones/pendientes/{id}/rechazar` (reinicia cadena) y `/count` (badge).

---

## 4. Lo que está SÓLIDO (verificado)

- Motor de cálculo único por circuito (`cronograma`): simulado == contratado; cobertura fuerte.
- Event-sourcing del servicing + recompute idempotente; reversa = REVERSADA + recompute (verificado en vivo).
- Contabilidad balanceada (debe=haber) en todos los pasos (verificado en vivo).
- Idempotency-Key en el servicing de contratos (verificado en vivo: reintento no duplica).
- Unicidad concurrente con primer-libre + SAVEPOINT (numbering) — cubierto por tests.
- Cuatro-ojos / N-ojos: precedencia rol→cuatro-ojos, carrera resuelta por `uq_wf_aprobacion_nivel` (409).
- H-150 RBAC (roles+grupos): `roles_de`/`caps_creditos`/`_rol_apto` comparten fuente; ADMG sin_restricciones;
  perfil configurado queda restringido (ahora también respeta grupo inactivo).
- H-152 diálogos in-app: 0 `window.confirm/alert/prompt` residuales; Esc/Enter/fondo/danger correctos.
- Portal: realms separados, secretos sólo por env (Mi Catamarca), token en fragmento (sin PII en URL), sin XSS.

---

## 5. Recomendación

Orden sugerido para la próxima tanda (todo ALTA, bajo costo/alto impacto y en la misma área):
1. Reversa de refinanciación (bloquear o cascada) — riesgo de doble colocación de capital.
2. Idempotencia + serialización de `liquidar_lote` y de cobros/pagos (caja/egresos/juegos/payoff).
3. Unicidad concurrente + constraint en `Cliente.cuil` + Idempotency-Key en alta de cliente.
4. Guard de "último admin" en editar_usuario/set_usuario_perfiles/editar_perfil.
5. Auditoría (`registrar_cambio`) en las mutaciones de IAM.
6. Enforcement RBAC fino por pantalla en el backend (no sólo front).

Los casos de test faltantes de la sección 3 se pueden ir sumando junto con cada fix (cada bug suma su caso
en Controles de Versión + su entrada en hallazgos, como marca el CLAUDE.md).
