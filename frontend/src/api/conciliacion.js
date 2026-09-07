import api from "./client";

export const getConciliacion = (date) =>
  api.get("/conciliacion", { params: { date } }).then((r) => r.data);

export const getSummary = (date) =>
  api.get("/conciliacion/summary", { params: { date } }).then((r) => r.data);

export const getAgencies = () =>
  api.get("/conciliacion/agencies").then((r) => r.data);

export const getRecord = (id) =>
  api.get(`/conciliacion/records/${id}`).then((r) => r.data);

export const getHistory = (id) =>
  api.get(`/conciliacion/records/${id}/history`).then((r) => r.data);

export const updateRecord = (id, data) =>
  api.put(`/conciliacion/records/${id}`, data).then((r) => r.data);

export const assignAgency = (txType, txId, clientId) =>
  api.put(`/conciliacion/interbanking/${txType}/${txId}/agency`, { client_id: clientId }).then((r) => r.data);

export const removeLink = (linkId) =>
  api.delete(`/conciliacion/links/${linkId}`).then((r) => r.data);

// Descarga la boleta usando el cliente axios (que agrega el token) como blob,
// y dispara la descarga en el navegador. Un <a href> directo no lleva el JWT.
export const downloadBoleta = async (recordId) => {
  const res = await api.get(`/conciliacion/records/${recordId}/boleta`, {
    responseType: "blob",
  });
  const disposition = res.headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `boleta_${recordId}.pdf`;
  const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

export const getAdjustments = (id) =>
  api.get(`/conciliacion/records/${id}/adjustments`).then((r) => r.data);

export const addAdjustment = (id, amount, reason) =>
  api.post(`/conciliacion/records/${id}/adjustments`, { amount, reason }).then((r) => r.data);
