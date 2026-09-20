# Inventario de tablas DBF disponibles (código CCyPP)

> Barrido completo del árbol. **18 DBF reales** (no hay DBC ni drives de red
> montados). Nota: los `.scx/.frx/.vcx/.pjx` de FoxPro son internamente formato
> DBF, pero no son bases de datos de negocio.

## Datos de producción reales (útiles para ETL y validación)

| Archivo | Registros | Qué contiene | Uso en la migración |
|---|---:|---|---|
| `prgs/tmpdev.DBF` | 2.655.268 | Cuotas + solicitud + cliente (desnormalizado, hasta 2020) | ✅ Ya usado: calibración del motor francés |
| `ivacob.DBF` | 29.084 | Cuotas **cobradas con mora** (INTERES_PU, IVA_PUNI, INTERES_RE) | ⭐ Validar el **motor de mora** (punitorios/resarcitorios) |
| `pp.DBF` | 65.332 | Padrón de haberes: NRO_AGENTE, CUIL, APEYNOM, REMUIMPO (rem. imponible) | Validar **margen de afectación** (sueldo real) · ⚠️ PII |
| `ls082021.DBF` | 63.070 | Liquidación de sueldos 08/2021 (mismo layout que pp) | Haberes por período · ⚠️ PII |
| `tmpls.DBF` | 63.070 | Liquidación de sueldos (temporal) | ídem · ⚠️ PII |
| `dup.DBF` | 3.420 | Duplicados/depuración de haberes | Análisis de calidad de datos |
| `gasegre.DBF` | 1.756 | **Solicitudes con garantes** (SO_CUIL, GA/G2/G3_CUIL) | Referencia para el módulo Solicitudes |
| `Querys/ctapagproducir.dbf` | 445 | Cuotas de la línea PRODUCIR | Caso de prueba adicional |
| `cr146189.DBF` | 48 | Cuotas de un crédito puntual | Caso de prueba |
| `turnos_erroneos.DBF` | 26 | Turnos con error (mesa de entradas) | — |
| `Docs/AGE_CBU.DBF` | 54 | CBU por agencia/subagencia | Tabla maestra chica |

## Archivos internos de FoxPro (no son datos de negocio)

| Archivo | Qué es |
|---|---|
| `ccypp_sistema.DBF` / `_ref.DBF` | Tabla de **proyecto** VFP (.pjx) y sus referencias |
| `copiares.dbf` | Metadatos de estructura de campos |
| `FoxyPreviewer_Settings.dbf` | Config del visor de reportes |
| `FOXUSER.DBF` | Archivo de recursos de VFP |
| `mantenimiento.DBF` | 1 registro, log de mantenimiento |

## ⚠️ Seguridad

- `Apis_Consultas_VFP/apis.dbf` (4 registros) contiene **CLIENT_ID, CLIENT_SEC
  y TOKEN** de las APIs en texto plano. Sumado al `ClientSecret` hardcodeado en
  `login1.prg`/`set_class.prg`, refuerza la necesidad de **rotar credenciales**
  y externalizar secretos. No se transcriben aquí sus valores.
- Las tablas de haberes (`pp`, `ls082021`, `tmpls`, `dup`) contienen **datos
  personales de ~63.000 agentes públicos** (CUIL, nombre, remuneración).
  Tratar como PII: acceso restringido, no exportar fuera del entorno seguro.
