import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfiguracionesModule from "./index";
import { useAuthStore } from "../../context/authStore";
import * as api from "../../api/configuraciones";

vi.mock("../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarImpuestos: vi.fn(), listarIndices: vi.fn(), listarFeriados: vi.fn(), listarPaises: vi.fn(),
  listarWorkflow: vi.fn(),
}));

vi.mock("../../components/Layout", () => ({
  Layout: ({ children, sidebar }) => (
    <div>
      {typeof sidebar === "function" ? sidebar(undefined) : sidebar}
      <main>{children}</main>
    </div>
  ),
}));

const sesion = (acciones) => useAuthStore.setState({
  token: "tok", user: { username: "ana" },
  permissions: { modules: ["configuraciones"], actions: { configuraciones: acciones } },
});

function montar(ruta = "/modules/configuraciones") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/configuraciones/*" element={<ConfiguracionesModule />} />
        <Route path="/dashboard" element={<p>tablero</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("módulo Configuraciones", () => {
  beforeEach(() => {
    api.listarImpuestos.mockResolvedValue({ items: [] });
    api.listarIndices.mockResolvedValue({ items: [] });
    api.listarFeriados.mockResolvedValue({ items: [], anios: [] });
    api.listarPaises.mockResolvedValue({ items: [{ codigo: "AR", nombre: "Argentina" }] });
    api.listarWorkflow.mockResolvedValue({ reglas: [], roles: [], puedeEditar: false });
  });

  it("el menú muestra sólo los catálogos que el usuario puede ver", () => {
    sesion(["feriados:read", "workflow:read"]);
    montar();
    expect(screen.getByRole("link", { name: /Feriados/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Workflow/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Impuestos/ })).toBeNull();
  });

  it("entra a la primera pantalla habilitada", async () => {
    sesion(["indices:read"]);
    montar();
    expect(await screen.findByRole("heading", { name: "Índices de referencia" })).toBeInTheDocument();
  });

  it("sin permiso sobre un catálogo no se abre por URL", async () => {
    sesion(["feriados:read"]);
    montar("/modules/configuraciones/impuestos");
    expect(await screen.findByRole("heading", { name: "Feriados" })).toBeInTheDocument();
    expect(api.listarImpuestos).not.toHaveBeenCalled();
  });

  it("sin ningún permiso de lectura vuelve al tablero", () => {
    sesion(["impuestos:write"]);
    montar();
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });
});
