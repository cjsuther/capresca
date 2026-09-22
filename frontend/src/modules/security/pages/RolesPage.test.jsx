import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/security", () => ({
  getRoles: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
  deleteRole: vi.fn(),
  getPermissions: vi.fn(),
  assignPermissions: vi.fn(),
}));

import {
  getRoles, createRole, updateRole, deleteRole, getPermissions, assignPermissions,
} from "../../../api/security";
import RolesPage from "./RolesPage";
import { useAuthStore } from "../../../context/authStore";

const PERM_USERS_READ = { id: 1, code: "users:read", description: "Ver usuarios" };
const PERM_USERS_WRITE = { id: 2, code: "users:write", description: null };
const PERM_CAJEROS_READ = { id: 3, code: "transactions:read", description: "Ver transacciones" };

const rolAdmin = {
  id: 1, name: "admin", description: "Acceso total",
  permissions: [PERM_USERS_READ, PERM_USERS_WRITE],
};
const rolVisor = { id: 2, name: "visor", description: null, permissions: [] };

function sesion(acciones) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["security"], actions: { security: acciones } },
  });
}

async function montar() {
  const utils = render(<MemoryRouter><RolesPage /></MemoryRouter>);
  await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
  return utils;
}

const tarjetaDe = (nombre) => screen.getByText(nombre).closest("div.bg-surface");

