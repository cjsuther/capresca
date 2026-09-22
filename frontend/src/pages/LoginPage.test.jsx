import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./LoginPage";
import { useAuthStore } from "../context/authStore";
import * as authApi from "../api/auth";

const SESION = {
  access_token: "tok-1",
  user: { id: 1, username: "ana", full_name: "Ana" },
  permissions: { modules: ["cajeros"], actions: { cajeros: ["rules:read"] } },
};

function montar(ruta = "/login") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<p>tablero</p>} />
      </Routes>
    </MemoryRouter>
  );
}

async function ingresar(user) {
  await user.type(screen.getByPlaceholderText("usuario"), "ana");
  await user.type(screen.getByPlaceholderText("••••••••"), "secreta");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, permissions: null });
    delete window.location;
    window.location = { assign: vi.fn(), href: "" };
  });

  it("guarda la sesión y va al tablero", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue(SESION);
    const user = userEvent.setup();
    montar();
    await ingresar(user);

    await waitFor(() => expect(screen.getByText("tablero")).toBeInTheDocument());
    expect(useAuthStore.getState().token).toBe("tok-1");
    expect(useAuthStore.getState().permissions.modules).toEqual(["cajeros"]);
  });

  it("muestra el error de credenciales y no guarda sesión", async () => {
    vi.spyOn(authApi, "login").mockRejectedValue({ response: { data: { detail: "Credenciales inválidas" } } });
    const user = userEvent.setup();
    montar();
    await ingresar(user);

    expect(await screen.findByText("Credenciales inválidas")).toBeInTheDocument();
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("si el error no trae detalle muestra un mensaje genérico", async () => {
    vi.spyOn(authApi, "login").mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    expect(await screen.findByText("Error al iniciar sesión")).toBeInTheDocument();
  });

  it("con sesión abierta no muestra el formulario", () => {
    useAuthStore.setState({ token: "tok", user: { username: "ana" }, permissions: { modules: [] } });
    montar();
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });

  // El ?next= existía sólo para volver a la SPA vieja de Créditos (/creditos/), ya retirada:
  // ahora cualquier next se ignora, así el login no puede usarse como open redirect.
  it.each([
    ["/creditos/", "ruta local"],
    ["//evil.com", "protocolo relativo"],
    ["https://evil.com", "absoluta"],
  ])("ignora el parámetro next %s (%s) y va al tablero", async (next) => {
    vi.spyOn(authApi, "login").mockResolvedValue(SESION);
    const user = userEvent.setup();
    montar(`/login?next=${encodeURIComponent(next)}`);
    await ingresar(user);

    await waitFor(() => expect(screen.getByText("tablero")).toBeInTheDocument());
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});
