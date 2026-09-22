import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./authStore";

const PERMISOS = {
  modules: ["cajeros", "creditos"],
  actions: { cajeros: ["rules:read"], creditos: ["caja:read"] },
};

describe("sesión", () => {
  beforeEach(() => useAuthStore.setState({ token: null, user: null, permissions: null }));

  it("guarda token, usuario y permisos al ingresar", () => {
    useAuthStore.getState().setAuth("tok", { username: "ana" }, PERMISOS);
    const s = useAuthStore.getState();
    expect(s.token).toBe("tok");
    expect(s.user.username).toBe("ana");
    expect(s.permissions).toEqual(PERMISOS);
  });

  it("limpia todo al salir", () => {
    useAuthStore.getState().setAuth("tok", { username: "ana" }, PERMISOS);
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.token).toBeNull();
    expect(s.user).toBeNull();
    expect(s.permissions).toBeNull();
  });

  it("hasModule y hasPermission responden según los permisos", () => {
    const { setAuth, hasModule, hasPermission } = useAuthStore.getState();
    setAuth("tok", { username: "ana" }, PERMISOS);
    expect(hasModule("cajeros")).toBe(true);
    expect(hasModule("legacy")).toBe(false);
    expect(hasPermission("cajeros", "rules:read")).toBe(true);
    expect(hasPermission("cajeros", "rules:write")).toBe(false);
    expect(hasPermission("otro", "x")).toBe(false);
  });

  it("sin sesión no hay módulos ni permisos", () => {
    const { hasModule, hasPermission } = useAuthStore.getState();
    expect(hasModule("cajeros")).toBe(false);
    expect(hasPermission("cajeros", "rules:read")).toBe(false);
  });

  it("la sesión se persiste en sessionStorage, no en localStorage", () => {
    useAuthStore.getState().setAuth("tok", { username: "ana" }, PERMISOS);
    expect(sessionStorage.getItem("auth-storage")).toContain("tok");
    expect(localStorage.getItem("auth-storage")).toBeNull();
  });
});
