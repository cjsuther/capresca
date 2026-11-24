# Módulo Configuraciones (:8011)

Configuración compartida de Portezuelo. Es el **dueño** de estos datos; los módulos que los usan los leen
por su API interna y no guardan copia propia.

| Catálogo | Qué es | Quién lo usa |
|---|---|---|
| **Impuestos** | IVA, IIBB, sellados, percepciones (alícuota, base, cuenta, vigencia) | Créditos, al armar el componente de impuestos de un producto |
| **Índices de referencia** | BADLAR, TPM, UVA… (% nominal anual) | Créditos: TNA de las líneas variables = índice + margen, y repricing |
| **Feriados** | Calendario por país (carga manual o importación oficial / cálculo local AR) | Créditos: corre vencimientos a día hábil |
| **Workflow de aprobaciones** | Por módulo y objeto: niveles en serie, rol que aprueba cada uno, cuatro-ojos y excepciones por usuario | Créditos: LINEA, SOLICITUD, DESEMBOLSO, REFINANCIACION |

Del workflow vive acá **sólo la definición**. La ejecución (qué nivel de qué objeto aprobó quién, con la
unicidad por nivel) la hace el módulo dueño del objeto.

### Workflow gráfico versionado (fases 1 y 2)

- `wf_proceso` (uno por módulo/objeto) y `wf_version` (un **grafo** por versión: `BORRADOR` → `PUBLICADA`
  → `RETIRADA`; una sola publicada y un solo borrador por proceso, con índices únicos parciales).
- API `/api/configuraciones/workflow/{procesos,versiones,comparar,catalogo}` (`app/routers/wf.py`).
  Borradores con `workflow:write` y **sin step-up** (autosave); publicar/retirar/habilitar con
  `workflow:publish` y **step-up**.
- Validación, proyección, diff y conversión del grafo: funciones puras en `app/services/wf_grafo.py`.
- **Convivencia:** la versión publicada se proyecta sobre `workflow_reglas`/`workflow_niveles`/
  `workflow_nivel_usuarios`, que es lo que sigue sirviendo `/internal/configuraciones/workflow/...`.
  Créditos y Tesorería no cambian. Por eso sólo se **publica** un grafo que el motor actual sabe ejecutar
  (aprobaciones en serie por rol). Decisiones, notificaciones y grupos se diseñan y validan en
  borrador, y se van a poder publicar cuando llegue el motor nuevo (fase 3).
- **Migración:** el seed (`sincronizar_procesos`) convierte cada regla en la versión 1 PUBLICADA. Es
  idempotente y no borra ni toca las tablas viejas. La vista lista (`GET /workflow`) quedó en sólo
  lectura.
- Decisiones y supuestos: `docs/decisiones-workflows.md`.

## API

- **Pública** (por el gateway, `/api/configuraciones/*`): ABM de cada catálogo. Frontend en
  `frontend/src/modules/configuraciones/`.
- **Interna** (`/internal/configuraciones/*`, header `X-Api-Key` = `CONFIGURACIONES_INTERNAL_API_KEY`; no
  sale del gateway ni de nginx): lectura de impuestos, índices (`/indices/{codigo}`), feriados por rango,
  regla de workflow (`/workflow/{modulo}/{objeto}`) e importación idempotente (`/importar`). Sin clave
  configurada, la API interna queda cerrada.

## Permisos (Seguridad → módulo *Configuraciones*)

Un par por catálogo: `impuestos:read|write`, `indices:read|write`, `feriados:read|write`,
`workflow:read|write`, más `workflow:publish`, que se asigna aparte para publicar, retirar o habilitar
un workflow. El gateway exige `read` para GET y `write` para el resto; el módulo revalida las
escrituras. **Configurar el workflow es un permiso aparte** de operar los módulos: quien diseña o
carga créditos no puede sacarse de encima su propio control.

## Cómo lo consume Créditos

`modules/creditos/backend/app/core/configuraciones.py`: caché de 30 s (`CONFIGURACIONES_CACHE_SEGUNDOS`),
y si este módulo no responde usa la última copia hasta 10 min. Sin copia **falla cerrado** con 503: no
se simula ni se aprueba con un calendario o una regla inventados.

Para sumar un módulo al workflow, agregá sus objetos a `CATALOGO` en `app/services/workflow.py` (se
siembran inactivos al arrancar o al pedir la regla).

## Operación

```bash
docker compose up -d --build configuraciones      # alembic upgrade + seed + API
# Una vez, para traer lo que tenía Créditos (idempotente):
docker compose exec creditos python -m app.etl.migrar_configuraciones [--dry-run]
# Tests
docker compose run --rm configuraciones sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```

El seed (idempotente) carga los impuestos e índices por defecto sólo si la tabla está vacía, el
calendario AR calculado del año actual y los dos siguientes, y las reglas del catálogo (inactivas, un
nivel `APROBAR` con cuatro-ojos). Después sincroniza cada regla con su proceso del workflow gráfico
(versión 1 publicada).
