import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/security", () => ({
  getUsers: vi.fn(),
  getRoles: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
  assignRoles: vi.fn(),
  adminChangePassword: vi.fn(),
}));

import {
  getUsers, getRoles, createUser, updateUser, deleteUser, assignRoles, adminChangePassword,
} from "../../../api/security";
import UsersPage from "./UsersPage";
import { useAuthStore } from "../../../context/authStore";

const ROL_ADMIN = { id: 1, name: "admin", description: "Todo" };
const ROL_CAJERO = { id: 2, name: "cajero", description: null };

const ana = {
  id: 10, username: "ana", email: "ana@x.com", full_name: "Ana Gómez",
  is_active: true, roles: [ROL_ADMIN],
};
const beto = {
  id: 11, username: "beto", email: "beto@x.com", full_name: null,
  is_active: false, roles: [],
};

function sesion(acciones) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["security"], actions: { security: acciones } },
  });
}

async function montar() {
  render(<MemoryRouter><UsersPage /></MemoryRouter>);
  await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
}

// TODO(bug): UsersPage.jsx:176 envuelve cada fila en un <> sin key (la key está en el <tr> interno),
// así que React avisa "Each child in a list should have a unique key" en cada render de la tabla.
// Los tests reflejan el comportamiento actual: el warning no rompe el render.

// El nombre puede aparecer también dentro del panel de roles: la primera coincidencia es la fila.
const filaDe = (username) => screen.getAllByText(username)[0].closest("tr");

