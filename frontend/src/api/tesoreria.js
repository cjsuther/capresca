import api from "./client";

// Módulo Tesorería: lotes de pagos (de Créditos, Conciliación o carga manual), aprobación y envío.
const B = "/tesoreria/lotes";
const data = (p) => p.then((r) => r.data);

export const listarLotes = (filtros = {}) => data(api.get(B, { params: filtros }));
export const verLote = (id) => data(api.get(`${B}/${id}`));
export const crearLote = (d) => data(api.post(B, d));
export const excluirPago = (id, pid, motivo) => data(api.post(`${B}/${id}/pagos/${pid}/excluir`, { motivo }));
export const incluirPago = (id, pid) => data(api.post(`${B}/${id}/pagos/${pid}/incluir`));
export const aprobarLote = (id) => data(api.post(`${B}/${id}/aprobar`));
export const rechazarLote = (id, motivo) => data(api.post(`${B}/${id}/rechazar`, { motivo }));
export const cuentasOrigen = () => data(api.get(`${B}/cuentas-origen`));
export const enviarLote = (id, cuentaOrigen) => data(api.post(`${B}/${id}/enviar`, { cuenta_origen: cuentaOrigen || null }));
export const actualizarLote = (id) => data(api.post(`${B}/${id}/actualizar`));
export const reintentarPago = (id, pid) => data(api.post(`${B}/${id}/pagos/${pid}/reintentar`));
export const reintentarFallidos = (id) => data(api.post(`${B}/${id}/reintentar-fallidos`));
// TXT para dar de alta las cuentas destino en Interbanking (todas las del lote o las de sus fallidos).
export const archivoAltaCuentas = (id, soloFallidos = false) =>
  data(api.post(`${B}/${id}/archivo-alta-cuentas`, { solo_fallidos: soloFallidos }));
export const resolverPago = (id, pid, resultado, observacion) =>
  data(api.post(`${B}/${id}/pagos/${pid}/resolver`, { resultado, observacion }));

// Órdenes de pago de créditos: resoluciones / disposiciones con sus lotes de Créditos.
const OP = "/tesoreria/ordenes-pago";
export const listarOrdenes = (filtros = {}) => data(api.get(OP, { params: filtros }));
export const verOrden = (id) => data(api.get(`${OP}/${id}`));
export const actosDisponibles = () => data(api.get(`${OP}/disponibles`));
export const confeccionarOrden = (actos) => data(api.post(OP, { actos }));
export const anularOrden = (id, motivo) => data(api.post(`${OP}/${id}/anular`, { motivo }));

/** Texto del error de la API: `detail` string, `detail.mensaje`, o el primer error de validación. */
export function mensajeDeError(err, porDefecto = "No se pudo completar la operación") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (d && typeof d === "object" && !Array.isArray(d) && d.mensaje) return d.mensaje;
  if (Array.isArray(d) && d.length) return d[0]?.msg || porDefecto;
  return porDefecto;
}
