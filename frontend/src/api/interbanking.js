import api from "./client";

// Config
export const getConfig = () => api.get("/interbanking/config").then((r) => r.data);
export const saveConfig = (data) => api.post("/interbanking/config", data).then((r) => r.data);
export const testConfig = (data) => api.post("/interbanking/config/test", data).then((r) => r.data);
export const getTokenStatus = () => api.get("/interbanking/config/token-status").then((r) => r.data);

// Cuentas
export const getCuentas = () => api.get("/interbanking/cuentas").then((r) => r.data);
export const getSaldo = (cuentaId) => api.get(`/interbanking/cuentas/${cuentaId}/saldo`).then((r) => r.data);

// Transferencias
export const validarCBU = (cbu_or_alias) =>
  api.post("/interbanking/transferencias/validar", { cbu_or_alias }).then((r) => r.data);
export const iniciarTransferencia = (data) =>
  api.post("/interbanking/transferencias/iniciar", data).then((r) => r.data);
export const getEstadoTransferencia = (id) =>
  api.get(`/interbanking/transferencias/${id}/estado`).then((r) => r.data);
export const getTransferencias = (params = {}) =>
  api.get("/interbanking/transferencias", { params }).then((r) => r.data);

// Pagos en lote
export const getLotes = (params = {}) => api.get("/interbanking/pagos/lotes", { params }).then((r) => r.data);
export const getLote = (id) => api.get(`/interbanking/pagos/lotes/${id}`).then((r) => r.data);
export const getLoteItems = (id) => api.get(`/interbanking/pagos/lotes/${id}/items`).then((r) => r.data);
export const createLote = (data) => api.post("/interbanking/pagos/lotes", data).then((r) => r.data);
export const procesarLote = (id) => api.post(`/interbanking/pagos/lotes/${id}/procesar`).then((r) => r.data);
export const getEstadoLote = (id) => api.get(`/interbanking/pagos/lotes/${id}/estado`).then((r) => r.data);

// Auditoría
export const getAuditoria = (params = {}) =>
  api.get("/interbanking/auditoria", { params }).then((r) => r.data);
export const getAuditoriaEntry = (id) =>
  api.get(`/interbanking/auditoria/${id}`).then((r) => r.data);
export const exportAuditoria = (params = {}) =>
  api.get("/interbanking/auditoria/export", { params, responseType: "blob" });
