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

export function mensajeDeError(err, porDefecto = "No se pudo completar la operación") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) return d[0]?.msg || porDefecto;
  return porDefecto;
}