describe("UsersPage", () => {
  beforeEach(() => {
    sesion(["users:read", "users:write"]);
    getUsers.mockResolvedValue({ data: [ana, beto], total: 2 });
    getRoles.mockResolvedValue([ROL_ADMIN, ROL_CAJERO]);
    createUser.mockResolvedValue({ id: 12 });
    updateUser.mockResolvedValue({});
    deleteUser.mockResolvedValue({});
    assignRoles.mockResolvedValue({});
    adminChangePassword.mockResolvedValue({});
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("muestra el cargando y después la tabla con estado y roles", async () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("ana")).toBeInTheDocument());
    expect(screen.getByText("ana@x.com")).toBeInTheDocument();
    expect(screen.getByText("Ana Gómez")).toBeInTheDocument();
    expect(within(filaDe("ana")).getByText("Activo")).toBeInTheDocument();
    expect(within(filaDe("beto")).getByText("Inactivo")).toBeInTheDocument();
    // beto no tiene nombre ni roles: guiones
    expect(within(filaDe("beto")).getAllByText("—")).toHaveLength(2);
    expect(within(filaDe("ana")).getByText("admin")).toBeInTheDocument();
  });

  it("avisa cuando falla la carga", async () => {
    getUsers.mockRejectedValue(new Error("500"));
    await montar();
    expect(screen.getByText("Error al cargar datos")).toBeInTheDocument();
  });

  it("sin permiso de escritura no muestra el alta ni las acciones por fila", async () => {
    sesion(["users:read"]);
    await montar();

    expect(screen.queryByRole("button", { name: /Nuevo usuario/ })).not.toBeInTheDocument();
    expect(screen.queryByTitle("Editar")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Desactivar")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Cambiar contraseña")).not.toBeInTheDocument();
  });

  it("crea un usuario con los datos del formulario y recarga la lista", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo usuario/ }));
    const form = screen.getByRole("button", { name: "Crear" }).closest("form");
    const inputs = form.querySelectorAll("input");

    await user.type(inputs[0], "carla");
    await user.type(inputs[1], "carla@x.com");
    await user.type(inputs[2], "secreta123");
    await user.type(inputs[3], "Carla Pérez");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() => expect(createUser).toHaveBeenCalledWith({
      username: "carla", email: "carla@x.com", password: "secreta123", full_name: "Carla Pérez",
    }));
    // Se cierra el formulario y se vuelve a pedir la lista
    await waitFor(() => expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument());
    expect(getUsers).toHaveBeenCalledTimes(2);
  });

  it("muestra el error de la API al crear y deja el formulario abierto", async () => {
    const user = userEvent.setup();
    createUser.mockRejectedValue({ response: { data: { detail: "El usuario ya existe" } } });
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo usuario/ }));
    const inputs = screen.getByRole("button", { name: "Crear" }).closest("form").querySelectorAll("input");
    await user.type(inputs[0], "ana");
    await user.type(inputs[1], "ana@x.com");
    await user.type(inputs[2], "secreta123");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText("El usuario ya existe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear" })).toBeInTheDocument();
  });

  it("el botón de alta funciona como toggle y Cancelar cierra el formulario", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(screen.getByRole("button", { name: /Nuevo usuario/ }));
    expect(screen.getByRole("button", { name: "Crear" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Nuevo usuario/ }));
    expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Nuevo usuario/ }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("button", { name: "Crear" })).not.toBeInTheDocument();
  });

  it("edita email, nombre y estado de un usuario", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Editar"));
    const fila = filaDe("ana");
    const [email, nombre] = fila.querySelectorAll('input[type="text"], input:not([type])');

    await user.clear(email);
    await user.type(email, "nueva@x.com");
    await user.clear(nombre);
    await user.type(nombre, "Ana G.");
    await user.click(within(fila).getByRole("checkbox"));
    await user.click(within(fila).getByRole("button", { name: /Guardar/ }));

    await waitFor(() => expect(updateUser).toHaveBeenCalledWith(10, {
      email: "nueva@x.com", full_name: "Ana G.", is_active: false,
    }));
    await waitFor(() => expect(getUsers).toHaveBeenCalledTimes(2));
  });

  it("cancelar la edición vuelve a la vista de sólo lectura", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Editar"));
    expect(within(filaDe("ana")).getByRole("button", { name: /Guardar/ })).toBeInTheDocument();

    await user.click(within(filaDe("ana")).getByTitle("Cancelar"));
    expect(screen.getByText("ana@x.com")).toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("muestra el error de la API al editar", async () => {
    const user = userEvent.setup();
    updateUser.mockRejectedValue({ response: { data: { detail: "Email inválido" } } });
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Editar"));
    await user.click(within(filaDe("ana")).getByRole("button", { name: /Guardar/ }));

    expect(await screen.findByText("Email inválido")).toBeInTheDocument();
  });

  it("desactiva un usuario previa confirmación", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Desactivar"));

    expect(window.confirm).toHaveBeenCalledWith('¿Desactivar al usuario "ana"?');
    await waitFor(() => expect(deleteUser).toHaveBeenCalledWith(10));
    await waitFor(() => expect(getUsers).toHaveBeenCalledTimes(2));
  });

  it("si se cancela la confirmación no desactiva", async () => {
    const user = userEvent.setup();
    window.confirm.mockReturnValue(false);
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Desactivar"));
    expect(deleteUser).not.toHaveBeenCalled();
  });

  it("avisa si falla la desactivación", async () => {
    const user = userEvent.setup();
    deleteUser.mockRejectedValue(new Error("409"));
    await montar();

    await user.click(within(filaDe("ana")).getByTitle("Desactivar"));
    expect(await screen.findByText("Error al desactivar usuario")).toBeInTheDocument();
  });

  it("asigna roles desde el panel expandible", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(filaDe("ana")).getByRole("button", { name: /Roles/ }));

    const panel = screen.getByText(/Asignar roles a/).closest("td");
    expect(within(panel).getByText("ana")).toBeInTheDocument();
    // Arranca con los roles actuales tildados
    const [chkAdmin, chkCajero] = within(panel).getAllByRole("checkbox");
    expect(chkAdmin).toBeChecked();
    expect(chkCajero).not.toBeChecked();

    await user.click(chkCajero);
    await user.click(chkAdmin);
    await user.click(within(panel).getByRole("button", { name: /Guardar roles/ }));

    await waitFor(() => expect(assignRoles).toHaveBeenCalledWith(10, [2]));
    await waitFor(() => expect(screen.queryByText(/Asignar roles a/)).not.toBeInTheDocument());
  });

  it("el botón Roles cierra el panel si ya estaba abierto y Cancelar no guarda", async () => {
    const user = userEvent.setup();
    await montar();

    const botonRoles = () => within(filaDe("ana")).getByRole("button", { name: /Roles/ });
    await user.click(botonRoles());
    expect(screen.getByText(/Asignar roles a/)).toBeInTheDocument();

    await user.click(botonRoles());
    expect(screen.queryByText(/Asignar roles a/)).not.toBeInTheDocument();

    await user.click(botonRoles());
    await user.click(within(screen.getByText(/Asignar roles a/).closest("td")).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText(/Asignar roles a/)).not.toBeInTheDocument();
    expect(assignRoles).not.toHaveBeenCalled();
  });

  it("avisa si falla el guardado de roles", async () => {
    const user = userEvent.setup();
    assignRoles.mockRejectedValue({ response: { data: { detail: "Rol inexistente" } } });
    await montar();

    await user.click(within(filaDe("ana")).getByRole("button", { name: /Roles/ }));
    await user.click(screen.getByRole("button", { name: /Guardar roles/ }));

    expect(await screen.findByText("Rol inexistente")).toBeInTheDocument();
  });

  it("un admin cambia la contraseña de otro usuario sin pedir la actual", async () => {
    const user = userEvent.setup();
    const { container } = render(<MemoryRouter><UsersPage /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());

    await user.click(within(filaDe("ana")).getByTitle("Cambiar contraseña"));
    expect(screen.getByText("Contraseña de ana")).toBeInTheDocument();

    const inputs = container.querySelectorAll('input[type="password"]');
    expect(inputs).toHaveLength(2); // no pide la contraseña actual
    await user.type(inputs[0], "nueva1234");
    await user.type(inputs[1], "nueva1234");
    // El botón del modal, no el de la fila (ambos se llaman igual)
    await user.click(container.querySelector('form button[type="submit"]'));

    await waitFor(() => expect(adminChangePassword).toHaveBeenCalledWith(10, "nueva1234"));
    await waitFor(() => expect(screen.queryByText("Contraseña de ana")).not.toBeInTheDocument());
  });

  it("cerrar el modal de contraseña no dispara la API", async () => {
    const user = userEvent.setup();
    await montar();

    await user.click(within(filaDe("beto")).getByTitle("Cambiar contraseña"));
    expect(screen.getByText("Contraseña de beto")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText("Contraseña de beto")).not.toBeInTheDocument();
    expect(adminChangePassword).not.toHaveBeenCalled();
  });
});
