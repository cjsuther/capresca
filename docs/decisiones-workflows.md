# Workflows gráficos — decisiones y supuestos (fases 1 y 2)

> Acompaña a `docs/analisis-workflows.md` (PR #7). Mientras Cristian no responda las preguntas de la §6
> del análisis, se trabaja con los **supuestos** de abajo. Si alguno cambia, este documento dice qué
> hay que tocar.

## Supuestos (pendientes de confirmación)

| # | Pregunta (§6 del análisis) | Supuesto con el que se implementó | Si cambia… |
|---|---|---|---|
| 1 | Alcance | **Aprobaciones primero.** El grafo gobierna la compuerta de aprobación, no el ciclo de vida de los objetos | Ciclo de vida = fase posterior al motor nuevo |
| 2 | Quién diseña | **Sólo administradores.** Armar borradores: `configuraciones:workflow:write`. Publicar, retirar o habilitar: `configuraciones:workflow:publish` + **step-up**. El autosave del borrador **no** pide step-up | Si lo editan usuarios funcionales: más guía en el editor y, quizás, cuatro-ojos para publicar (quien editó no publica) |
| 3 | Tipos de nodo de la v1 | **5:** inicio, aprobación, decisión, notificación, fin | Sumar nodos = sumar el tipo en `wf_grafo.py`, `grafo.js` y la paleta |
| 4 | Aprobadores | **Rol** (APROBAR/SUPERVISAR → permisos `<modulo>:aprobaciones:*`) **o grupo** de Seguridad, más incluir/excluir usuarios | — |
| 5 | Rechazo | **Vuelve al inicio** (reinicia la cadena, como hoy). El editor lo crea así por defecto | Se admite también rechazo → Fin «Rechazado» |
| 6 | Casos en curso | **Terminan con su versión** | Migrar casos en curso = fase posterior |

## Decisiones de implementación

### Convivencia con el motor actual (lo más importante)

- Créditos y Tesorería **no cambian**: siguen leyendo `GET /internal/configuraciones/workflow/{modulo}/{objeto}`. Ese endpoint sigue sirviendo las tablas viejas (`workflow_reglas` / `workflow_niveles` / `workflow_nivel_usuarios`), sin tocar su código.
- Al **publicar** una versión, se **proyecta** sobre esas tablas *en el lugar*: lo que no cambia conserva su id. Hay un test de equivalencia (`tests/test_wf_api.py`) que verifica tres cosas:
  - migrar no cambia ni un byte de la API interna;
  - publicar devuelve el mismo formato;
  - volver a una versión igual a la original devuelve **exactamente** lo de antes, ids incluidos.
- **Sólo se publica lo que el motor actual sabe ejecutar:** Inicio → Aprobación 1 → … → Aprobación N → Fin «Aprobado», asignado por **rol**, con «rechazado» al Inicio o a un Fin «Rechazado».
  - Decisiones, notificaciones y aprobaciones por **grupo** se pueden **diseñar, validar y guardar** en borrador.
  - Publicarlas devuelve 409 con el motivo («llega con el motor nuevo, fase 3»). El editor lo avisa antes.
  - Así nadie publica algo que el sistema ignoraría en silencio.
- `habilitado` del proceso = `activo` de la regla vieja.
  - **Retirar** la versión publicada sin reemplazo deja el proceso **deshabilitado**: no hay definición vigente, igual que desactivar la regla vieja.
  - Una vez retirada, la sincronización no la vuelve a publicar sola.

### Defecto conocido que el versionado todavía no corrige

Publicar una versión con **menos niveles** sigue afectando a los casos en curso en Créditos y Tesorería (§2.3 del análisis). Pasa porque esos módulos leen la regla "en vivo" hasta la fase 3. El editor lo advierte al publicar. Conviene corregir esos dos defectos aparte, como hallazgos con su test.

### Migración de las reglas actuales

- **Alembic `0002_wf_versionado`:** sólo crea `wf_proceso` y `wf_version`, con índices únicos parciales: una PUBLICADA y un BORRADOR por proceso, en Postgres y SQLite. El downgrade borra sólo esas dos tablas.
- La **carga de datos** la hace `app.seed` (que corre después de `alembic upgrade head` al arrancar el contenedor), con `wf_procesos.sincronizar_procesos`:
  - cada regla queda como **versión 1 PUBLICADA**, con el mismo nombre, rol, cuatro-ojos y excepciones;
  - es **idempotente**;
  - **no borra ni toca** las tablas viejas.

  No va dentro de la migración porque una migración que importa los modelos ORM se rompe el día que el modelo cambie.
- Si una regla vieja cambia por fuera del editor (el import interno del ETL de Créditos), la sincronización crea una versión publicada nueva tomada de la regla. Así el editor siempre muestra la verdad.
- Verificado contra **Postgres 16**:
  - upgrade y seed dos veces;
  - la API interna queda idéntica;
  - con dos publicaciones simultáneas, pasa una y la otra recibe 409;
  - downgrade y upgrade otra vez.

### Vista lista

La pantalla vieja queda como **«Vista lista», de sólo lectura**: muestra la versión vigente de cada regla. Se quitaron sus endpoints de escritura (`/workflow/reglas|niveles|usuarios`). Tener dos lugares para editar haría que publicar un borrador pisara en silencio un cambio hecho en la lista.

### Concurrencia

- **Autosave:** concurrencia optimista con `revision`. Si otro usuario guardó el borrador antes, la respuesta es 409 y no se pisa nada.
- **Publicar y retirar:** `SELECT … FOR UPDATE` sobre el proceso, relectura después del lock, y los índices únicos parciales como árbitro.

### Step-up (proxy)

- `publicar`, `retirar` y `habilitado` tienen su regla con texto propio.
- Las escrituras de **borradores** (crear, guardar, descartar) están en `SIN_STEP_UP`. Esa lista se evalúa **después** de `REGLA_SEGURIDAD`, así que nunca exime nada de Seguridad; hay un test que lo verifica.
- El resto de las escrituras en `/api/configuraciones/workflow` sigue bajo la regla general.

### Auditoría

- `auditoria_central` sigue registrando cada fila que cambia: `wf_version`, `wf_proceso` y la proyección sobre las reglas.
- Además, publicar, retirar y habilitar dejan un evento de negocio (`ACCION`) con el **diff en castellano** respecto de la versión anterior. Ese diff también queda guardado en `wf_version.diff_resumen`.

### Variables de las condiciones

- Las declara Configuraciones por ahora (`services/workflow.py → VARIABLES`), por ejemplo `monto`, `plazo` y `origen` de la solicitud, o `importe_total` y `origen` del lote.
- Sirven para **diseñar y validar** decisiones. Las evalúa el motor nuevo (fase 3), cuando cada módulo pase a declararlas él mismo.

### Editor gráfico (fase 2)

- **React Flow** (`@xyflow/react`, MIT) para el lienzo y **elkjs** (EPL-2.0) para el auto-layout. ELK se carga con import dinámico: sólo baja al pedir «Ordenar».
- Para exportar PNG se usa **html-to-image** (MIT).
- Toda la lógica (validación espejo, armado del grafo, conversión a nodos de React Flow, condiciones, diff) está en **funciones puras** con tests de Vitest. El canvas no se testea por arrastre.
- La validación del frontend usa **los mismos códigos** que la del backend. Es para el feedback en vivo; la que decide al publicar es la del backend.
- Los selectores de rol, grupo y usuario leen Seguridad (`/api/security/groups` y `/api/security/users`). Si el usuario no tiene permiso de lectura en Seguridad, se puede escribir el nombre a mano.
