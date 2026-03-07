import api from "./client";

export const login = (username, password) =>
  api.post("/auth/login", { username, password }).then((r) => r.data);

export const logout = () =>
  api.post("/auth/logout").catch(() => {});

export const refreshToken = () =>
  api.post("/auth/refresh").then((r) => r.data);
