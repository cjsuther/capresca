import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/auth", () => ({ logout: vi.fn() }));
vi.mock("../../api/notifications", () => ({
  getNotifications: vi.fn().mockResolvedValue({ data: [], unread_count: 0 }),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
  markAsRead: vi.fn().mockResolvedValue({}),
  markAllAsRead: vi.fn().mockResolvedValue({}),
}));
vi.mock("../../api/security", () => ({
  getUsers: vi.fn().mockResolvedValue({ data: [], total: 0 }),
  getRoles: vi.fn().mockResolvedValue([]),
  getPermissions: vi.fn().mockResolvedValue([]),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
  assignRoles: vi.fn(),
  adminChangePassword: vi.fn(),
  changeMyPassword: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
  deleteRole: vi.fn(),
  assignPermissions: vi.fn(),
}));

import SecurityModule, { securityMenu } from "./index";
import { useAuthStore } from "../../context/authStore";

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/security/*" element={<SecurityModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SecurityModule", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "tok",
      user: { username: "ana", full_name: "Ana Gómez" },
      permissions: { modules: ["security"], actions: { security: ["users:read", "roles:read"] } },
    });
  });

  it("el menú declara Usuarios, Grupos y Roles con sus permisos de lectura", () => {
    expect(securityMenu.map((i) => [i.label, i.path, i.permission])).toEqual([
      ["Usuarios", "/modules/security/users", "users:read"],
      ["Grupos", "/modules/security/groups", "groups:read"],
      ["Roles", "/modules/security/roles", "roles:read"],
    ]);
  });

  it("la raíz del módulo redirige a Usuarios", async () => {
    montar("/modules/security");
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
  });

  it("/users muestra la pantalla de usuarios dentro del Layout", async () => {
    montar("/modules/security/users");

    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
    // El Layout aporta la topbar con el usuario logueado
    expect(screen.getByRole("button", { name: /Ana Gómez/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
  });

  it("/roles muestra la pantalla de roles", async () => {
    montar("/modules/security/roles");
    expect(await screen.findByRole("heading", { name: "Roles" })).toBeInTheDocument();
  });

  it("el sidebar sólo lista las opciones permitidas", async () => {
    useAuthStore.setState({
      permissions: { modules: ["security"], actions: { security: ["users:read"] } },
    });
    montar("/modules/security/users");

    await screen.findByRole("heading", { name: "Usuarios" });
    // Aparece en el sidebar desktop y en el panel mobile, pero nunca "Roles"
    expect(screen.getAllByRole("link", { name: "Usuarios" })).toHaveLength(2);
    expect(screen.queryByRole("link", { name: "Roles" })).not.toBeInTheDocument();
  });
});
