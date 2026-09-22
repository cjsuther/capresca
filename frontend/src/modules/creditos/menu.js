// Menú del módulo Créditos.
//
// `heredada`: pantalla que viene del sistema VFP anterior. Por defecto NO se muestran: exigen el
// permiso `creditos:heredadas:read`, que no trae ningún rol. Visibles quedan las pantallas creadas en
// la migración (las que el menú original marcaba como "nuevas"). Para volver a habilitar las heredadas,
// en Seguridad se le asigna ese permiso al rol.
export const PERMISO_HEREDADAS = "heredadas:read";

export const MENU = [
  {
    label: "Trabajo", items: [
      { to: "tablero-cartera", label: "Tablero de cartera" },
      { to: "solicitudes-credito", label: "Solicitudes de crédito" },
      { to: "inbox-aprobaciones", label: "Inbox de aprobaciones" },
    ],
  },
  {
    label: "Configuración", items: [
      { to: "configurar", label: "Configurar Créditos" },
      { to: "lineas", label: "Líneas de crédito", heredada: true },
      { to: "parametros", label: "Parámetros de créditos" },
      { to: "sistema-calculos", label: "Sistema de cálculos" },
    ],
  },
  {
    label: "Consultas", items: [
      { to: "situacion", label: "Situación del cliente", heredada: true },
      { to: "situacion-linea", label: "Situación del cliente (línea nueva)" },
      { to: "cuenta-corriente", label: "Cuenta corriente", heredada: true },
      { to: "estadisticas", label: "Estadísticas de cartera", heredada: true },
      { to: "por-cartera", label: "Créditos por cartera", heredada: true },
      { to: "sin-debito", label: "Sin débito automático", heredada: true },
      { to: "pagos-caja", label: "Pagos en caja", heredada: true },
      { to: "envios", label: "Envíos (padrón de débito)", heredada: true },
      { to: "jubilados", label: "Jubilados / Ley 5094", heredada: true },
      { to: "turnos", label: "Turnos otorgados", heredada: true },
    ],
  },
  {
    label: "Operaciones", items: [
      { to: "solicitudes", label: "Solicitudes", heredada: true },
      { to: "cancelacion", label: "Cancelación de crédito", heredada: true },
      { to: "baja", label: "Baja de crédito", heredada: true },
      { to: "recalculo", label: "Recálculo de cuotas", heredada: true },
      { to: "simulador", label: "Simulador", heredada: true },
      { to: "liquidacion-lote", label: "Liquidación por lote" },
      { to: "caja", label: "Caja de créditos" },
      { to: "turnos-admin", label: "Turnos (generar / asignar)", heredada: true },
    ],
  },
  {
    label: "Reportes", items: [
      { to: "informe", label: "Informe de créditos", heredada: true },
      { to: "listado", label: "Listado de créditos", heredada: true },
      { to: "resumen-cobros", label: "Resumen de cobros" },
      { to: "mora", label: "Cuotas en mora", heredada: true },
      { to: "pendientes", label: "Pendientes de cobro", heredada: true },
    ],
  },
];

export const todosLosItems = () => MENU.flatMap((g) => g.items);

/** Rutas que sólo se ven con el permiso de las pantallas heredadas. */
export const RUTAS_HEREDADAS = new Set(todosLosItems().filter((i) => i.heredada).map((i) => i.to));
