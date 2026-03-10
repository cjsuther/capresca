import api from "./client";

// Rules
export const getRules = (params = {}) =>
  api.get("/cajeros/rules", { params }).then((r) => r.data);

export const createRule = (data) =>
  api.post("/cajeros/rules", data).then((r) => r.data);

export const deleteRule = (id) =>
  api.delete(`/cajeros/rules/${id}`);

// Transactions
export const getTransactions = (params = {}) =>
  api.get("/cajeros/transactions", { params }).then((r) => r.data);

export const getTransaction = (id) =>
  api.get(`/cajeros/transactions/${id}`).then((r) => r.data);

export const createTransaction = (data) =>
  api.post("/cajeros/transactions", data).then((r) => r.data);

export const authorizeTransaction = (id) =>
  api.put(`/cajeros/transactions/${id}/authorize`).then((r) => r.data);

export const rejectTransaction = (id, data) =>
  api.put(`/cajeros/transactions/${id}/reject`, data).then((r) => r.data);

export const deleteTransaction = (id) =>
  api.delete(`/cajeros/transactions/${id}`).then((r) => r.data);
