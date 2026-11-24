import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/security", () => ({
  searchUsers: vi.fn(), getRoles: vi.fn(), createUser: vi.fn(), updateUser: vi.fn(), deleteUser: vi.fn(),
  assignRoles: vi.fn(), adminChangePassword: vi.fn(), getGroups: vi.fn(), assignUserGroups: vi.fn(),
}));

import { getGroups, getRoles, searchUsers } from "../../../api/security";
import UsersPage, { leerFiltros } from "./UsersPage";
import { useAuthStore } from "../../../context/authStore";

const ROLES = [{ id: 1, name: "admin" }, { id: 2, name: "cajero" }];
const GRUPOS = [{ id: 7, name: "Tesorería", is_active: true, roles: [] }];
const usuario = (i) => ({
  id: i, username: `u${i}`, email: `u${i}@x.com`, full_name: `Usuario ${i}`, is_active: true, roles: [], groups: [],
});
const pagina = (items, total = items.length, pages = 1, extra = {}) =>
  ({ items, total, page: 1, page_size: 25, pages, ...extra });

function sesion({ mfa = false, grupos = false } = {}) {
  useAuthStore.setState({
    token: "tok", user: { username: "admin" }, mfa: { habilitado: mfa, activo: mfa },
    permissions: {
      modules: ["security"],
      actions: { security: ["users:read", "users:write", ...(grupos ? ["groups:read"] : [])] },
    },
  });
}

function Url() {
  const { search } = useLocation();
  return <output data-testid="url">{search}</output>;
}

const url = () => new URLSearchParams(screen.getByTestId("url").textContent);
const ultimaLlamada = () => searchUsers.mock.calls.at(-1)[0];

async function montar(ruta = "/modules/security/users") {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes><Route path="/modules/security/users" element={<><UsersPage /><Url /></>} /></Routes>
    </MemoryRouter>,
  );
  await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
}

