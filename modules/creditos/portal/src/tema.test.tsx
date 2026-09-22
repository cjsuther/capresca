import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// El portal no usa red para el tema, pero App monta el login (api.loginUrl) al renderizar.
const h = vi.hoisted(() => ({ api: { loginUrl: vi.fn(), me: vi.fn(), notificaciones: vi.fn() } }));
vi.mock("./api", async (original) => ({ ...(await original() as any), api: h.api }));

import App from "./App";
import { aplicarTema, getTema, iniciarTema, setTema, temaEfectivo } from "./tema";

/** matchMedia no existe en jsdom: se simula pudiendo cambiar la preferencia del dispositivo. */
function simularDispositivo(oscuro: boolean) {
  const oyentes = new Set<() => void>();
  const mq = {
    matches: oscuro,
    addEventListener: (_: string, f: () => void) => { oyentes.add(f); },
    removeEventListener: (_: string, f: () => void) => { oyentes.delete(f); },
  };
  vi.stubGlobal("matchMedia", vi.fn(() => mq));
  return {
    cambiarA(nuevoOscuro: boolean) { mq.matches = nuevoOscuro; oyentes.forEach((f) => f()); },
  };
}

beforeEach(() => {
  simularDispositivo(false);
  document.documentElement.removeAttribute("data-tema");
});

afterEach(() => {
  // Desmontar antes de resetear: el store avisa a los suscriptores y React lo pediría dentro de act().
  cleanup();
  act(() => setTema("system"));
  document.documentElement.removeAttribute("data-tema");
});

describe("preferencia de tema", () => {
  it("resuelve 'system' contra el dispositivo", () => {
    const disp = simularDispositivo(true);
    expect(temaEfectivo("system")).toBe("dark");
    disp.cambiarA(false);
    expect(temaEfectivo("system")).toBe("light");
    expect(temaEfectivo("dark")).toBe("dark");
  });

  it("pinta el tema elegido en el <html> y lo guarda para la próxima visita", () => {
    setTema("dark");
    expect(document.documentElement.dataset.tema).toBe("dark");
    expect(localStorage.getItem("portal-creditos-theme")).toBe("dark");

    setTema("light");
    expect(document.documentElement.dataset.tema).toBe("light");
  });

  it("al arrancar aplica lo guardado, sin esperar al render", () => {
    localStorage.setItem("portal-creditos-theme", "dark");
    iniciarTema();
    expect(getTema()).toBe("dark");
    expect(document.documentElement.dataset.tema).toBe("dark");
  });

  it("sigue al dispositivo sólo mientras la preferencia sea 'system'", () => {
    const disp = simularDispositivo(false);
    localStorage.removeItem("portal-creditos-theme");
    const soltar = iniciarTema();
    expect(document.documentElement.dataset.tema).toBe("light");

    disp.cambiarA(true);
    expect(document.documentElement.dataset.tema).toBe("dark");

    setTema("light");
    disp.cambiarA(false);
    disp.cambiarA(true);
    expect(document.documentElement.dataset.tema).toBe("light");
    soltar();
  });

  it("ignora un valor inválido guardado y vuelve a 'system'", () => {
    localStorage.setItem("portal-creditos-theme", "fucsia");
    iniciarTema();
    expect(getTema()).toBe("system");
  });

  it("no rompe si localStorage está bloqueado (modo privado)", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("bloqueado"); });
    expect(() => setTema("dark")).not.toThrow();
    expect(document.documentElement.dataset.tema).toBe("dark");
    setItem.mockRestore();
  });
});

describe("selector de tema en el portal", () => {
  it("el ciudadano puede cambiar a oscuro antes de iniciar sesión", async () => {
    aplicarTema("light");
    const u = userEvent.setup();
    render(<App />);

    const grupo = await screen.findByRole("radiogroup", { name: /Tema de la interfaz/ });
    const oscuro = within(grupo).getByRole("radio", { name: "Oscuro" });
    expect(oscuro).toHaveAttribute("aria-checked", "false");

    await u.click(oscuro);
    expect(document.documentElement.dataset.tema).toBe("dark");
    expect(within(grupo).getByRole("radio", { name: "Oscuro" })).toHaveAttribute("aria-checked", "true");

    await u.click(within(grupo).getByRole("radio", { name: "Claro" }));
    expect(document.documentElement.dataset.tema).toBe("light");
  });
});
