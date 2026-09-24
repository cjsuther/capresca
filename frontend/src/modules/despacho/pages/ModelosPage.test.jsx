import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ModelosPage from "./ModelosPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const modelo = (extra = {}) => ({
  id: 3, codigo: 103, descripcion: "TRANSFERENCIA", tipo: "RES", es_seguros: false,
  plantilla: "<p>VISTO…</p>", tiene_plantilla: true, activo: true, ...extra,
});

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "modelos:write"]);
  api.getModelos.mockResolvedValue([modelo()]);
  document.execCommand = vi.fn();
});

describe("modelos de resolución", () => {
  it("lista los modelos con su código y si tienen texto", async () => {
    render(<ModelosPage />);
    expect(await screen.findByText("TRANSFERENCIA")).toBeInTheDocument();
    expect(screen.getByText("103")).toBeInTheDocument();
    expect(screen.getByText("con texto")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
  });

  it("los inactivos sólo se traen si se piden", async () => {
    const user = userEvent.setup();
    render(<ModelosPage />);
    await screen.findByText("TRANSFERENCIA");
    expect(api.getModelos).toHaveBeenCalledWith(expect.objectContaining({ incluir_inactivos: false }));

    await user.click(screen.getByLabelText("Ver inactivos"));
    await waitFor(() => expect(api.getModelos).toHaveBeenLastCalledWith(
      expect.objectContaining({ incluir_inactivos: true })));
  });

  it("guarda un modelo nuevo con su descripción y su plantilla", async () => {
    const user = userEvent.setup();
    api.crearModelo.mockResolvedValue(modelo({ id: 9 }));
    render(<ModelosPage />);
    await screen.findByText("TRANSFERENCIA");

    await user.click(screen.getByRole("button", { name: /Nuevo modelo/ }));
    await user.type(screen.getByLabelText("Descripción"), "BAJA DE CREDITO");
    await user.selectOptions(screen.getByLabelText("Tipo del modelo"), "DIS");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.crearModelo).toHaveBeenCalledWith(
      expect.objectContaining({ descripcion: "BAJA DE CREDITO", tipo: "DIS" })));
  });

  it("sin permiso de escritura no se puede editar ni crear", async () => {
    sesion(["resoluciones:read"]);
    render(<ModelosPage />);
    await screen.findByText("TRANSFERENCIA");
    expect(screen.queryByRole("button", { name: /Nuevo modelo/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Editar TRANSFERENCIA/ })).not.toBeInTheDocument();
  });

  it("avisa cuando el backend rechaza el modelo", async () => {
    const user = userEvent.setup();
    api.crearModelo.mockRejectedValue(
      { response: { data: { detail: "La descripción es obligatoria." } } });
    render(<ModelosPage />);
    await screen.findByText("TRANSFERENCIA");

    await user.click(screen.getByRole("button", { name: /Nuevo modelo/ }));
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("La descripción es obligatoria.")).toBeInTheDocument();
  });
});
