import api from "./client";

export const getInteractions = (params) =>
  api.get("/legacy/interactions", { params }).then((r) => r.data);

export const getInteraction = (id) =>
  api.get(`/legacy/interactions/${id}`).then((r) => r.data);

export const getDatabases = () =>
  api.get("/legacy/databases").then((r) => r.data);

export const getStatus = () =>
  api.get("/legacy/status").then((r) => r.data);

export const triggerSync = (tabla) =>
  api.post(`/legacy/sync/${tabla}`).then((r) => r.data);

export const getOutbox = (params) =>
  api.get("/legacy/outbox", { params }).then((r) => r.data);

export const drainOutbox = () =>
  api.post("/legacy/outbox/drain").then((r) => r.data);
