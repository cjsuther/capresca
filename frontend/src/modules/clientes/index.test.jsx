import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClientesModule, { clientesMenu } from "./index";
import { useAuthStore } from "../../context/authStore";
import { getClient, getClients, getNotes } from "../../api/clientes";

vi.mock("../../api/clientes", () => ({
  getClients: vi.fn(),
  getClient: vi.fn(),
  getNotes: vi.fn(),
  addNote: vi.fn(),
  updateClient: vi.fn(),
  updateHumanProfile: vi.fn(),
  updateLegalProfile: vi.fn(),
  getMembers: vi.fn(),
  addMember: vi.fn(),
  removeMember: vi.fn(),
  searchClients: vi.fn(),
  getCbus: vi.fn(),
  addCbu: vi.fn(),
  deleteCbu: vi.fn(),
  createHumanClient: vi.fn(),
  createLegalClient: vi.fn(),
}));

vi.mock("../../api/notifications", () => ({
  getNotifications: vi.fn().mockResolvedValue({ data: [], unread_count: 0 }),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
  markAsRead: vi.fn().mockResolvedValue({}),
  markAllAsRead: vi.fn().mockResolvedValue({}),
}));

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana", full_name: "Ana Pérez" },
    permissions: { modules: ["clientes"], actions: { clientes: acciones } },
  });

function montar(ruta = "/modules/clientes") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/clientes/*" element={<ClientesModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ClientesModule", () => {
  beforeEach(() => {
    getClients.mockResolvedValue({ data: [], total: 0 });
    sesion(["clients:read", "clients:write"]);
  });

  it("el menú declara las tres secciones con sus permisos", () => {
    expect(clientesMenu.map((i) => i.permission)).toEqual([
      "clients:read", "clients:write", "clients:write",
    ]);
    expect(clientesMenu.map((i) => i.path)).toEqual([
      "/modules/clientes/lista",
      "/modules/clientes/nuevo/humano",
      "/modules/clientes/nuevo/juridico",
    ]);
  });

  it("la raíz del módulo redirige al listado", async () => {
    montar("/modules/clientes");
    expect(await screen.findByRole("heading", { name: "Clientes" })).toBeInTheDocument();
    await waitFor(() => expect(getClients).toHaveBeenCalled());
  });

  it("muestra en el sidebar sólo las opciones permitidas", async () => {
    sesion(["clients:read"]);
    montar("/modules/clientes/lista");
    await screen.findByText("Sin resultados");
    expect(screen.getAllByText("Todos los clientes").length).toBeGreaterThan(0);
    expect(screen.queryByText("Nueva Persona Física")).not.toBeInTheDocument();
    expect(screen.queryByText("Nueva Persona Jurídica")).not.toBeInTheDocument();
  });

  it("con permiso de escritura muestra las altas y permite navegar a una", async () => {
    const user = userEvent.setup();
    montar("/modules/clientes/lista");
    await screen.findByText("Sin resultados");

    const alta = screen.getAllByText("Nueva Persona Jurídica")[0];
    await user.click(alta);
    expect(await screen.findByRole("heading", { name: "Nueva Persona Jurídica" })).toBeInTheDocument();
  });

  it("la ruta :id monta el detalle del cliente", async () => {
    getClient.mockResolvedValue({
      id: 123, code: "CLI-0123", client_type: "HUMAN", is_active: true,
      human_profile: { first_name: "Ana", last_name: "Pérez" },
    });
    getNotes.mockResolvedValue([]);
    montar("/modules/clientes/123");

    expect(await screen.findByText("CLI-0123")).toBeInTheDocument();
    expect(getClient).toHaveBeenCalledWith("123");
  });
});
