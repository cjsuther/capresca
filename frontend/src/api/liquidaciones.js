import api from "./client";

export const processZip = (zipPath) =>
  api.post("/liquidaciones/process", { zip_path: zipPath }).then((r) => r.data);

export const uploadZip = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/liquidaciones/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then((r) => r.data);
};

export const getBatches = (params) =>
  api.get("/liquidaciones/batches", { params }).then((r) => r.data);

export const getBatch = (id) =>
  api.get(`/liquidaciones/batches/${id}`).then((r) => r.data);

export const getBatchDetalle = (id, agency) =>
  api.get(`/liquidaciones/batches/${id}/detalle`, { params: agency ? { agency } : {} }).then((r) => r.data);

export const getBatchValidaciones = (id) =>
  api.get(`/liquidaciones/batches/${id}/validaciones`).then((r) => r.data);

export const getBatchArchivos = (id) =>
  api.get(`/liquidaciones/batches/${id}/archivos`).then((r) => r.data);

export const getArchivoUrl = (batchId, archivoId) =>
  `/api/liquidaciones/batches/${batchId}/archivos/${archivoId}`;

export const retryConciliacion = (id) =>
  api.post(`/liquidaciones/batches/${id}/retry-conciliacion`).then((r) => r.data);
