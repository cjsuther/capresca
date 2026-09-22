// Menú del módulo Créditos: todas las pantallas están migradas al frontend del sistema.
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
      { to: "lineas", label: "Líneas de crédito" },
      { to: "parametros", label: "Parámetros de créditos" },
      { to: "sistema-calculos", label: "Sistema de cálculos" },
    ],
  },
  {
    label: "Consultas", items: [
      { to: "situacion", label: "Situación del cliente" },
      { to: "situacion-linea", label: "Situación del cliente (línea nueva)" },
      { to: "cuenta-corriente", label: "Cuenta corriente" },
      { to: "estadisticas", label: "Estadísticas de cartera" },
      { to: "por-cartera", label: "Créditos por cartera" },
      { to: "sin-debito", label: "Sin débito automático" },
      { to: "pagos-caja", label: "Pagos en caja" },
      { to: "envios", label: "Envíos (padrón de débito)" },
      { to: "jubilados", label: "Jubilados / Ley 5094" },
      { to: "turnos", label: "Turnos otorgados" },
    ],
  },
  {
    label: "Operaciones", items: [
      { to: "solicitudes", label: "Solicitudes" },
      { to: "cancelacion", label: "Cancelación de crédito" },
      { to: "baja", label: "Baja de crédito" },
      { to: "recalculo", label: "Recálculo de cuotas" },
      { to: "simulador", label: "Simulador" },
      { to: "liquidacion-lote", label: "Liquidación por lote" },
      { to: "caja", label: "Caja de créditos" },
      { to: "turnos-admin", label: "Turnos (generar / asignar)" },
    ],
  },
  {
    label: "Reportes", items: [
      { to: "informe", label: "Informe de créditos" },
      { to: "listado", label: "Listado de créditos" },
      { to: "resumen-cobros", label: "Resumen de cobros" },
      { to: "mora", label: "Cuotas en mora" },
      { to: "pendientes", label: "Pendientes de cobro" },
    ],
  },
];

export const todosLosItems = () => MENU.flatMap((g) => g.items);
