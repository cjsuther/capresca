import api from "./client";

export const getNotifications = (params = {}) =>
  api.get("/notifications", { params }).then((r) => r.data);

export const getUnreadCount = () =>
  api.get("/notifications/unread-count").then((r) => r.data);

export const markAsRead = (id) =>
  api.put(`/notifications/${id}/read`).then((r) => r.data);

export const markAllAsRead = () =>
  api.put("/notifications/read-all").then((r) => r.data);
