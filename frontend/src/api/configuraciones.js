import api from "./client";

// Módulo Configuraciones: impuestos, índices de referencia, feriados y workflow de aprobaciones.
const B = "/configuraciones";
const data = (p) => p.then((r) => r.data);

/** Texto del error de la API: `detail` string, o el primer error de validación (422 de FastAPI). */
export function mensajeDeError(err, porDefecto = "No se pudo completar la operación") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (d && typeof d === "object" && !Array.isArray(d) && typeof d.mensaje === "string") return d.mensaje;
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
// Vista lista (reglas en serie, sólo lectura): lo que ejecutan hoy Créditos y Tesorería.
export const listarWorkflow = (modulo) => data(api.get(`${B}/workflow`, { params: modulo ? { modulo } : {} }));

// Workflow gráfico versionado. Borradores: permiso workflow:write, sin step-up (autosave).
// Publicar / retirar / habilitar: permiso workflow:publish + step-up (el modal lo pide el cliente).
const W = `${B}/workflow`;
export const catalogoWorkflow = () => data(api.get(`${W}/catalogo`));
export const listarProcesos = () => data(api.get(`${W}/procesos`));
export const verProceso = (id) => data(api.get(`${W}/procesos/${id}`));
export const verVersion = (id) => data(api.get(`${W}/versiones/${id}`));
export const crearBorrador = (procesoId, desde) => data(api.post(`${W}/procesos/${procesoId}/borrador`, desde ? { desde } : {}));
export const guardarBorrador = (id, d) => data(api.put(`${W}/versiones/${id}`, d));
export const descartarBorrador = (id) => data(api.delete(`${W}/versiones/${id}`));
export const publicarVersion = (id, nota) => data(api.post(`${W}/versiones/${id}/publicar`, nota ? { nota } : {}));
export const retirarVersion = (id) => data(api.post(`${W}/versiones/${id}/retirar`));
export const habilitarProceso = (id, habilitado) => data(api.post(`${W}/procesos/${id}/habilitado`, { habilitado }));
export const compararVersiones = (a, b) => data(api.get(`${W}/comparar`, { params: { a, b } }));

/** Problemas que devuelve la API al publicar (`detail.problemas`), como lista de textos. */
export function problemasDeError(err) {
  const p = err?.response?.data?.detail?.problemas;
  return Array.isArray(p) ? p.map((x) => (typeof x === "string" ? x : x?.mensaje)).filter(Boolean) : [];
}
