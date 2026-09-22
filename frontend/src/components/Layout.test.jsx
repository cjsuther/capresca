import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/auth", () => ({ logout: vi.fn() }));
vi.mock("../api/security", () => ({ changeMyPassword: vi.fn() }));
vi.mock("../api/notifications", () => ({
  getNotifications: vi.fn().mockResolvedValue({ data: [], unread_count: 0 }),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
  markAsRead: vi.fn().mockResolvedValue({}),
  markAllAsRead: vi.fn().mockResolvedValue({}),
}));

import { logout as apiLogout } from "../api/auth";
import { changeMyPassword } from "../api/security";
import { Layout } from "./Layout";
import { useAuthStore } from "../context/authStore";

function montar({ sidebar } = {}) {
  return render(
    <MemoryRouter initialEntries={["/modules/security/users"]}>
      <Routes>
        <Route
          path="/modules/security/users"
          element={<Layout sidebar={sidebar}><p>contenido del módulo</p></Layout>}
        />
        <Route path="/login" element={<p>pantalla de login</p>} />
        <Route path="/dashboard" element={<p>tablero</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const abrirMenuUsuario = async (user) => {
  await user.click(screen.getByRole("button", { name: /Ana Gómez/ }));
};

describe("Layout", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "tok",
      user: { username: "ana", full_name: "Ana Gómez" },
      permissions: { modules: ["security"], actions: {} },
    });
    apiLogout.mockResolvedValue(undefined);
    changeMyPassword.mockResolvedValue(undefined);
  });

  it("renderiza el contenido y el nombre del usuario en la topbar", () => {
    montar();
    expect(screen.getByText("contenido del módulo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ana Gómez/ })).toBeInTheDocument();
    // En mobile se muestra sólo el primer nombre
    expect(screen.getByText("Ana")).toBeInTheDocument();
  });

  it("cae al username cuando el usuario no tiene nombre completo", () => {
    useAuthStore.setState({ user: { username: "ana" } });
    montar();
    expect(screen.getByRole("button", { name: /ana/ })).toBeInTheDocument();
  });

  it("el logo lleva al dashboard", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByAltText("Portezuelo"));
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });

  it("el menú de usuario se abre y se cierra con el overlay", async () => {
    const user = userEvent.setup();
    const { container } = montar();

    await abrirMenuUsuario(user);
    expect(screen.getByRole("button", { name: /Cambiar contraseña/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cerrar sesión/ })).toBeInTheDocument();

    // El overlay invisible que cierra el menú
    await user.click(container.querySelector(".fixed.inset-0.z-10"));
    expect(screen.queryByRole("button", { name: /Cerrar sesión/ })).not.toBeInTheDocument();
  });

  it("cerrar sesión llama a la API, limpia la sesión y va al login", async () => {
    const user = userEvent.setup();
    montar();

    await abrirMenuUsuario(user);
    await user.click(screen.getByRole("button", { name: /Cerrar sesión/ }));

    await waitFor(() => expect(screen.getByText("pantalla de login")).toBeInTheDocument());
    expect(apiLogout).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().permissions).toBeNull();
  });

  it("abre el modal de cambio de contraseña propio (pide la actual) y lo cierra", async () => {
    const user = userEvent.setup();
    const { container } = montar();

    await abrirMenuUsuario(user);
    await user.click(screen.getByRole("button", { name: /Cambiar contraseña/ }));

    expect(screen.getByText("Cambiar mi contraseña")).toBeInTheDocument();
    expect(container.querySelectorAll('input[type="password"]')).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText("Cambiar mi contraseña")).not.toBeInTheDocument();
  });

  it("el modal propio guarda contra changeMyPassword", async () => {
    const user = userEvent.setup();
    const { container } = montar();

    await abrirMenuUsuario(user);
    await user.click(screen.getByRole("button", { name: /Cambiar contraseña/ }));

    const inputs = container.querySelectorAll('input[type="password"]');
    await user.type(inputs[0], "vieja123");
    await user.type(inputs[1], "nueva1234");
    await user.type(inputs[2], "nueva1234");
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));

    await waitFor(() => expect(changeMyPassword).toHaveBeenCalledWith("vieja123", "nueva1234"));
    await waitFor(() => expect(screen.queryByText("Cambiar mi contraseña")).not.toBeInTheDocument());
  });

  it("sin sidebar no hay hamburguesa ni panel lateral", () => {
    montar();
    expect(screen.queryByLabelText("Abrir menú")).not.toBeInTheDocument();
    expect(screen.queryByText("Menú")).not.toBeInTheDocument();
  });

  it("acepta un sidebar como nodo y lo muestra en desktop y en el panel mobile", () => {
    montar({ sidebar: <nav>menú lateral</nav> });
    expect(screen.getAllByText("menú lateral")).toHaveLength(2);
    expect(screen.getByLabelText("Abrir menú")).toBeInTheDocument();
  });

  it("acepta un sidebar como render prop y le pasa el onClose sólo en mobile", () => {
    const sidebar = vi.fn((onClose) => <nav data-cerrable={typeof onClose === "function"}>menú lateral</nav>);
    montar({ sidebar });

    const navs = screen.getAllByText("menú lateral");
    expect(navs[0]).toHaveAttribute("data-cerrable", "true");   // overlay mobile
    expect(navs[1]).toHaveAttribute("data-cerrable", "false");  // desktop
  });

  it("la hamburguesa abre el panel mobile y se cierra con la X y con el fondo", async () => {
    const user = userEvent.setup();
    const { container } = montar({ sidebar: (onClose) => <button onClick={onClose}>ir a usuarios</button> });

    const overlay = () => container.querySelector(".fixed.inset-0.z-50");
    expect(overlay().className).toContain("pointer-events-none");

    await user.click(screen.getByLabelText("Abrir menú"));
    expect(overlay().className).toContain("opacity-100");
    expect(overlay().className).not.toContain("pointer-events-none");

    // La X del header del panel
    await user.click(overlay().querySelector("button"));
    expect(overlay().className).toContain("opacity-0");

    // Vuelve a abrir y cierra tocando el fondo oscuro
    await user.click(screen.getByLabelText("Abrir menú"));
    expect(overlay().className).toContain("opacity-100");
    await user.click(overlay().querySelector(".bg-black\\/50"));
    expect(overlay().className).toContain("opacity-0");
  });

  it("el onClose que recibe el sidebar cierra el panel mobile", async () => {
    const user = userEvent.setup();
    const { container } = montar({ sidebar: (onClose) => <button onClick={onClose}>ir a usuarios</button> });
    const overlay = () => container.querySelector(".fixed.inset-0.z-50");

    await user.click(screen.getByLabelText("Abrir menú"));
    expect(overlay().className).toContain("opacity-100");

    await user.click(screen.getAllByRole("button", { name: "ir a usuarios" })[0]);
    expect(overlay().className).toContain("opacity-0");
  });
});
