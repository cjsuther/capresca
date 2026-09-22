import api from "./client";

// Módulo Contabilidad: los módulos mandan transacciones y acá se definen y generan los asientos.
const B = "/contabilidad";
const data = (p) => p.then((r) => r.data);

export const resumenContable = () => data(api.get(`${B}/resumen`));

// Plan de cuentas, centros y diarios
export const listarCuentas = (params = {}) => data(api.get(`${B}/cuentas`, { params }));
export const crearCuenta = (d) => data(api.post(`${B}/cuentas`, d));
export const editarCuenta = (id, d) => data(api.put(`${B}/cuentas/${id}`, d));
export const listarDiarios = () => data(api.get(`${B}/diarios`));
export const listarCentros = () => data(api.get(`${B}/centros`));

// Ejercicios
export const listarEjercicios = () => data(api.get(`${B}/ejercicios`));
export const crearEjercicio = (d) => data(api.post(`${B}/ejercicios`, d));
export const cerrarEjercicio = (id) => data(api.post(`${B}/ejercicios/${id}/cerrar`));

// Definiciones (cómo se contabiliza cada transacción)
export const listarDefiniciones = (modulo = "") => data(api.get(`${B}/definiciones`, { params: { modulo } }));
export const crearDefinicion = (d) => data(api.post(`${B}/definiciones`, d));
export const editarDefinicion = (id, d) => data(api.put(`${B}/definiciones/${id}`, d));
export const probarDefinicion = (id, datos) => data(api.post(`${B}/definiciones/${id}/probar`, { datos }));

// Transacciones
export const listarTransacciones = (params = {}) => data(api.get(`${B}/transacciones`, { params }));
export const sinDefinir = () => data(api.get(`${B}/transacciones/sin-definir`));
export const verTransaccion = (id) => data(api.get(`${B}/transacciones/${id}`));
export const reprocesar = (params = {}) => data(api.post(`${B}/transacciones/reprocesar`, null, { params }));

// Asientos y libros
export const listarAsientos = (params = {}) => data(api.get(`${B}/asientos`, { params }));
export const verAsiento = (id) => data(api.get(`${B}/asientos/${id}`));
export const crearAsiento = (d) => data(api.post(`${B}/asientos`, d));
export const anularAsiento = (id, motivo) => data(api.post(`${B}/asientos/${id}/anular`, { motivo }));
export const libroMayor = (cuenta, params = {}) => data(api.get(`${B}/libros/mayor/${cuenta}`, { params }));
export const sumasYSaldos = (params = {}) => data(api.get(`${B}/libros/sumas-y-saldos`, { params }));
export const estadosContables = (params = {}) => data(api.get(`${B}/libros/estados`, { params }));
export const libroIva = (libro, params = {}) => data(api.get(`${B}/libros/iva/${libro}`, { params }));

// Entes contables
export const listarEmpresas = () => data(api.get(`${B}/empresas`));
export const crearEmpresa = (d) => data(api.post(`${B}/empresas`, d));
export const editarEmpresa = (id, d) => data(api.put(`${B}/empresas/${id}`, d));

// Plan y centros
export const borrarCuenta = (id) => data(api.delete(`${B}/cuentas/${id}`));
export const crearCentro = (d) => data(api.post(`${B}/centros`, d));
export const editarCentro = (id, d) => data(api.put(`${B}/centros/${id}`, d));

// Ejercicios
export const reabrirEjercicio = (id) => data(api.post(`${B}/ejercicios/${id}/reabrir`));
export const aperturaEjercicio = (id) => data(api.post(`${B}/ejercicios/${id}/apertura`));

// Asientos en borrador
export const publicarAsiento = (id) => data(api.post(`${B}/asientos/${id}/publicar`));
export const borrarAsiento = (id) => data(api.delete(`${B}/asientos/${id}`));

// Reportes
export const flujoEfectivo = (params = {}) => data(api.get(`${B}/libros/flujo-efectivo`, { params }));
export const posicionIva = (params = {}) => data(api.get(`${B}/libros/iva/posicion/periodo`, { params }));
export const porCentro = (params = {}) => data(api.get(`${B}/reportes/por-centro`, { params }));

// Conciliación bancaria
export const verConciliacion = (params = {}) => data(api.get(`${B}/conciliacion`, { params }));
export const cargarExtracto = (d) => data(api.post(`${B}/conciliacion/extracto`, d));
export const borrarExtracto = (id) => data(api.delete(`${B}/conciliacion/extracto/${id}`));
export const conciliar = (extracto_id, asiento_linea_id) =>
  data(api.post(`${B}/conciliacion/conciliar`, { extracto_id, asiento_linea_id }));
export const desconciliar = (id) => data(api.post(`${B}/conciliacion/desconciliar/${id}`));
export const conciliarAutomatica = (cuenta) => data(api.post(`${B}/conciliacion/automatica`, null, { params: { cuenta } }));

export function mensajeDeError(err, porDefecto = "No se pudo completar la operación") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) return d[0]?.msg || porDefecto;
  return porDefecto;
}
