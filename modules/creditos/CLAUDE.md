# CCyPP — Guía obligatoria para trabajar en este proyecto

Migración del sistema VFP CCyPP (Ca.Pre.S.Ca.) a **Python/FastAPI + PostgreSQL + React + Docker**, integrado a Portezuelo.
El módulo en foco es **Configurar Créditos** (product builder tipo Temenos AA, tablas `pp_*`).

> Esta guía es el catálogo de principios del módulo (la pantalla *Controles de Versión* de CCyPP se retiró
> con la integración a Portezuelo). Si una decisión aporta un principio nuevo, **agregarlo acá**.

## Alcance
El módulo es **sólo el circuito de créditos**: productos, solicitudes, originación, servicing, cartera,
reportes y el portal ciudadano. Las demás áreas de CCyPP (caja de ventanilla, contabilidad, tesorería,
seguros, despacho, mesa de entradas, juegos, tablas generales, seguridad) **no se migraron** y no tienen
endpoints ni permisos. Sus servicios que el crédito usa por dentro siguen: asientos (`services/contabilidad`),
póliza al otorgar (`services/seguros`), orden de pago del desembolso (`services/egresos`) y recibo de la
cancelación anticipada (`services/caja`). Permisos: `creditos:read` / `creditos:write` +
`aprobaciones:aprobar|supervisar` (ver H-211).
El **desembolso** sale por el módulo **Tesorería** de Portezuelo (`DESEMBOLSO_VIA_TESORERIA`, H-216): el
contrato queda A_LIQUIDAR "en Tesorería" y pasa a ACTIVO con el aviso de transferencia acreditada.

**Impuestos, índices de referencia, feriados y las reglas del workflow** son del módulo
**Configuraciones** (`modules/configuraciones`, H-212): Créditos los lee con `app/core/configuraciones.py`
(caché corta, falla cerrado con 503) y no tiene ABM ni tablas propias de eso. Los tests usan
`tests/config_falsa.py` (fixture autouse `config_falsa`): para activar una regla o cambiar un índice en un
test, `config_falsa.activar("LINEA")`, `config_falsa.set_indice("BADLAR", 60)`.

## Antes de tocar UI — Principios de diseño (obligatorio)
El backoffice es el módulo `frontend/src/modules/creditos/` del frontend de Portezuelo (**JSX + Tailwind**,
tests Vitest al lado de cada pantalla). La SPA TSX propia (`modules/creditos/frontend`) se retiró; no
reintroducir pantallas fuera del frontend del sistema. El portal ciudadano (`portal/`) sí sigue aparte.
- **Tablas = componente `DataTable`** (`components/DataTable.jsx`), idénticas en todo el módulo. No
  armar tablas propias.
- **Layout de pantalla**: `PageHeader` (título + descripción + acciones) → `Card padding={false}` con
  `Toolbar` de búsqueda/filtros (+ `LimpiarFiltros`) → `DataTable` → alta/edición en `Modal`
  (`components/ui.jsx`).
- **Estados con `Pill`** semánticos: `tono = ok | warn | crit | brand | neutral`.
- **Colores sólo con las clases del tema** (`bg-surface`, escala `gray-*`, acentos `blue/red/green/
  amber/yellow-*`): son tokens CSS que cambian con el tema claro/oscuro (`frontend/src/index.css`).
  Nada de hex fijos ni variantes `dark:` en el markup; los gráficos toman la paleta de
  `graficos.js` (validada para ambos fondos). Ver H-208.
- **Formato es-AR** con `components/format.js` (`money`, `num`, `fecha`) y `tabular-nums` en columnas numéricas.
- **Confirmar acciones irreversibles** (baja/borrado/payoff) con `Confirmacion` y marcarlas en rojo
  (`Boton variante="danger"`).
- **Permisos**: `usePuedeVer` / `usePuedeEscribir` / `useSoloLectura` (`permisos.js`); toda pantalla
  nueva se registra en `menu.js` + `rutas.jsx`.

## Antes de decidir algo estructural — Principios de arquitectura (obligatorio)
- **Unicidad concurrente**: los IDs únicos se generan con "primer libre" + **reintento sobre SAVEPOINT**
  (`app/core/numbering.py`); la constraint única de la DB es el árbitro, nunca un lock aplicativo.
- **Idempotency-Key** en altas mutantes (`app/core/idempotency.py` + `postIdem` en el front).
- **Motor único de cálculo**: `cronograma()` es la única fuente de verdad (simulado == contratado).
- **Event-sourcing** del servicing: `pp_actividad` es la verdad; `_recompute` reconstruye; reversa = marcar
  REVERSADA + recompute (idempotente).
- **Snapshot congelado**: el contrato congela el producto/versión al originar.
- **Contabilidad balanceada**: todo asiento debe=haber; la reversa contra-asienta, no borra.
- **Cuatro-ojos / N-ojos** configurable en Configuraciones → Workflow (permiso `configuraciones:workflow:write`);
  el emisor no aprueba. La definición vive allá; la ejecución (`pp_workflow_aprobacion`) acá.

## QA (obligatorio) — ver también memoria `qa-profundo-siempre`
- No alcanza la UI: verificar **persistencia real en la DB** tras cada mutación y probar las **altas
  contra Postgres** (incluida la carrera borrar-y-recrear y concurrente), no sólo con SQLite en verde.
- Todo bug encontrado suma su **test de regresión** (pytest en el backend, Vitest en
  `frontend/src/modules/creditos`) y su entrada en `salida/hallazgos.md`. Al mutar producción en QA, **limpiar los datos demo** después.
- El backup es de **producción viva**: fechas 2026 son reales; las claves nunca se migraron (hash
  irreversible) — no recuperarlas.

## Operación
- Backend + DB en Docker (compose de la raíz): `docker compose run --rm creditos python -m pytest -q`;
  tras cambios, `docker compose up -d --build creditos`. Tablas `pp_*` nuevas se crean solas al arrancar.
- DB Postgres: usuario/clave/base `ccypp`. En producción sólo existe el usuario `admin` (los flujos
  cuatro-ojos con otros perfiles se prueban por pytest/SQLite).
