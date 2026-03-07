import api from "./client";

export const getClients = (params = {}) =>
  api.get("/clientes", { params }).then((r) => r.data);

export const searchClients = (q, page = 1) =>
  api.get("/clientes/search", { params: { q, page } }).then((r) => r.data);

export const createHumanClient = (data) =>
  api.post("/clientes/human", data).then((r) => r.data);

export const createLegalClient = (data) =>
  api.post("/clientes/legal", data).then((r) => r.data);

export const getClient = (id) =>
  api.get(`/clientes/${id}`).then((r) => r.data);

export const updateClient = (id, data) =>
  api.put(`/clientes/${id}`, data).then((r) => r.data);

export const updateHumanProfile = (id, data) =>
  api.put(`/clientes/${id}/human`, data).then((r) => r.data);

export const updateLegalProfile = (id, data) =>
  api.put(`/clientes/${id}/legal`, data).then((r) => r.data);

export const deactivateClient = (id) =>
  api.delete(`/clientes/${id}`).then((r) => r.data);

export const getContacts = (id) =>
  api.get(`/clientes/${id}/contacts`).then((r) => r.data);

export const addContact = (id, data) =>
  api.post(`/clientes/${id}/contacts`, data).then((r) => r.data);

export const removeContact = (clientId, contactId) =>
  api.delete(`/clientes/${clientId}/contacts/${contactId}`);

export const getNotes = (id) =>
  api.get(`/clientes/${id}/notes`).then((r) => r.data);

export const addNote = (id, content) =>
  api.post(`/clientes/${id}/notes`, { content }).then((r) => r.data);

export const getMembers = (id) =>
  api.get(`/clientes/${id}/members`).then((r) => r.data);

export const addMember = (id, data) =>
  api.post(`/clientes/${id}/members`, data).then((r) => r.data);

export const removeMember = (clientId, memberId) =>
  api.delete(`/clientes/${clientId}/members/${memberId}`);
