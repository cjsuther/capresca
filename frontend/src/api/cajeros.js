import api from "./client";

export const getMyLimit = () =>
  api.get("/cajeros/limits").then((r) => r.data);

export const getUserLimit = (userId) =>
  api.get(`/cajeros/limits/${userId}`).then((r) => r.data);

export const updateLimit = (userId, data) =>
  api.put(`/cajeros/limits/${userId}`, data).then((r) => r.data);

export const getRelations = () =>
  api.get("/cajeros/relations").then((r) => r.data);

export const createRelation = (data) =>
  api.post("/cajeros/relations", data).then((r) => r.data);

export const deleteRelation = (id) =>
  api.delete(`/cajeros/relations/${id}`);

export const createRequest = (data) =>
  api.post("/cajeros/requests", data).then((r) => r.data);

export const getRequests = (asAuthorizer = false) =>
  api.get("/cajeros/requests", { params: { as_authorizer: asAuthorizer } }).then((r) => r.data);

export const getRequest = (id) =>
  api.get(`/cajeros/requests/${id}`).then((r) => r.data);

export const approveRequest = (id, data = {}) =>
  api.put(`/cajeros/requests/${id}/approve`, data).then((r) => r.data);

export const rejectRequest = (id, data = {}) =>
  api.put(`/cajeros/requests/${id}/reject`, data).then((r) => r.data);

export const getOperations = () =>
  api.get("/cajeros/operations").then((r) => r.data);