describe("UsersPage: filtros, orden y paginado", () => {
  beforeEach(() => {
    sesion();
    searchUsers.mockReset().mockResolvedValue(pagina([usuario(1), usuario(2)]));
    getRoles.mockResolvedValue(ROLES);
    getGroups.mockResolvedValue(GRUPOS);
  });

  it("pide la primera página de 25 ordenada por nombre, sin filtros", async () => {
    await montar();
    expect(searchUsers).toHaveBeenCalledTimes(1);
    expect(ultimaLlamada()).toEqual({
      q: "", role_id: "", group_id: "", estado: "", mfa: "",
      sort: "nombre", order: "asc", page: 1, page_size: 25,
    });
    expect(url().toString()).toBe("");
  });

  it("toma filtros, orden y página de la URL (link compartido o refresh)", async () => {
    sesion({ mfa: true, grupos: true });
    await montar("/modules/security/users?q=ana&rol=2&grupo=7&estado=inactivo&mfa=si&orden=email&dir=desc&pagina=2&tam=50");
    expect(ultimaLlamada()).toEqual({
      q: "ana", role_id: "2", group_id: "7", estado: "inactivo", mfa: true,
      sort: "email", order: "desc", page: 2, page_size: 50,
    });
    expect(screen.getByLabelText("Buscar usuarios")).toHaveValue("ana");
    await waitFor(() => expect(screen.getByLabelText("Filtrar por rol")).toHaveValue("2"));
    expect(screen.getByLabelText("Filtrar por estado")).toHaveValue("inactivo");
    expect(screen.getByLabelText("Filtrar por doble factor")).toHaveValue("si");
    expect(screen.getByLabelText("Usuarios por página")).toHaveValue("50");
  });

  it("la búsqueda espera a que se deje de tipear, va a la URL y vuelve a la página 1", async () => {
    const user = userEvent.setup();
    await montar("/modules/security/users?pagina=3");
    searchUsers.mockClear();

    await user.type(screen.getByLabelText("Buscar usuarios"), "carla");
    await waitFor(() => expect(searchUsers).toHaveBeenCalledTimes(1));
    expect(ultimaLlamada()).toMatchObject({ q: "carla", page: 1 });
    expect(url().get("q")).toBe("carla");
    expect(url().get("pagina")).toBeNull();
  });

  it("los selects filtran y quedan en la URL; Limpiar los saca", async () => {
    const user = userEvent.setup();
    await montar();
    await waitFor(() => expect(screen.getByRole("option", { name: "cajero" })).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Filtrar por rol"), "2");
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ role_id: "2" }));
    await user.selectOptions(screen.getByLabelText("Filtrar por estado"), "activo");
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ role_id: "2", estado: "activo" }));
    expect(url().get("rol")).toBe("2");
    expect(url().get("estado")).toBe("activo");

    await user.click(screen.getByRole("button", { name: /Limpiar filtros/ }));
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ role_id: "", estado: "" }));
    expect(url().toString()).toBe("");
    expect(screen.queryByRole("button", { name: /Limpiar filtros/ })).not.toBeInTheDocument();
  });

  it("los filtros de grupo y 2FA sólo aparecen si corresponden", async () => {
    await montar();
    expect(screen.queryByLabelText("Filtrar por grupo")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Filtrar por doble factor")).not.toBeInTheDocument();
  });

  it("filtra por grupo y por doble factor", async () => {
    sesion({ mfa: true, grupos: true });
    const user = userEvent.setup();
    await montar();
    await waitFor(() => expect(screen.getByRole("option", { name: "Tesorería" })).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Filtrar por grupo"), "7");
    await user.selectOptions(screen.getByLabelText("Filtrar por doble factor"), "no");
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ group_id: "7", mfa: false }));
  });

  it("el paginador muestra el rango y el total y avanza/retrocede", async () => {
    searchUsers.mockResolvedValue(pagina(Array.from({ length: 25 }, (_, i) => usuario(i + 1)), 60, 3));
    const user = userEvent.setup();
    await montar();

    expect(screen.getByText("1–25 de 60 usuarios")).toBeInTheDocument();
    expect(screen.getByText("1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Página anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Página siguiente" }));
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ page: 2 }));
    expect(url().get("pagina")).toBe("2");
    await waitFor(() => expect(screen.getByText("26–50 de 60 usuarios")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Página anterior" }));
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ page: 1 }));
  });

  it("cambiar el tamaño de página vuelve a la primera", async () => {
    const user = userEvent.setup();
    await montar("/modules/security/users?pagina=2");
    await user.selectOptions(screen.getByLabelText("Usuarios por página"), "100");
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ page: 1, page_size: 100 }));
    expect(url().get("tam")).toBe("100");
  });

  it("los encabezados ordenan y un segundo clic invierte el sentido", async () => {
    const user = userEvent.setup();
    await montar();
    const email = screen.getByRole("columnheader", { name: /Email/ });
    expect(email).toHaveAttribute("aria-sort", "none");

    await user.click(within(email).getByRole("button"));
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ sort: "email", order: "asc" }));
    expect(email).toHaveAttribute("aria-sort", "ascending");

    await user.click(within(email).getByRole("button"));
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ sort: "email", order: "desc" }));
    expect(url().get("dir")).toBe("desc");
  });

  it("estado vacío: sin usuarios, o sin coincidencias con botón para limpiar", async () => {
    searchUsers.mockResolvedValue(pagina([], 0));
    await montar();
    expect(screen.getByText("Todavía no hay usuarios.")).toBeInTheDocument();
    expect(screen.getByText("Sin resultados")).toBeInTheDocument();
  });

  it("estado vacío con filtros ofrece limpiarlos", async () => {
    searchUsers.mockResolvedValue(pagina([], 0));
    const user = userEvent.setup();
    await montar("/modules/security/users?q=zzz");
    expect(screen.getByText("Ningún usuario coincide con los filtros.")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Limpiar filtros/ })[0]);
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ q: "" }));
    expect(screen.getByLabelText("Buscar usuarios")).toHaveValue("");
  });

  it("una página fuera de rango salta a la última", async () => {
    searchUsers.mockImplementation(async ({ page }) =>
      (page > 2 ? pagina([], 30, 2) : pagina([usuario(26)], 30, 2, { page })));
    await montar("/modules/security/users?pagina=9");
    await waitFor(() => expect(ultimaLlamada()).toMatchObject({ page: 2 }));
    await waitFor(() => expect(screen.getByText("u26")).toBeInTheDocument());
    expect(url().get("pagina")).toBe("2");
  });
});

describe("leerFiltros", () => {
  it("descarta valores inválidos de la URL", () => {
    const f = leerFiltros(new URLSearchParams("rol=abc&grupo=-3&estado=bloqueado&mfa=x&orden=hash&dir=up&pagina=0&tam=7"));
    expect(f).toEqual({
      q: "", rol: "", grupo: "", estado: "", mfa: "", orden: "nombre", dir: "asc", pagina: 1, tam: 25,
    });
  });
});
