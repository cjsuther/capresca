import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Cada pantalla se reemplaza por un cartel: acá sólo se prueba el ruteo de App.
vi.mock("./pages/LoginPage", () => ({ default: () => <p>pantalla de login</p> }));
vi.mock("./pages/DashboardPage", () => ({ default: () => <p>tablero</p> }));
vi.mock("./modules/security", () => ({ default: () => <p>módulo security</p> }));
vi.mock("./modules/cajeros", () => ({ default: () => <p>módulo cajeros</p> }));
vi.mock("./modules/clientes", () => ({ default: () => <p>módulo clientes</p> }));
vi.mock("./modules/interbanking", () => ({ default: () => <p>módulo interbanking</p> }));
vi.mock("./modules/conciliacion", () => ({ default: () => <p>módulo conciliacion</p> }));
vi.mock("./modules/liquidaciones", () => ({ default: () => <p>módulo liquidaciones</p> }));
vi.mock("./modules/legacy", () => ({ default: () => <p>módulo legacy</p> }));

import App from "./App";
import { useAuthStore } from "./context/authStore";

const MODULOS = [
  "security", "cajeros", "clientes", "interbanking",
  "conciliacion", "liquidaciones", "legacy",
];

function sesion(modules) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules, actions: {} },
  });
}

// App monta su propio BrowserRouter: la ruta inicial se fija en el historial.
function montarEn(ruta) {
  window.history.pushState({}, "", ruta);
  return render(<App />);
}

describe("App — ruteo", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, permissions: null });
  });

  it("/login es pública", () => {
    montarEn("/login");
    expect(screen.getByText("pantalla de login")).toBeInTheDocument();
  });

  it('"/" redirige al dashboard', () => {
    sesion([]);
    montarEn("/");
    expect(screen.getByText("tablero")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
  });

  it("cualquier ruta desconocida cae en el dashboard", () => {
    sesion([]);
    montarEn("/no-existe/nada");
    expect(screen.getByText("tablero")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
  });

  it("el dashboard está detrás de PrivateRoute", () => {
    montarEn("/dashboard");
    expect(screen.getByText("pantalla de login")).toBeInTheDocument();
    expect(screen.queryByText("tablero")).not.toBeInTheDocument();
  });

  it("con sesión el dashboard se muestra", () => {
    sesion([]);
    montarEn("/dashboard");
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });

  it.each(MODULOS)("/modules/%s se muestra si el módulo está habilitado", (modulo) => {
    sesion([modulo]);
    montarEn(`/modules/${modulo}`);
    expect(screen.getByText(`módulo ${modulo}`)).toBeInTheDocument();
  });

  it.each(MODULOS)("/modules/%s vuelve al dashboard si el módulo no está habilitado", (modulo) => {
    sesion(["otro-modulo"]);
    montarEn(`/modules/${modulo}`);
    expect(screen.getByText("tablero")).toBeInTheDocument();
    expect(screen.queryByText(`módulo ${modulo}`)).not.toBeInTheDocument();
  });

  it.each(MODULOS)("/modules/%s manda al login sin sesión", (modulo) => {
    montarEn(`/modules/${modulo}`);
    expect(screen.getByText("pantalla de login")).toBeInTheDocument();
  });

  it("las rutas de módulo son splat: las subrutas las resuelve el módulo", () => {
    sesion(["conciliacion"]);
    montarEn("/modules/conciliacion/dias/2026-01-01");
    expect(screen.getByText("módulo conciliacion")).toBeInTheDocument();
  });
});
