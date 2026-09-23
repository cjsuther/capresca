import api from "./client";

// Módulo Auditoría: registro central de lo que hace cada usuario con la información del sistema.
const B = "/auditoria";
const data = (p) => p.then((r) => r.data);

export const listarEventos = (filtros = {}) => data(api.get(`${B}/eventos`, { params: filtros }));
export const verEvento = (id) => data(api.get(`${B}/eventos/${id}`));
export const resumenAuditoria = () => data(api.get(`${B}/eventos/resumen`));
export const historiaDeRegistro = (modulo, entidad, id) =>
  data(api.get(`${B}/registros/${modulo}/${entidad}/${encodeURIComponent(id)}`));

export function mensajeDeError(err, porDefecto = "No se pudo consultar la auditoría") {
  const d = err?.response?.data?.detail;
  return typeof d === "string" && d.trim() ? d : porDefecto;
}
