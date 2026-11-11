import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/security", () => ({
  getUsers: vi.fn(), getRoles: vi.fn(), createUser: vi.fn(), updateUser: vi.fn(), deleteUser: vi.fn(),
  assignRoles: vi.fn(), adminChangePassword: vi.fn(), getGroups: vi.fn(), assignUserGroups: vi.fn(),
}));
vi.mock("../../../api/dobleFactor", async (orig) => ({ ...(await orig()), resetear2fa: vi.fn() }));

import { getUsers, getRoles } from "../../../api/security";
import { resetear2fa } from "../../../api/dobleFactor";
import UsersPage from "./UsersPage";
import { useAuthStore } from "../../../context/authStore";

const ana = { id: 10, username: "ana", email: "a@x", full_name: "Ana", is_active: true, roles: [], totp_activo: true };
const beto = { id: 11, username: "beto", email: "b@x", full_name: "Beto", is_active: true, roles: [], totp_activo: false };

function sesion(mfa) {
  useAuthStore.setState({
    token: "tok", user: { username: "admin" }, mfa,
    permissions: { modules: ["security"], actions: { security: ["users:read", "users:write"] } },
  });
}

async function montar() {
  render(<MemoryRouter><UsersPage /></MemoryRouter>);
  await waitFor(() => expect(screen.queryByText("Cargando...")).not.toBeInTheDocument());
}

const filaDe = (u) => screen.getAllByText(u)[0].closest("tr");

describe("UsersPage: doble factor", () => {
  beforeEach(() => {
    getUsers.mockResolvedValue({ data: [ana, beto], total: 2 });
    getRoles.mockResolvedValue([]);
  });

  it("con la función apagada no muestra nada del 2FA", async () => {
    sesion({ habilitado: false, activo: false });
    await montar();
    expect(screen.queryByText("2FA")).toBeNull();
    expect(screen.queryByTitle("Resetear doble factor")).toBeNull();
  });

  it("marca quién tiene 2FA y ofrece resetearlo sólo a esos", async () => {
    sesion({ habilitado: true, activo: true });
    await montar();
    expect(within(filaDe("ana")).getByText("2FA")).toBeInTheDocument();
    expect(within(filaDe("beto")).queryByText("2FA")).toBeNull();
    expect(within(filaDe("beto")).queryByTitle("Resetear doble factor")).toBeNull();
  });

  it("el reset pide confirmación, llama al backend y recarga", async () => {
    sesion({ habilitado: true, activo: true });
    resetear2fa.mockResolvedValue({ user_id: 10, totp_activo: false });
    const user = userEvent.setup();
    await montar();
    await user.click(within(filaDe("ana")).getByTitle("Resetear doble factor"));
    const dialogo = screen.getByRole("dialog", { name: "Resetear el doble factor de ana" });
    expect(resetear2fa).not.toHaveBeenCalled();
    await user.click(within(dialogo).getByRole("button", { name: "Resetear" }));
    await waitFor(() => expect(resetear2fa).toHaveBeenCalledWith(10));
    await waitFor(() => expect(getUsers).toHaveBeenCalledTimes(2));
  });

  it("si falla el reset muestra el motivo", async () => {
    sesion({ habilitado: true, activo: true });
    resetear2fa.mockRejectedValue({ response: { data: { detail: "El servicio de doble factor no responde." } } });
    const user = userEvent.setup();
    await montar();
    await user.click(within(filaDe("ana")).getByTitle("Resetear doble factor"));
    await user.click(screen.getByRole("button", { name: "Resetear" }));
    expect(await screen.findByText("El servicio de doble factor no responde.")).toBeInTheDocument();
  });
});
