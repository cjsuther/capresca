import api from "./client";

// Config
export const getConfig = () => api.get("/interbanking/config").then((r) => r.data);
export const saveConfig = (data) => api.post("/interbanking/config", data).then((r) => r.data);
export const testConfig = (data, scope) =>
  api.post("/interbanking/config/test", data, { params: scope ? { scope } : {} }).then((r) => r.data);
export const getTokenStatus = () => api.get("/interbanking/config/token-status").then((r) => r.data);

// Cuentas (API Interbanking - Información Financiera)
export const getCuentas = (params = {}) =>
  api.get("/interbanking/cuentas", { params }).then((r) => r.data);
export const getCuenta = (accountNumber, params = {}) =>
  api.get(`/interbanking/cuentas/${accountNumber}`, { params }).then((r) => r.data);
export const getSaldos = (params = {}) =>
  api.get("/interbanking/cuentas/saldos", { params }).then((r) => r.data);

// Transferencias
export const listarTransferencias = (params = {}) =>
  api.get("/interbanking/transferencias", { params }).then((r) => r.data);
export const crearTransferencia = (data) =>
  api.post("/interbanking/transferencias", data).then((r) => r.data);
export const validarCBU = (cbu_or_alias) =>
  api.post("/interbanking/transferencias/validar", { cbu_or_alias }).then((r) => r.data);
export const getEstadoTransferencia = (id) =>
  api.get(`/interbanking/transferencias/${id}/estado`).then((r) => r.data);
export const getTransferenciasLocal = (params = {}) =>
  api.get("/interbanking/transferencias/local", { params }).then((r) => r.data);

// Auditoría
export const getAuditoria = (params = {}) =>
  api.get("/interbanking/auditoria", { params }).then((r) => r.data);
export const getAuditoriaEntry = (id) =>
  api.get(`/interbanking/auditoria/${id}`).then((r) => r.data);
export const exportAuditoria = (params = {}) =>
  api.get("/interbanking/auditoria/export", { params, responseType: "blob" });
