import { beforeEach, describe, expect, it, vi } from "vitest";

import { useThemeStore, temaEfectivo, aplicarTema, iniciarTema } from "./themeStore";

/** matchMedia doble: jsdom no lo implementa. */
function stubPrefiereOscuro(oscuro) {
  const listeners = new Set();
  const mq = {
    matches: oscuro,
    addEventListener: (_e, cb) => listeners.add(cb),
    removeEventListener: (_e, cb) => listeners.delete(cb),
  };
  vi.stubGlobal("matchMedia", vi.fn(() => mq));
  return { mq, disparar: () => listeners.forEach((cb) => cb()) };
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = "";
  useThemeStore.setState({ tema: "system" });
  stubPrefiereOscuro(false);
});

describe("tema de la plataforma", () => {
  it("por defecto sigue al sistema operativo", () => {
    stubPrefiereOscuro(true);
    expect(temaEfectivo("system")).toBe("dark");
    stubPrefiereOscuro(false);
    expect(temaEfectivo("system")).toBe("light");
  });

  it("elegir oscuro marca el <html> y lo recuerda en el navegador", () => {
    useThemeStore.getState().setTema("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("portezuelo-theme")).toContain("dark");
  });

  it("elegir claro saca la marca aunque el sistema esté en oscuro", () => {
    stubPrefiereOscuro(true);
    useThemeStore.getState().setTema("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("aplicarTema resuelve 'system' contra el navegador", () => {
    stubPrefiereOscuro(true);
    expect(aplicarTema("system")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("con 'sistema' sigue los cambios del SO; con una elección explícita no", () => {
    const { mq, disparar } = stubPrefiereOscuro(false);
    const parar = iniciarTema();
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    mq.matches = true;
    disparar();
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    useThemeStore.getState().setTema("light");
    mq.matches = true;
    disparar();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    parar();
  });

  it("si el navegador bloquea el storage no rompe", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("bloqueado"); });
    expect(() => useThemeStore.getState().setTema("dark")).not.toThrow();
    vi.restoreAllMocks();
  });
});
