export type Item = { to: string; label: string; nuevo?: boolean };  // nuevo = opción creada en la migración
export type Grupo = { label: string; items: Item[] };   // submenú (Datos, Procesos, Reportes…)
// `oculto`: módulo escondido por defecto; sólo un administrador puede revelarlo con el botón del sidebar.
// `soloNuevos`: en este módulo sólo se muestran las opciones `nuevo`; las heredadas del legacy quedan
// ocultas por defecto y el administrador las revela con el mismo botón.
export type Modulo = { label: string; icon: string; grupos: Grupo[]; oculto?: boolean; soloNuevos?: boolean };

// Estructura de DOS niveles según el MENÚ REAL (symdeperf, perfil ADMG):
// Módulo → Submenú (Archivos/Datos/Consultas/Procesos/Reportes/Parámetros) → Pantalla.
// Ver salida/menu-real.md. Orden: 1 Despacho … X General.
export const MENU: Modulo[] = [
  {
    label: "Clientes", icon: "clientes", grupos: [
      { label: "Consultas", items: [
        { to: "/clientes/vision-360", label: "Visión 360° del cliente" },
      ] },
      { label: "Archivos", items: [
        { to: "/clientes/maestro", label: "Maestro de clientes (ABM)" },
      ] },
    ],
  },
  {
    label: "Despacho", icon: "despacho", oculto: true, grupos: [
      { label: "Archivos", items: [
        { to: "/despacho/modelos", label: "Modelos de resoluciones", nuevo: true },
      ] },
      { label: "Datos", items: [
        { to: "/despacho/resoluciones", label: "Resoluciones y disposiciones", nuevo: true },
        { to: "/despacho/anexos", label: "Anexo de resolución" },
        { to: "/despacho/expedientes", label: "Expedientes y pases" },
      ] },
    ],
  },
  {
    label: "Caja", icon: "caja", oculto: true, grupos: [
      { label: "Procesos", items: [
        { to: "/caja/quiniela", label: "Aplicativo de caja (quiniela)" },
        { to: "/caja/cobranza", label: "Cobranza (créditos, seguros)" },
        { to: "/caja/control", label: "Control de caja" },
        { to: "/caja/deuda-agencia", label: "Deuda de agencia" },
        { to: "/caja/agencia-historico", label: "Histórico de agencia" },
      ] },
      { label: "Reportes", items: [
        { to: "/caja/cobranzas-periodo", label: "Cobranzas en un período" },
        { to: "/caja/ingresos-brutos", label: "Ingresos brutos" },
        { to: "/caja/recaudacion-anual", label: "Recaudación anual" },
        { to: "/caja/liquidaciones-cobradas", label: "Liquidaciones cobradas (día)" },
        { to: "/caja/intereses-iva", label: "Intereses e IVA (mensual)" },
        { to: "/caja/planilla-contable", label: "Planilla contable (créditos/día)" },
        { to: "/caja/pagos-realizados", label: "Pagos realizados" },
        { to: "/caja/premios", label: "Premios de quiniela" },
        { to: "/caja/cheques-agencias", label: "Cheques para agencias" },
        { to: "/caja/premios-compensados", label: "Premios compensados" },
        { to: "/caja/reimpresion-recibos", label: "Reimpresión de recibos" },
        { to: "/contabilidad/cierre", label: "Reimpresión de cierre de caja" },
        { to: "/caja/control", label: "Reimpresión control de cajero" },
      ] },
    ],
  },
  {
    label: "Créditos", icon: "creditos", soloNuevos: true, grupos: [
      { label: "Archivos", items: [
        { to: "/creditos/tablero-cartera", label: "Tablero de cartera", nuevo: true },
        { to: "/creditos/situacion-linea", label: "Situación del cliente", nuevo: true },
        { to: "/creditos/solicitudes-credito", label: "Solicitudes de crédito", nuevo: true },
        { to: "/creditos/liquidacion-lote", label: "Liquidación por lote", nuevo: true },
        { to: "/creditos/caja", label: "Caja de créditos", nuevo: true },
        { to: "/creditos/resumen-cobros", label: "Resumen de cobros", nuevo: true },
        { to: "/creditos/sistema-calculos", label: "Sistema de cálculos", nuevo: true },
        { to: "/creditos/configurar", label: "Configurar Créditos", nuevo: true },
        { to: "/creditos/lineas", label: "Líneas de crédito" },
      ] },
      { label: "Datos", items: [
        { to: "/creditos/solicitudes", label: "Solicitudes" },
        { to: "/creditos/simulador", label: "Simulador" },
        { to: "/creditos/jubilados", label: "Jubilados / Ley 5094" },
        { to: "/creditos/cancelacion", label: "Cancelación de crédito" },
        { to: "/creditos/baja", label: "Baja de crédito" },
      ] },
      { label: "Procesos", items: [
        { to: "/creditos/recalculo", label: "Recálculo de cuotas" },
        { to: "/creditos/turnos-admin", label: "Turnos (generar / asignar)" },
      ] },
      { label: "Consultas", items: [
        { to: "/creditos/situacion", label: "Situación del cliente" },
        { to: "/creditos/cuenta-corriente", label: "Cuenta corriente" },
        { to: "/creditos/estadisticas", label: "Estadísticas de cartera" },
        { to: "/creditos/por-cartera", label: "Créditos por cartera" },
        { to: "/creditos/turnos", label: "Turnos otorgados" },
        { to: "/creditos/sin-debito", label: "Sin débito automático" },
        { to: "/creditos/pagos-caja", label: "Pagos en caja" },
        { to: "/creditos/envios", label: "Envíos (padrón de débito)" },
      ] },
      { label: "Reportes", items: [
        { to: "/creditos/informe", label: "Informe de créditos" },
        { to: "/creditos/listado", label: "Listado de créditos" },
        { to: "/creditos/mora", label: "Cuotas en mora" },
        { to: "/creditos/pendientes", label: "Pendientes de cobro" },
      ] },
    ],
  },
  {
    label: "Juegos / Quiniela", icon: "juegos", oculto: true, grupos: [
      { label: "Archivos", items: [
        { to: "/juegos/maestro", label: "Maestro de juegos" },
        { to: "/juegos/sorteos", label: "Control de sorteos" },
        { to: "/juegos/liquidaciones", label: "Agencias y liquidaciones" },
      ] },
      { label: "Reportes", items: [
        { to: "/juegos/ingresos", label: "Ingresos por juego" },
        { to: "/juegos/fondo-garantia", label: "Fondo de garantía" },
      ] },
    ],
  },
  {
    label: "Mesa de Entradas", icon: "mesa", oculto: true, grupos: [
      { label: "Consultas", items: [
        { to: "/mesa/turnos", label: "Turnos" },
        { to: "/mesa/tramites", label: "Consulta de trámites" },
      ] },
      { label: "Reportes", items: [
        { to: "/mesa/ingresados", label: "Trámites ingresados" },
      ] },
    ],
  },
  {
    label: "Contabilidad", icon: "contabilidad", grupos: [
      { label: "Archivos", items: [
        { to: "/contabilidad/plan-cuentas", label: "Plan de cuentas", nuevo: true },
        { to: "/contabilidad/ejercicios", label: "Ejercicios contables", nuevo: true },
        { to: "/contabilidad/centros-costo", label: "Centros de costo", nuevo: true },
        { to: "/contabilidad/imputaciones", label: "Parametrización contable", nuevo: true },
        { to: "/contabilidad/impuestos", label: "Impuestos", nuevo: true },
        { to: "/contabilidad/indices", label: "Índices de referencia", nuevo: true },
        { to: "/contabilidad/feriados", label: "Feriados (calendario)", nuevo: true },
      ] },
      { label: "Asientos", items: [
        { to: "/contabilidad/asientos", label: "Asientos manuales", nuevo: true },
        { to: "/contabilidad/mayor", label: "Balance / Mayor (real)" },
        { to: "/contabilidad/libro-diario", label: "Libro diario (app)" },
        { to: "/contabilidad/balance", label: "Balance (asientos app)" },
      ] },
      { label: "Consultas", items: [
        { to: "/contabilidad/ctacte-credito", label: "Cta. cte. contable por crédito" },
        { to: "/contabilidad/general", label: "Contabilidad general (caja/juegos)" },
      ] },
      { label: "Reportes", items: [
        { to: "/contabilidad/estados", label: "Estados contables", nuevo: true },
        { to: "/contabilidad/conciliacion", label: "Conciliación bancaria", nuevo: true },
        { to: "/contabilidad/iva-cuotas", label: "IVA de cuotas cobradas (real)" },
        { to: "/contabilidad/iva", label: "IVA por período (app)" },
        { to: "/contabilidad/cierre", label: "Cierre de caja" },
      ] },
    ],
  },
  {
    label: "Seguros", icon: "seguros", oculto: true, grupos: [
      { label: "Archivos", items: [
        { to: "/seguros/titulares", label: "Titulares de seguro" },
      ] },
      { label: "Datos", items: [
        { to: "/seguros/polizas", label: "Pólizas y liquidación" },
        { to: "/seguros/regimenes", label: "Regímenes especiales" },
      ] },
      { label: "Reportes", items: [
        { to: "/seguros/adicional", label: "Seguro de vida adicional" },
        { to: "/seguros/informes", label: "Informes" },
      ] },
    ],
  },
  {
    label: "Tesorería", icon: "tesoreria", grupos: [
      { label: "Archivos", items: [
        { to: "/tesoreria/autorizaciones", label: "Cupos de OP (maestro)" },
        { to: "/tesoreria/ordenes", label: "Órdenes de pago" },
        { to: "/tesoreria/chequeras", label: "Chequeras" },
      ] },
      { label: "Consultas", items: [
        { to: "/tesoreria/egresos", label: "Busca transacciones de egresos" },
      ] },
      { label: "Reportes", items: [
        { to: "/tesoreria/reporte", label: "Reporte de OP (por tipo)" },
        { to: "/tesoreria/informe", label: "Informe de OP (generador)" },
        { to: "/tesoreria/cheques", label: "Cheques emitidos" },
      ] },
    ],
  },
  {
    label: "Adm. y Finanzas", icon: "finanzas", oculto: true, grupos: [
      { label: "Archivos", items: [
        { to: "/general/proveedores", label: "Proveedores" },
      ] },
    ],
  },
  {
    label: "General", icon: "general", grupos: [
      { label: "Archivos", items: [
        { to: "/general/parametros", label: "Parámetros generales" },
        { to: "/creditos/parametros", label: "Parámetros de créditos", nuevo: true },
        { to: "/general/organismos", label: "Organismos" },
        { to: "/general/oficinas", label: "Oficinas" },
        { to: "/general/companias", label: "Compañías de seguros" },
      ] },
    ],
  },
  {
    label: "Seguridad", icon: "seguridad", grupos: [
      // Usuarios, roles y permisos se administran en Seguridad de Portezuelo (módulo Créditos, por área).
      { label: "Auditoría", items: [
        { to: "/seguridad/auditoria", label: "Auditoría" },
        { to: "/seguridad/auditoria-cambios", label: "Auditoría de cambios", nuevo: true },
      ] },
      { label: "Workflow", items: [
        { to: "/seguridad/workflow", label: "Workflow de aprobaciones", nuevo: true },
      ] },
    ],
  },
  {
    label: "Controles de Versión", icon: "migradores", grupos: [
      { label: "Configurar Créditos", items: [
        { to: "/controles-version", label: "Modelo de datos · APIs · Cambios", nuevo: true },
        { to: "/controles-version/principios", label: "Principios de arquitectura", nuevo: true },
        { to: "/controles-version/principios-diseno", label: "Principios de diseño", nuevo: true },
        { to: "/controles-version/procesos", label: "Procesos de calidad", nuevo: true },
      ] },
      { label: "Migración de datos", items: [
        { to: "/controles-version/migradores", label: "Migradores (DBF → modelo)", nuevo: true },
        { to: "/controles-version/modelo-datos", label: "Modelo de datos (DER)", nuevo: true },
      ] },
    ],
  },
];

export const items = (m: Modulo): Item[] => m.grupos.flatMap((g) => g.items);
