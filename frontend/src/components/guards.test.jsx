import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { PermissionGate, PrivateRoute, ModuleRoute } from "./PrivateRoute";
import { Sidebar } from "./Sidebar";
import { useAuthStore } from "../context/authStore";

const sesion = (permissions) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" }, permissions });

function conRutas(ui, inicial = "/protegida") {
  return render(
    <MemoryRouter initialEntries={[inicial]}>
      <Routes>
        <Route path="/protegida" element={ui} />
        <Route path="/login" element={<p>pantalla de login</p>} />
        <Route path="/dashboard" element={<p>tablero</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("PrivateRoute", () => {
  beforeEach(() => useAuthStore.setState({ token: null, user: null, permissions: null }));

  it("sin sesión manda al login", () => {
    conRutas(<PrivateRoute><p>contenido</p></PrivateRoute>);
    expect(screen.getByText("pantalla de login")).toBeInTheDocument();
  });

  it("con sesión muestra el contenido", () => {
    sesion({ modules: [], actions: {} });
    conRutas(<PrivateRoute><p>contenido</p></PrivateRoute>);
    expect(screen.getByText("contenido")).toBeInTheDocument();
  });
});

describe("ModuleRoute", () => {
  beforeEach(() => useAuthStore.setState({ token: null, user: null, permissions: null }));

  it("sin sesión manda al login", () => {
    conRutas(<ModuleRoute moduleCode="cajeros"><p>módulo</p></ModuleRoute>);
    expect(screen.getByText("pantalla de login")).toBeInTheDocument();
  });

  it("sin el módulo habilitado vuelve al tablero", () => {
    sesion({ modules: ["clientes"], actions: {} });
    conRutas(<ModuleRoute moduleCode="cajeros"><p>módulo</p></ModuleRoute>);
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });

  it("con el módulo habilitado lo muestra", () => {
    sesion({ modules: ["cajeros"], actions: {} });
    conRutas(<ModuleRoute moduleCode="cajeros"><p>módulo</p></ModuleRoute>);
    expect(screen.getByText("módulo")).toBeInTheDocument();
  });
});

describe("PermissionGate", () => {
  it("muestra el hijo sólo con el permiso, y si no el fallback", () => {
    sesion({ modules: ["cajeros"], actions: { cajeros: ["rules:read"] } });
    const { rerender } = render(
      <PermissionGate moduleCode="cajeros" action="rules:read"><button>Editar</button></PermissionGate>
    );
    expect(screen.getByRole("button", { name: "Editar" })).toBeInTheDocument();

    rerender(
      <PermissionGate moduleCode="cajeros" action="rules:write" fallback={<p>sin permiso</p>}>
        <button>Editar</button>
      </PermissionGate>
    );
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.getByText("sin permiso")).toBeInTheDocument();
  });
});

describe("Sidebar", () => {
  const menu = [
    { label: "Transacciones", path: "/modules/cajeros/transactions", permission: "transactions:read" },
    { label: "Reglas", path: "/modules/cajeros/rules", permission: "rules:read" },
  ];

  it("oculta las opciones sin permiso", () => {
    sesion({ modules: ["cajeros"], actions: { cajeros: ["transactions:read"] } });
    render(
      <MemoryRouter>
        <Sidebar menuItems={menu} moduleCode="cajeros" />
      </MemoryRouter>
    );
    expect(screen.getByText("Transacciones")).toBeInTheDocument();
    expect(screen.queryByText("Reglas")).not.toBeInTheDocument();
  });

  it("muestra todas las opciones permitidas", () => {
    sesion({ modules: ["cajeros"], actions: { cajeros: ["transactions:read", "rules:read"] } });
    render(
      <MemoryRouter>
        <Sidebar menuItems={menu} moduleCode="cajeros" />
      </MemoryRouter>
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });
});
