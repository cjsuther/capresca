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

export const getBoletaUrl = (recordId) =>
  `/api/conciliacion/records/${recordId}/boleta`;
