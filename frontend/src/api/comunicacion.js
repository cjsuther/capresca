import api from "./client";

// Conversations
export const getConversations = (params) =>
  api.get("/comunicacion/conversations", { params }).then((r) => r.data);

export const getConversation = (id) =>
  api.get(`/comunicacion/conversations/${id}`).then((r) => r.data);

export const createConversation = (data) =>
  api.post("/comunicacion/conversations", data).then((r) => r.data);

export const linkClient = (conversationId, data) =>
  api.put(`/comunicacion/conversations/${conversationId}/link-client`, data).then((r) => r.data);

export const markConversationRead = (conversationId) =>
  api.put(`/comunicacion/conversations/${conversationId}/read`).then((r) => r.data);

// Messages
export const getMessages = (conversationId, params) =>
  api.get(`/comunicacion/conversations/${conversationId}/messages`, { params }).then((r) => r.data);

export const sendMessage = (conversationId, data) =>
  api.post(`/comunicacion/conversations/${conversationId}/messages`, data).then((r) => r.data);

export const sendMediaMessage = (conversationId, formData) =>
  api.post(`/comunicacion/conversations/${conversationId}/messages/media`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
  }).then((r) => r.data);

// Menu config
export const getMenuConfig = () =>
  api.get("/comunicacion/menu").then((r) => r.data);

export const updateMenuConfig = (data) =>
  api.put("/comunicacion/menu", data).then((r) => r.data);

// WhatsApp config
export const getWhatsappConfig = () =>
  api.get("/comunicacion/whatsapp-config").then((r) => r.data);

export const updateWhatsappConfig = (data) =>
  api.put("/comunicacion/whatsapp-config", data).then((r) => r.data);

// Stats
export const getStats = () =>
  api.get("/comunicacion/stats").then((r) => r.data);

// Clientes (for search)
export const searchClientes = (search) =>
  api.get("/clientes", { params: { search, per_page: 10 } }).then((r) => r.data);
