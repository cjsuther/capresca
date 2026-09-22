import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/security", () => ({
  getGroups: vi.fn(), createGroup: vi.fn(), updateGroup: vi.fn(), deleteGroup: vi.fn(),
  assignGroupRoles: vi.fn(), assignGroupMembers: vi.fn(), getRoles: vi.fn(), getUsers: vi.fn(),
}));

import {
  getGroups, createGroup, updateGroup, deleteGroup, assignGroupRoles, assignGroupMembers, getRoles, getUsers,
} from "../../../api/security";
import GroupsPage from "./GroupsPage";
import { useAuthStore } from "../../../context/authStore";

const TESORERO = { id: 1, name: "tesorero", description: "Aprueba lotes" };
const LECTOR = { id: 2, name: "lector", description: null };
const ANA = { id: 10, username: "ana", full_name: "Ana Gómez", is_active: true };
const BETO = { id: 11, username: "beto", full_name: null, is_active: true };
const TESORERIA = { id: 5, name: "Tesorería", description: "Área de pagos", is_active: true, roles: [TESORERO], users: [ANA] };
const AUDITORIA = { id: 6, name: "Auditoría", description: null, is_active: false, roles: [], users: [] };

function sesion(acciones) {
  useAuthStore.setState({
    token: "tok", user: { username: "admin" },
    permissions: { modules: ["security"], actions: { security: acciones } },
  });
}

async function montar() {
  render(<MemoryRouter><GroupsPage /></MemoryRouter>);
  await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
}

describe("GroupsPage", () => {
  beforeEach(() => {
    sesion(["groups:read", "groups:write"]);
    getGroups.mockResolvedValue([TESORERIA, AUDITORIA]);
    getRoles.mockResolvedValue([TESORERO, LECTOR]);
    getUsers.mockResolvedValue({ data: [ANA, BETO], total: 2 });
    createGroup.mockResolvedValue({ id: 7 });
    updateGroup.mockResolvedValue({ id: 5 });
    deleteGroup.mockResolvedValue({});
    assignGroupRoles.mockResolvedValue({});
    assignGroupMembers.mockResolvedValue({});
  });

  it("lista los grupos con estado, roles e integrantes", async () => {
    await montar();
    const fila = screen.getByText("Tesorería").closest("tr");
    expect(within(fila).getByText("Activo")).toBeInTheDocument();
    expect(within(fila).getByText("tesorero")).toBeInTheDocument();
    expect(within(fila).getByText("1")).toHaveAttribute("title", "ana");
    expect(within(screen.getByText("Auditoría").closest("tr")).getByText("Inactivo")).toBeInTheDocument();
  });

  it("busca por grupo, rol o usuario", async () => {
    await montar();
    await userEvent.type(screen.getByPlaceholderText("Grupo, rol o usuario"), "ana");
    expect(screen.getByText("Tesorería")).toBeInTheDocument();
    expect(screen.queryByText("Auditoría")).not.toBeInTheDocument();
  });

  it("crea un grupo con sus roles e integrantes", async () => {
    await montar();
    await userEvent.click(screen.getByRole("button", { name: /Nuevo grupo/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo grupo" });
    await userEvent.type(within(modal).getAllByRole("textbox")[0], "Cobranzas");
    await userEvent.click(within(modal).getByLabelText(/lector/));
    await userEvent.click(within(modal).getByLabelText(/beto/));
    await userEvent.click(within(modal).getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(assignGroupMembers).toHaveBeenCalledWith(7, [11]));
    expect(createGroup).toHaveBeenCalledWith({ name: "Cobranzas", description: null, is_active: true });
    expect(assignGroupRoles).toHaveBeenCalledWith(7, [2]);
    expect(getGroups).toHaveBeenCalledTimes(2);
  });

  it("edita un grupo partiendo de lo que ya tiene", async () => {
    await montar();
    await userEvent.click(screen.getByLabelText("Editar Tesorería"));
    const modal = screen.getByRole("dialog", { name: "Editar grupo Tesorería" });
    expect(within(modal).getByLabelText(/tesorero/)).toBeChecked();
    expect(within(modal).getByLabelText(/ana/)).toBeChecked();
    await userEvent.click(within(modal).getByLabelText(/ana/));
    await userEvent.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(assignGroupMembers).toHaveBeenCalledWith(5, []));
    expect(updateGroup).toHaveBeenCalledWith(5, { name: "Tesorería", description: "Área de pagos", is_active: true });
  });

  it("muestra el error del servidor dentro del modal", async () => {
    createGroup.mockRejectedValue({ response: { data: { detail: "El nombre de grupo ya existe" } } });
    await montar();
    await userEvent.click(screen.getByRole("button", { name: /Nuevo grupo/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo grupo" });
    await userEvent.type(within(modal).getAllByRole("textbox")[0], "Tesorería");
    await userEvent.click(within(modal).getByRole("button", { name: "Guardar" }));
    expect(await within(modal).findByText("El nombre de grupo ya existe")).toBeInTheDocument();
  });

  it("eliminar pide confirmación", async () => {
    await montar();
    await userEvent.click(screen.getByLabelText("Eliminar Tesorería"));
    const conf = screen.getByRole("dialog", { name: "Eliminar el grupo Tesorería" });
    expect(conf).toHaveTextContent("dejan de heredar");
    await userEvent.click(within(conf).getByRole("button", { name: "Eliminar" }));
    await waitFor(() => expect(deleteGroup).toHaveBeenCalledWith(5));
  });

  it("sólo lectura: sin alta ni acciones", async () => {
    sesion(["groups:read"]);
    await montar();
    expect(screen.queryByRole("button", { name: /Nuevo grupo/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Editar Tesorería")).not.toBeInTheDocument();
  });
});
