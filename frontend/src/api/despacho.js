import api from "./client";

// ── Series de numeración: cada área lleva su propio correlativo ──
export const getSeries = () =>
  api.get("/despacho/series").then((r) => r.data);

// ── Modelos (plantillas) de resoluciones y disposiciones ──
export const getModelos = (params = {}) =>
  api.get("/despacho/modelos", { params }).then((r) => r.data);

export const crearModelo = (data) =>
  api.post("/despacho/modelos", data).then((r) => r.data);

export const editarModelo = (id, data) =>
  api.put(`/despacho/modelos/${id}`, data).then((r) => r.data);

// ── Resoluciones y disposiciones ──
export const getResoluciones = (params = {}) =>
  api.get("/despacho/resoluciones", { params }).then((r) => r.data);

export const getResolucion = (id) =>
  api.get(`/despacho/resoluciones/${id}`).then((r) => r.data);

export const crearResolucion = (data) =>
  api.post("/despacho/resoluciones", data).then((r) => r.data);

export const editarResolucion = (id, data) =>
  api.put(`/despacho/resoluciones/${id}`, data).then((r) => r.data);

export const firmarResolucion = (id) =>
  api.post(`/despacho/resoluciones/${id}/firmar`).then((r) => r.data);

/** Carga el N° oficial, que llega después del correlativo. */
export const cargarNumeroReal = (id, fecha_real) =>
  api.post(`/despacho/resoluciones/${id}/numero-real`, { fecha_real }).then((r) => r.data);

export const anularResolucion = (id, motivo) =>
  api.post(`/despacho/resoluciones/${id}/anular`, { motivo }).then((r) => r.data);

export const descargarWord = (id) =>
  api.get(`/despacho/resoluciones/${id}/word`, { responseType: "blob" }).then((r) => r.data);

// ── Anexo: las solicitudes que otorga una resolución ──
export const getTiposAnexo = () =>
  api.get("/despacho/anexo/tipos").then((r) => r.data);

export const getSolicitudesAnexo = (params) =>
  api.get("/despacho/anexo/solicitudes", { params }).then((r) => r.data);

export const asignarAnexo = (data) =>
  api.post("/despacho/anexo/asignar", data).then((r) => r.data);

// El número de resolución va para que Despacho verifique que el instrumento siga en borrador.
export const quitarDelAnexo = (solicitud_ids, numero_resolucion) =>
  api.post("/despacho/anexo/quitar", { solicitud_ids, numero_resolucion }).then((r) => r.data);

export const descargarAnexoWord = (resolucionId) =>
  api.get(`/despacho/anexo/word/${resolucionId}`, { responseType: "blob" }).then((r) => r.data);

// ── Expedientes y pases ──
export const getExpedientes = (params = {}) =>
  api.get("/despacho/expedientes", { params }).then((r) => r.data);

export const getExpediente = (id) =>
  api.get(`/despacho/expedientes/${id}`).then((r) => r.data);

export const getExpedientesPorOficina = () =>
  api.get("/despacho/expedientes-por-oficina").then((r) => r.data);

export const crearExpediente = (data) =>
  api.post("/despacho/expedientes", data).then((r) => r.data);

export const pasarExpediente = (id, data) =>
  api.post(`/despacho/expedientes/${id}/pase`, data).then((r) => r.data);

export const archivarExpediente = (id) =>
  api.post(`/despacho/expedientes/${id}/archivar`).then((r) => r.data);

// ── Importación del sistema anterior ──
export const subirDespacho = (archivo, onProgreso) => {
  const f = new FormData();
  f.append("file", archivo);
  return api.post("/despacho/importaciones", f, {
    headers: { "Content-Type": "multipart/form-data" },
    // Sin el límite general de 15 s: el backup son ~26 MB y subirlo lleva bastante más que eso.
    // El servidor responde apenas termina de recibirlo; el procesado va en segundo plano.
    timeout: 0,
    onUploadProgress: (e) => onProgreso?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  }).then((r) => r.data);
};

export const getImportaciones = () =>
  api.get("/despacho/importaciones").then((r) => r.data);

export const getImportacion = (id) =>
  api.get(`/despacho/importaciones/${id}`).then((r) => r.data);