describe("RolesPage", () => {
  beforeEach(() => {
    sesion(["roles:read", "roles:write"]);
    getRoles.mockResolvedValue([rolAdmin, rolVisor]);
    getPermissions.mockResolvedValue([PERM_USERS_READ, PERM_USERS_WRITE, PERM_CAJEROS_READ]);
    createRole.mockResolvedValue({ id: 3 });
    updateRole.mockResolvedValue({});
    deleteRole.mockResolvedValue({});
    assignPermissions.mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("lista los roles con su descripción, el conteo y los tags de permisos", async () => {
    render(<MemoryRouter><RolesPage /></MemoryRouter>);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("admin")).toBeInTheDocument());
    expect(screen.getByText("Acceso total")).toBeInTheDocument();
    expect(screen.getByText("2 permisos")).toBeInTheDocument();
    expect(screen.getByText("0 permisos")).toBeInTheDocument();
    expect(within(tarjetaDe("admin")).getByText("users:read")).toBeInTheDocument();
    expect(within(tarjetaDe("admin")).getByText("users:write")).toBeInTheDocument();
  });

  it("avisa cuando falla la carga", async () => {
    getPermissions.mockRejectedValue(new Error("500"));
    await montar();
    expect(screen.getByText("Error al cargar datos")).toBeInTheDocument();
  });

  it("sin permiso de escritura oculta el alta y las acciones", async () => {
    sesion(["roles:read"]);
    await montar();

    expect(screen.queryByRole("button", { name: /Nuevo rol/ })).not.toBeInTheDocument();
    expect(screen.queryByTitle("Editar")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Eliminar")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Gestionar permisos")).not.toBeInTheDocument();
  });

  it("crea un rol con nombre y descripción y recarga", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo rol/ }));
    const form = screen.getByRole("button", { name: "Crear" }).closest("form");
    const [nombre, descripcion] = form.querySelectorAll("input");

    await user.type(nombre, "supervisor");
    await user.type(descripcion, "Controla la caja");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() => expect(createRole).toHaveBeenCalledWith({
      name: "supervisor", description: "Controla la caja",
    }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument());
    expect(getRoles).toHaveBeenCalledTimes(2);
  });

  it("muestra el error de la API al crear", async () => {
    const user = userEvent.setup();
    createRole.mockRejectedValue({ response: { data: { detail: "El rol ya existe" } } });
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo rol/ }));
    await user.type(screen.getByRole("button", { name: "Crear" }).closest("form").querySelector("input"), "admin");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText("El rol ya existe")).toBeInTheDocument();
  });

  it("el botón de alta funciona como toggle y Cancelar cierra el formulario", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo rol/ }));
    expect(screen.getByRole("button", { name: "Crear" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Nuevo rol/ }));
    expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Nuevo rol/ }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument();
  });

  it("edita el nombre y la descripción de un rol", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Editar"));
    const form = screen.getByRole("button", { name: /Guardar/ }).closest("form");
    const [nombre, descripcion] = form.querySelectorAll("input");

    await user.clear(nombre);
    await user.type(nombre, "administrador");
    await user.clear(descripcion);
    await user.type(descripcion, "Mando total");
    await user.click(within(form).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateRole).toHaveBeenCalledWith(1, {
      name: "administrador", description: "Mando total",
    }));
    await waitFor(() => expect(getRoles).toHaveBeenCalledTimes(2));
  });

  it("cancelar la edición deja el rol como estaba", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Editar"));
    expect(screen.getByRole("button", { name: /Guardar/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Cancelar/ }));
    expect(screen.getByText("Acceso total")).toBeInTheDocument();
    expect(updateRole).not.toHaveBeenCalled();
  });

  it("muestra el error de la API al editar", async () => {
    const user = userEvent.setup();
    updateRole.mockRejectedValue({ response: { data: { detail: "Nombre repetido" } } });
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Editar"));
    await user.click(screen.getByRole("button", { name: /Guardar/ }));

    expect(await screen.findByText("Nombre repetido")).toBeInTheDocument();
  });

  it("elimina un rol previa confirmación y recarga", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("visor")).getByTitle("Eliminar"));

    expect(window.confirm).toHaveBeenCalledWith('¿Eliminar el rol "visor"? Esta acción no se puede deshacer.');
    await waitFor(() => expect(deleteRole).toHaveBeenCalledWith(2));
    await waitFor(() => expect(getRoles).toHaveBeenCalledTimes(2));
  });

  it("si se cancela la confirmación no elimina", async () => {
    const user = userEvent.setup();
    window.confirm.mockReturnValue(false);
    await montar();

    await user.click(within(tarjetaDe("visor")).getByTitle("Eliminar"));
    expect(deleteRole).not.toHaveBeenCalled();
  });

  it("muestra el error de la API al eliminar", async () => {
    const user = userEvent.setup();
    deleteRole.mockRejectedValue({ response: { data: { detail: "El rol tiene usuarios asignados" } } });
    await montar();

    await user.click(within(tarjetaDe("visor")).getByTitle("Eliminar"));
    expect(await screen.findByText("El rol tiene usuarios asignados")).toBeInTheDocument();
  });

  it("el panel de permisos los agrupa por prefijo del código", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Gestionar permisos"));

    expect(screen.getByText("Seleccionar permisos")).toBeInTheDocument();
    expect(screen.getByText("users")).toBeInTheDocument();
    expect(screen.getByText("transactions")).toBeInTheDocument();
    // Los tags de permisos actuales se ocultan mientras el panel está abierto
    expect(within(tarjetaDe("admin")).getAllByText("users:read")).toHaveLength(1);
  });

  it("guarda los permisos seleccionados del rol", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Gestionar permisos"));
    const panel = screen.getByText("Seleccionar permisos").closest("div");
    const checks = within(panel).getAllByRole("checkbox");

    // admin ya tiene users:read y users:write tildados; transactions:read no
    expect(checks[0]).toBeChecked();
    expect(checks[1]).toBeChecked();
    expect(checks[2]).not.toBeChecked();

    await user.click(checks[1]);           // saca users:write
    await user.click(checks[2]);           // agrega transactions:read
    await user.click(within(panel).getByRole("button", { name: /Guardar permisos/ }));

    await waitFor(() => expect(assignPermissions).toHaveBeenCalledWith(1, [1, 3]));
    await waitFor(() => expect(screen.queryByText("Seleccionar permisos")).not.toBeInTheDocument());
  });

  it("el botón Permisos cierra el panel si ya estaba abierto y Cancelar no guarda", async () => {
    const user = userEvent.setup();
    await montar();

    const boton = () => within(tarjetaDe("admin")).getByTitle("Gestionar permisos");
    await user.click(boton());
    expect(screen.getByText("Seleccionar permisos")).toBeInTheDocument();

    await user.click(boton());
    expect(screen.queryByText("Seleccionar permisos")).not.toBeInTheDocument();

    await user.click(boton());
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText("Seleccionar permisos")).not.toBeInTheDocument();
    expect(assignPermissions).not.toHaveBeenCalled();
  });

  it("muestra el error de la API al guardar permisos", async () => {
    const user = userEvent.setup();
    assignPermissions.mockRejectedValue({ response: { data: { detail: "Permiso inexistente" } } });
    await montar();

    await user.click(within(tarjetaDe("visor")).getByTitle("Gestionar permisos"));
    await user.click(screen.getByRole("button", { name: /Guardar permisos/ }));

    expect(await screen.findByText("Permiso inexistente")).toBeInTheDocument();
  });

  it("editar un rol cierra el panel de permisos y viceversa", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(tarjetaDe("admin")).getByTitle("Gestionar permisos"));
    expect(screen.getByText("Seleccionar permisos")).toBeInTheDocument();

    await user.click(within(tarjetaDe("admin")).getByTitle("Editar"));
    expect(screen.queryByText("Seleccionar permisos")).not.toBeInTheDocument();

    await user.click(within(tarjetaDe("visor")).getByTitle("Gestionar permisos"));
    expect(screen.getByText("Seleccionar permisos")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Guardar$/ })).not.toBeInTheDocument();
  });
});
