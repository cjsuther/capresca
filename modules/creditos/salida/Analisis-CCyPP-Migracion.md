# Análisis del Sistema CCyPP — Ca.Pre.S.Ca.
### Base para plan de migración a stack moderno

> Documento de análisis técnico. Fecha: 2026-08-03.
> Fuente: `CCyPP-Desarrollo` (código Visual FoxPro).

---

## 1. Identificación del sistema

| Dato | Valor |
|---|---|
| Organización | **Ca.Pre.S.Ca.** — Caja de Prestaciones Sociales de Catamarca |
| Autor / proveedor | AGJSistemas (Alejandro Jorge Falca) |
| Antigüedad | Desarrollo original ~2001, en evolución continua hasta 2024 |
| Lenguaje / plataforma | **Visual FoxPro 9** (Windows) |
| Distribución | Ejecutable monolítico `ccypp-sistema.exe` (~39 MB) |
| Datos | Tablas **DBF/DBC** de FoxPro sobre **share de red** (`w:\`, `\\serversql\agjs`, `\\192.168.0.7\agjs`) |
| Naturaleza | ERP financiero de una caja de crédito y previsión social provincial |

Es un sistema de misión crítica: gestiona créditos a agentes públicos, cobranzas, caja/tesorería, seguros, contabilidad y liquidaciones, con descuento por planilla (débito sobre haberes).

---

## 2. Arquitectura actual (as-is)

```
┌─────────────────────────────────────────────┐
│  PCs de usuarios (Windows)                   │
│  ccypp-sistema*.exe  (VFP runtime embebido)  │
└───────────────┬─────────────────────────────┘
                │  SMB / file share (w:\)
┌───────────────▼─────────────────────────────┐
│  Servidor de archivos  \\serversql\agjs      │
│  DBC/DBF por módulo (Caja, Créditos, ...)    │
└───────────────┬─────────────────────────────┘
                │  proceso batch (ccypp-proceso.exe)
┌───────────────▼─────────────────────────────┐
│  PostgreSQL (192.168.0.7)  ← ya iniciado     │
│  Réplica del maestro de agentes/clientes     │
└─────────────────────────────────────────────┘
        ▲                    ▲
        │ OAuth2/REST        │ certificado .pfx
   API Intranet          SARH / RENAPER
   Catamarca (empleados,  (RRHH provincial,
   CUIL)                  identidad)
```

**Características clave:**
- **Monolito de escritorio** con motor de datos de archivos (no hay servidor de base de datos transaccional para el núcleo; la lógica corre en el cliente y bloquea registros sobre el share).
- **Menú y permisos data-driven**: las tablas `symdeperf` / `symdesec` definen los menús, popups y accesos por **perfil de usuario** (ADMG, xCJ caja, xCR créditos, xTE tesorería, xSE seguros, xCG contable, xDE despacho, xJU juegos, xAU/PE/PA mesa de entradas, xNT). El `mainagjs.prg` arma el menú dinámicamente desde la base.
- **Múltiples ejecutables paralelos**: hay decenas de `.exe` variantes (`_caja`, `_miriam`, `_sergio`, `_premios`, `_liq_especiales`, `_baja_fallecimiento`, etc.). Es *branching por feature/usuario a nivel de binario* — señal de fuerte deuda técnica y falta de control de versiones sobre releases.
- **Reportería**: FoxyPreviewer (`FoxyPreviewer.app`) + generación de PDF nativa (`libhpdf.dll`, `pdf3.prg` de ~1 MB) + integración con Word/Outlook/Excel (`owordclass.vcx`, `outlook.vcx`, `excelx.vcx`).

---

## 3. Módulos funcionales

Cada módulo tiene su propio contenedor de base de datos (DBC). El perfil del usuario determina qué DBCs abre el login.

| Módulo | Base (DBC) | Función |
|---|---|---|
| **General** | `agjsgeneral` | Maestros compartidos: clientes/agentes (`maeclientes`, `maestrodio`), usuarios, parámetros |
| **Seguridad** | `symdesec` | Perfiles, menús, accesos (`symdeperf`) |
| **Créditos** | `agjscreditos` | Solicitudes, líneas de crédito, requisitos, pagarés, liquidación de créditos, cuotas, mora |
| **Caja / Tesorería** | `agjscaja` | Cobranzas, recibos, cierre de caja, control de caja, pagos, arqueo |
| **Contabilidad** | `agjscontable` | Asientos (devengamiento, otorgamiento), IVA, comprobantes |
| **Egresos** | `agjsegresos` | Órdenes de pago, egresos, devoluciones |
| **Despacho** | `agjsdespacho` | Resoluciones, disposiciones, notas, pases, expedientes |
| **Mesa de entradas** | `agjsmesa` | Trámites, turnos, recepción |
| **Seguros** | `agjsseguros` | Pólizas, seguros de vida sobre créditos, liquidación de seguros |
| **Juegos** | `agjsjuegos` | Premios / jugadas (lotería/bingo social — `maejugadas`, `mibingo`) |
| **Personal** | (path `w:\Personal`) | RRHH interno, tardanzas |

**Distribución del código por familia de pantalla** (prefijo numérico del menú):
- `1xx` Despacho / resoluciones · `2xx` (220/225/230) Caja y sus listados · `3xx` (305–335) Créditos (config, solicitudes, liquidación) · `4xx` Contabilidad/Egresos · `5xx` Despacho/notas/pases · `7xx`–`8xx` Personal/Seguros/Juegos · `9xx` Utilidades y tablas de sistema.

---

## 4. Modelo de datos (inferido del código)

Los DBC/DBF **no están en el repo** (viven en el share `w:\`), pero el código revela el esquema. Tablas núcleo:

**Clientes / agentes** (`maeclientes`, `maestrodio` — maestro de descuento por planilla / DIO):
`cidcliente`, `ccuil`, `capenom` (apellido y nombre), `edni/ndoc`, `fnacim`, `csexo`, `cdomicilio`, `cbarrio`, `clocalidad`, `norgano` (organismo), `corga`, `ncatfun`, `ffperm/fingre` (ingreso), `nsueldo/nhaberbruto`, `ldebauto` (débito automático), `ccbucta` (CBU), `lbaja`, `fecbaja`, `cmotbaja`, `ntipocli`.

**Créditos**: `solicitud`, `hisolicitud` (histórico), `pagare`, `maecuotas` (plan de cuotas), `crcliact` (créditos activos por cliente), `cajacreseg` (crédito+seguro), `liqsegur`, `recleg`, `decjur` (declaración jurada).

**Caja**: `cajaliq`, `cajapagos`, `cajaforpag` (formas de pago), `cierrec` (cierre).

**Otros**: `egresos`, `liquidaciones`, `maejugadas`, `turnos`, `mtramites`, `v_agentes`/`v_crcliact` (vistas), `age_cbu` (CBU de agencias).

> Estimación: **decenas de tablas por módulo**, cientos en total. El detalle exacto de campos/índices se obtiene cuando se tenga acceso al share `w:\` (o a un backup de los DBC).

---

## 5. Formularios (734 `.scx`)

734 pantallas VFP. Nomenclatura por código de menú (`frm<código>...`). Ejemplos representativos:
- Créditos: `consulta_solicitudes`, `frm305050000lineas` (líneas), `frm305150000requisitos`, `frm320*` (alta/consulta cliente y solicitud), `frm330100000reimpliq` (reimpresión liquidación).
- Caja: `frm225050000aplicativodeCaja`, `frm225300000ctrlcaj` (control de caja), `frm225350000cierrec` (cierre), `frm225250000anupago` (anulación de pago), `frm225150001pagcsj`.
- Contabilidad: `cb-crasientodevenga`, `cb-crasientootorga`, `cb-egivaegresos`, `cb-iva-a-pagar-periodo`.
- Despacho: `120050000reso_disp` (resoluciones/disposiciones), `520100000pasegral` (pases).

## 6. Reportes (487 `.frx` únicos)

Reportería extensa: recibos (`rpt225050000recibo*`), cierres de caja (`rpt225350000cierre*`), controles administrativos por rubro (`rpt225300000ctrl*`), listados de mora/pendientes, IVA cobrado por período, carteras y líneas, resoluciones, AFIP (`afip1130`, `comisiones afip`). Muchos exportan a PDF/Excel/Word.

---

## 7. Integraciones externas

| Integración | Detalle | Ubicación en código |
|---|---|---|
| **API Intranet Catamarca** | OAuth2 client-credentials; consulta de empleados públicos y CUIL | `login1.prg`, `set_class.prg`, `frm320100002cliente_api` |
| **RENAPER** | Validación de identidad (documentación en `API/`) | `Apis_Consultas_VFP/` |
| **SARH** (RRHH provincial) | Certificado cliente `.pfx` para consumo de servicios | `pfx_test_sarh_capresca.pfx` |
| **PostgreSQL** | Réplica del maestro de agentes (`v_agentes`) — migración ya iniciada | `Actualiza_Agentes_PostgreSql.prg`, `ccypp-proceso.prg` |
| **JSON** | Serialización propia | `qdfoxjson.prg` |
| **Ofimática** | Word / Outlook / Excel vía OLE | `owordclass.vcx`, `outlook.vcx`, `excelx.vcx` |

---

## 8. Lógica de negocio

Concentrada en tres librerías-programa muy grandes (candidatas prioritarias a portar):
- `set_class.prg` (240 KB) — clase `set_capresca`: seteo de ambiente, motor de cálculo de cuotas (capital, interés, IVA, seguro, gastos), integración API.
- `clases.prg` (230 KB) — clases de negocio generales.
- `capresca_class.prg` (174 KB) — reglas específicas de la caja.
- 25 bibliotecas visuales `.vcx` (`agjsclases`, `cpsc_comunes`, `proceso`, etc.).
- 135 programas batch en `prgs/` (conversiones, actualizaciones de mora, sincronizaciones, cierres).

---

## 9. Riesgos y deuda técnica (relevante para migrar)

1. **Seguridad — credenciales hardcodeadas**: el `ClientId`/`ClientSecret` de la API de Catamarca están en texto plano en `login1.prg` y `set_class.prg`. Deben rotarse y externalizarse (secreto de entorno) en el nuevo sistema. *(Recomiendo tratarlo aparte, incluso antes de migrar.)*
2. **Datos sobre file share**: sin motor transaccional real para el núcleo → riesgo de corrupción, bloqueos, integridad referencial débil, límites de concurrencia. Ya hay síntomas (`atfixdbffpt.prg`, tablas `_corrupted`, utilidades de reparación).
3. **Proliferación de ejecutables/branches** (`_miriam`, `_sergio`, `_caja`, `_premios`…): no hay una única línea de verdad; hay que consolidar la lógica antes o durante la migración.
4. **Lógica en el cliente**: reglas de negocio embebidas en formularios y clases VFP; hay que extraerlas a servicios.
5. **Dependencia de Windows/OLE/DLLs** (`libhpdf`, `vfp2c32.fll`, ActiveX/OCX): la reportería y ofimática requieren reimplementación.
6. **Conocimiento tribal**: nomenclatura críptica (campos `c*`/`n*`/`l*`), sin documentación de esquema. Riesgo de dependencia del proveedor original.

---

## 10. Stack destino elegido

| Capa | Tecnología |
|---|---|
| Backend / API | **Python 3.12 + FastAPI** (REST, OpenAPI autogenerado, Pydantic v2) |
| ORM / migraciones | **SQLAlchemy 2.0 + Alembic** |
| Base de datos | **PostgreSQL** (ya adoptado por el equipo) |
| Frontend | **React** (SPA; sugerido Vite + TypeScript) |
| Empaquetado / entorno | **Docker + docker-compose** (dev y prod) |
| Reportería | **Motor server-side en Python**: WeasyPrint/ReportLab (PDF), openpyxl (Excel) — reimplementa los `.frx` |
| Tareas batch | **Celery + Redis** o APScheduler (reemplaza `prgs/` y `ccypp-proceso`) |
| Auth | **OAuth2/JWT** en FastAPI, replicando el modelo de perfiles `symdeperf` como RBAC |
| Testing | **pytest** (incluye pruebas de equivalencia numérica contra el sistema VFP) |

**Restricción de partida:** trabajamos **solo con el código fuente**, sin los DBC/DBF reales. Por lo tanto, la primera pieza de valor es **reconstruir el esquema por ingeniería inversa del código VFP**, y solo se accederá a los datos reales al momento del ETL (fase de datos), que dependerá de que Ca.Pre.S.Ca. provea un backup.

---

## 11. Plan de migración

Estrategia global: **Strangler Fig** — construir el nuevo sistema por dominios, dejando el `.exe` VFP en producción hasta apagar cada módulo. Arquitectura backend en **capas por dominio** (Créditos, Caja, Contabilidad, Seguros, Despacho, Mesa, Juegos, General/Seguridad), cada una con sus modelos, servicios y routers FastAPI.

### Fase 0 — Descubrimiento y aseguramiento (2–4 semanas)
- **Rotar las credenciales** expuestas (`ClientSecret` de API Intranet) — acción inmediata e independiente.
- Ingeniería inversa del **esquema**: parsear referencias a tablas/campos en `.prg`, `.scx`, `.frx` y las clases grandes → catálogo de entidades y campos (nombre, tipo inferido, uso). *Automatizable con scripts.*
- Inventariar **reglas de negocio** en `set_class.prg`, `clases.prg`, `capresca_class.prg` (motor de cuotas, interés, IVA, seguros, mora).
- Priorizar módulos/reportes/forms por **uso real** (descartar variantes muertas y los `.exe` branch).
- Entregable: modelo de datos preliminar + backlog priorizado + repo con Docker/CI base.

### Fase 1 — Fundaciones técnicas (2–3 semanas)
- Scaffolding: monorepo (`backend/` FastAPI, `frontend/` React, `infra/` Docker), `docker-compose` con Postgres + Redis.
- Modelo relacional en PostgreSQL (SQLAlchemy + Alembic) a partir del esquema inferido; **consolidar maestros duplicados** `maeclientes` + `maestrodio` → una entidad `cliente/agente`.
- Auth OAuth2/JWT + RBAC portando perfiles `symdeperf`.
- Pipeline CI (lint, tests, build de imágenes).

### Fase 2 — Núcleo de dominio: motor de cálculo (3–5 semanas)
- Portar a servicios Python el **cálculo de cuotas** (capital, interés, IVA, seguro, gastos), mora y liquidaciones.
- **Pruebas de equivalencia**: casos reales corridos en VFP vs. Python deben coincidir al centavo (pytest con datasets de referencia). Es la pieza de mayor riesgo → se valida antes que la UI.

### Fase 3 — ETL de datos (depende de acceso a backup)
- Cuando Ca.Pre.S.Ca. provea un backup de los DBC: pipeline **DBF → PostgreSQL** (librería `dbfread`/`simpledbf` en Python) con validación, deduplicación y reconciliación de saldos.
- Ejecuciones de prueba repetibles + reporte de discrepancias.

### Fase 4 — Módulos por prioridad (iterativo, el grueso del proyecto)
Orden sugerido por criticidad y dependencias:
1. **General / Seguridad** (usuarios, clientes, parámetros) — base de todo.
2. **Créditos** (solicitudes, líneas, requisitos, pagarés, cuotas, mora).
3. **Caja / Tesorería** (cobranzas, recibos, cierre y control de caja).
4. **Contabilidad / Egresos** (asientos, IVA, órdenes de pago).
5. **Seguros** (pólizas, seguro sobre crédito, liquidación).
6. **Despacho / Mesa de entradas** (resoluciones, pases, trámites, turnos).
7. **Juegos** (premios).

Cada módulo: modelos → servicios → API → UI React → reportes del módulo → pruebas → puesta en paralelo.

### Fase 5 — Reportería (transversal a la Fase 4)
- Reimplementar los reportes **priorizados por uso** (muchos de los 487 son variantes/reimpresiones). Motor Python: PDF (WeasyPrint/ReportLab), Excel (openpyxl).

### Fase 6 — Integraciones (transversal)
- API Intranet Catamarca (OAuth2), RENAPER, SARH (certificado `.pfx`) con **gestión segura de secretos** (variables de entorno / secret manager, nunca en código).

### Fase 7 — Convivencia, corte y salida
- Paralelo controlado por módulo (VFP + nuevo), reconciliación diaria.
- Corte definitivo por dominio; apagado progresivo del `.exe`.
- Documentación, capacitación, plan de rollback.

### Estimación gruesa
Un proyecto de este tamaño (734 forms, 487 reportes, 11 módulos, motor financiero) es de **~12–24 meses** según equipo. El valor se entrega incremental por módulo desde la Fase 4.

---

## Próximos pasos inmediatos

1. **Rotar las credenciales** expuestas en `login1.prg` / `set_class.prg` (independiente de todo lo demás).
2. Arrancar **Fase 0**: puedo generar ahora el **script de ingeniería inversa del esquema** (extraer tablas/campos usados desde `.prg`/`.scx`) para producir el catálogo de datos preliminar.
3. **Gestionar con Ca.Pre.S.Ca. un backup de los DBC** — bloqueante solo para la Fase 3 (ETL), no para empezar backend/UI.
4. Definir el **equipo y el módulo piloto** (recomiendo General/Seguridad + un flujo de Créditos como vertical de extremo a extremo).

---

## ESTADO REAL DE EJECUCIÓN (actualizado 2026-08-04)

> Documentos vivos: [estado-migracion.md](salida/estado-migracion.md) (mapeo
> pantalla→nuevo), [analisis-brechas.md](salida/analisis-brechas.md) (377
> pantallas), [hallazgos.md](salida/hallazgos.md) (descubrimientos),
> [catalogo_real.md](salida/catalogo_real.md) (esquema real).

### Lo construido (stack Python/FastAPI + React + PostgreSQL/SQLite + Docker)
- **Fundación**: API FastAPI, auth JWT + RBAC por perfil, Docker, 12 routers.
- **Motor financiero** portado y **validado contra 400k cuotas reales**
  (cuotas, mora, margen, carteras) — ver hallazgos H-003, H-004, H-005, H-010.
- **Módulos con funcionalidad**: Créditos (solicitud, otorgamiento, cobranza,
  consultas, ABMs), Caja (cobranza, cierre, control, anulación), Contabilidad
  (asientos automáticos, libro diario, IVA), Tesorería (OP, chequeras), Seguros
  (pólizas, liquidación, regímenes especiales), Despacho (resoluciones +Word,
  expedientes), Mesa (turnos), Tablas/Maestros.
- **Reportería**: recibo, libro diario, cierre, control de caja, pendientes, IVA,
  cartera, padrón de débito (Excel), resoluciones (Word).
- **85 tests** en verde. Menú lateral moderno por módulos.

### Fase 3 — ETL (backup real recibido y cargado)
- Esquema real: 9 módulos, **216 tablas, 62,6M registros**.
- Cargado a la base del sistema: **78.055 clientes, 398 líneas, 3.686 organismos,
  3.559 créditos, 202.140 cuotas, 1.057 beneficiarios de seguros**.

### Cobertura de pantallas (registro honesto)
- **~62/377 construido (16%)** + 4 requieren extensión de modelo + variantes.
- El grueso pendiente: informes/consultas de Créditos (120), Juegos/Quiniela (32),
  Utilidades (28), y carga ETL de Caja/Egresos/Despacho.

### Lo que sigue
1. **Extender el modelo** con conceptos reales de `solicitud` (gastos originación,
   quebranto, previo pago, CFT, 4º garante) → desbloquea informes 🔷 (H-011).
2. **ETL de módulos restantes** (Caja/recibos, Egresos/OP, Despacho, Juegos).
3. **Cerrar brechas** de pantallas módulo por módulo, ahora con datos reales.
4. **Migrar a PostgreSQL** en Docker para producción (hoy corre en SQLite para
   validación local; el código es agnóstico vía SQLAlchemy).
