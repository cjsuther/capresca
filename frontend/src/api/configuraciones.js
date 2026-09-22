import api from "./client";

// Módulo Configuraciones: impuestos, índices de referencia, feriados y workflow de aprobaciones.
const B = "/configuraciones";
const data = (p) => p.then((r) => r.data);

/** Texto del error de la API: `detail` string, o el primer error de validación (422 de FastAPI). */
export function mensajeDeError(err, porDefecto = "No se pudo completar la operación") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) {
    const e = d[0];
    const campo = Array.isArray(e?.loc) ? e.loc[e.loc.length - 1] : "";
    return campo ? `${campo}: ${e.msg}` : e.msg;
  }
  return porDefecto;
}

// ── Impuestos ──
export const listarImpuestos = (estado = "todos") => data(api.get(`${B}/impuestos`, { params: { estado } }));
export const crearImpuesto = (d) => data(api.post(`${B}/impuestos`, d));
export const editarImpuesto = (id, d) => data(api.put(`${B}/impuestos/${id}`, d));
export const bajaImpuesto = (id) => data(api.post(`${B}/impuestos/${id}/baja`));
export const reactivarImpuesto = (id) => data(api.post(`${B}/impuestos/${id}/reactivar`));

// ── Índices de referencia ──
export const listarIndices = (estado = "todos") => data(api.get(`${B}/indices`, { params: { estado } }));
export const crearIndice = (d) => data(api.post(`${B}/indices`, d));
export const editarIndice = (id, d) => data(api.put(`${B}/indices/${id}`, d));
export const bajaIndice = (id) => data(api.post(`${B}/indices/${id}/baja`));
export const reactivarIndice = (id) => data(api.post(`${B}/indices/${id}/reactivar`));

// ── Feriados ──
export const listarPaises = () => data(api.get(`${B}/feriados/paises`));
export const listarFeriados = (pais, anio) => data(api.get(`${B}/feriados`, { params: { pais, anio } }));
export const crearFeriado = (d) => data(api.post(`${B}/feriados`, d));
export const editarFeriado = (id, d) => data(api.put(`${B}/feriados/${id}`, d));
export const borrarFeriado = (id) => data(api.delete(`${B}/feriados/${id}`));
export const importarFeriados = (pais, anio) => data(api.post(`${B}/feriados/importar`, { pais, anio }));

// ── Workflow de aprobaciones ──
export const listarWorkflow = (modulo) => data(api.get(`${B}/workflow`, { params: modulo ? { modulo } : {} }));
export const editarRegla = (id, d) => data(api.put(`${B}/workflow/reglas/${id}`, d));
export const agregarNivel = (reglaId, d) => data(api.post(`${B}/workflow/reglas/${reglaId}/niveles`, d));
export const editarNivel = (id, d) => data(api.put(`${B}/workflow/niveles/${id}`, d));
export const borrarNivel = (id) => data(api.delete(`${B}/workflow/niveles/${id}`));
export const agregarOverride = (nivelId, d) => data(api.post(`${B}/workflow/niveles/${nivelId}/usuarios`, d));
export const borrarOverride = (id) => data(api.delete(`${B}/workflow/usuarios/${id}`));
