# CCyPP — Guía obligatoria para trabajar en este proyecto

Migración del sistema VFP CCyPP (Ca.Pre.S.Ca.) a **Python/FastAPI + PostgreSQL + React/Vite/TS + Docker**.
El módulo en foco es **Configurar Créditos** (product builder tipo Temenos AA, tablas `pp_*`).

> Los catálogos vivos de estos principios están en la app: **Controles de Versión → Principios de
> arquitectura** y **→ Principios de diseño** (con ejemplos). Fuente: `app/api/controles_version.py`
> (`PRINCIPIOS` / `PRINCIPIOS_DISENO`). Si una decisión aporta un principio nuevo, **agregarlo ahí**.

## Antes de tocar UI — Principios de diseño (obligatorio)
- **Tablas = componente `DataTable`**, idénticas en todo el sistema salvo aclaración. Modelo de
  referencia: **Maestro de clientes** (`src/pages/Clientes.tsx`). No armar tablas propias.
- **Layout de ABM**: header (h1 + subtítulo muted + `＋ Nuevo`) → card `padding:0` con toolbar de
  búsqueda/filtros (borderBottom) → `DataTable` → alta/edición en form panel/modal.
- **Badge `new`** (`nuevo:true` en el Sidebar) en toda opción nueva o rehecha.
- **Estados con pills** semánticos: `pill ok|warn|crit|brand`.
- **CSS scopeado por pantalla** (prefijo `.cfgc`, `.sitc`, `.wfa`…) — nunca clases genéricas compartidas
  (rompió el calendario de feriados, H-083). **Con candado** (`check-diseno.mjs` + hook): definir `.card`,
  `.row`, `.cell`… bare en el `<style>` de una página se bloquea; usá prefijo por pantalla.
- **Colores por variables de tema** (`--surface`, `--ink`, `--border`, `--brand-2`, `--ok/--warn/--crit`
  y sus `*-soft`), nunca hex cromático fijo (sí `#fff`/`#000`). **Con candado** (`check-diseno.mjs` + hook):
  hex nuevo se bloquea salvo `diseño-ok:` o allowlist. Referencia OK: `src/pages/seguridad/WorkflowAprobaciones.tsx`.
- **Formato es-AR** y clase `.num` en columnas numéricas.
- **Confirmar acciones irreversibles** (baja/borrado/payoff) y marcarlas en rojo (danger).

## Antes de decidir algo estructural — Principios de arquitectura (obligatorio)
- **Unicidad concurrente**: los IDs únicos se generan con "primer libre" + **reintento sobre SAVEPOINT**
  (`app/core/numbering.py`); la constraint única de la DB es el árbitro, nunca un lock aplicativo.
- **Idempotency-Key** en altas mutantes (`app/core/idempotency.py` + `postIdem` en el front).
- **Motor único de cálculo**: `cronograma()` es la única fuente de verdad (simulado == contratado).
- **Event-sourcing** del servicing: `pp_actividad` es la verdad; `_recompute` reconstruye; reversa = marcar
  REVERSADA + recompute (idempotente).
- **Snapshot congelado**: el contrato congela el producto/versión al originar.
- **Contabilidad balanceada**: todo asiento debe=haber; la reversa contra-asienta, no borra.
- **Cuatro-ojos / N-ojos** configurable (Seguridad → Workflow); el emisor no aprueba.

## QA (obligatorio) — ver también memoria `qa-profundo-siempre`
- No alcanza la UI: verificar **persistencia real en la DB** tras cada mutación y probar las **altas
  contra Postgres** (incluida la carrera borrar-y-recrear y concurrente), no sólo con SQLite en verde.
- Todo bug encontrado suma su **caso en Controles de Versión** (auto/live/manual) y su entrada en
  `salida/hallazgos.md`. Al mutar producción en QA, **limpiar los datos demo** después.
- El backup es de **producción viva**: fechas 2026 son reales; las claves nunca se migraron (hash
  irreversible) — no recuperarlas.

## Operación
- Backend + DB en Docker: `docker compose exec backend python -m pytest -q`; reiniciar backend tras
  cambios (`docker compose restart backend`). Tablas `pp_*` nuevas se crean solas al arrancar.
- DB Postgres: usuario/clave/base `ccypp`. En producción sólo existe el usuario `admin` (los flujos
  cuatro-ojos con otros perfiles se prueban por pytest/SQLite).
