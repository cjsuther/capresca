import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "./client";
import { useAuthStore } from "../context/authStore";

describe("cliente HTTP", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, permissions: null });
  });

  it("usa /api como base", () => {
    expect(api.defaults.baseURL).toBe("/api");
  });

  it("inyecta el token de la sesión en cada request", () => {
    const interceptor = api.interceptors.request.handlers[0].fulfilled;
    expect(interceptor({ headers: {} }).headers.Authorization).toBeUndefined();

    useAuthStore.setState({ token: "tok-123" });
    expect(interceptor({ headers: {} }).headers.Authorization).toBe("Bearer tok-123");
  });

  it("ante un 401 cierra la sesión y manda al login", async () => {
    useAuthStore.setState({ token: "tok-123", user: { username: "ana" } });
    delete window.location;
    window.location = { href: "/dashboard" };

    const onError = api.interceptors.response.handlers[0].rejected;
    await expect(onError({ response: { status: 401 } })).rejects.toBeTruthy();

    expect(useAuthStore.getState().token).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("otros errores no cierran la sesión", async () => {
    useAuthStore.setState({ token: "tok-123" });
    const onError = api.interceptors.response.handlers[0].rejected;
    await expect(onError({ response: { status: 500 } })).rejects.toBeTruthy();
    expect(useAuthStore.getState().token).toBe("tok-123");
  });

  it("deja pasar las respuestas exitosas", () => {
    const onOk = api.interceptors.response.handlers[0].fulfilled;
    const resp = { data: { ok: true } };
    expect(onOk(resp)).toBe(resp);
  });
});

describe("clientes de API por módulo", () => {
  it("cada endpoint llama a su ruta y devuelve data", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ data: { ok: true } });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: { id: 1 } });
    const put = vi.spyOn(api, "put").mockResolvedValue({ data: { ok: true } });

    const { login, logout, refreshToken } = await import("./auth");
    const { getNotifications, getUnreadCount, markAsRead, markAllAsRead } = await import("./notifications");

    await expect(login("ana", "x")).resolves.toEqual({ id: 1 });
    expect(post).toHaveBeenCalledWith("/auth/login", { username: "ana", password: "x" });

    await expect(getNotifications({ limit: 5 })).resolves.toEqual({ ok: true });
    expect(get).toHaveBeenCalledWith("/notifications", { params: { limit: 5 } });

    await getUnreadCount();
    expect(get).toHaveBeenCalledWith("/notifications/unread-count");

    await markAsRead(9);
    expect(put).toHaveBeenCalledWith("/notifications/9/read");

    await markAllAsRead();
    expect(put).toHaveBeenCalledWith("/notifications/read-all");

    await refreshToken();
    expect(post).toHaveBeenCalledWith("/auth/refresh");

    post.mockRejectedValueOnce(new Error("sin red"));
    await expect(logout()).resolves.toBeUndefined();   // logout nunca rompe la UI
  });
});
