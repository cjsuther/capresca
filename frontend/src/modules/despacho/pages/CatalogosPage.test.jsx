import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CatalogosPage from "./CatalogosPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const serie = (extra = {}) => ({ serie: 1, nombre: "GENERAL", orden: 1, activa: true, en_uso: true, ...extra });

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

const fila = async (texto) => (await screen.findByText(texto)).closest("tr");

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "series:write"]);
  api.getSeries.mockResolvedValue([
    serie(),
    serie({ serie: 6, nombre: "JUEGOS", orden: 2 }),
    serie({ serie: 9, nombre: "POR ERROR", orden: 3, en_uso: false }),
    serie({ serie: 4, nombre: "SEGUROS", orden: 4, activa: false }),
  ]);
});

describe("catálogo de series", () => {
  it("lista todas las series, también las inactivas", async () => {
    render(<CatalogosPage />);
    expect(await screen.findByRole("tab", { name: "Series de numeración" })).toHaveAttribute("aria-selected", "true");
    expect(api.getSeries).toHaveBeenCalledWith({ incluir_inactivas: true });
    expect(await fila("SEGUROS")).toHaveTextContent("Inactiva");
    expect(await fila("JUEGOS")).toHaveTextContent("Activa");
  });

  it("crea una serie con su número y nombre", async () => {
    api.crearSerie.mockResolvedValue(serie({ serie: 8, nombre: "RECURSOS HUMANOS", orden: 5, en_uso: false }));
    const u = userEvent.setup();
    render(<CatalogosPage />);
    await u.click(await screen.findByRole("button", { name: /Nueva serie/ }));
    const dialogo = screen.getByRole("dialog", { name: "Nueva serie" });
    await u.type(within(dialogo).getByLabelText("Número de serie"), "8");
    await u.type(within(dialogo).getByLabelText("Nombre de la serie"), "Recursos humanos");
    await u.click(within(dialogo).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.crearSerie).toHaveBeenCalledWith({ serie: 8, nombre: "Recursos humanos", orden: null }));
    expect(await screen.findByText("Serie 8 · RECURSOS HUMANOS guardada.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("no deja crear sin número", async () => {
    const u = userEvent.setup();
    render(<CatalogosPage />);
    await u.click(await screen.findByRole("button", { name: /Nueva serie/ }));
    const dialogo = screen.getByRole("dialog");
    await u.type(within(dialogo).getByLabelText("Nombre de la serie"), "X");
    await u.click(within(dialogo).getByRole("button", { name: "Guardar" }));
    expect(within(dialogo).getByText(/número de la serie es obligatorio/)).toBeInTheDocument();
    expect(api.crearSerie).not.toHaveBeenCalled();
  });

  it("al editar, el número no se cambia y muestra el error del servidor", async () => {
    api.editarSerie.mockRejectedValue({ response: { data: { detail: "El nombre GENERAL ya lo usa la serie 1." } } });
    const u = userEvent.setup();
    render(<CatalogosPage />);
    await u.click(await screen.findByRole("button", { name: "Editar serie 6" }));
    const dialogo = screen.getByRole("dialog", { name: "Serie 6" });
    expect(within(dialogo).getByLabelText("Número de serie")).toBeDisabled();
    const nombre = within(dialogo).getByLabelText("Nombre de la serie");
    await u.clear(nombre);
    await u.type(nombre, "GENERAL");
    await u.click(within(dialogo).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.editarSerie).toHaveBeenCalledWith(6, { nombre: "GENERAL", orden: 2 }));
    expect(await within(dialogo).findByText(/ya lo usa la serie 1/)).toBeInTheDocument();
  });

  it("activa y desactiva; la serie por defecto no", async () => {
    api.activarSerie.mockResolvedValue({});
    const u = userEvent.setup();
    render(<CatalogosPage />);
    expect(within(await fila("GENERAL")).queryByRole("button", { name: /activar/i })).not.toBeInTheDocument();
    await u.click(within(await fila("SEGUROS")).getByRole("button", { name: "Activar" }));
    await waitFor(() => expect(api.activarSerie).toHaveBeenCalledWith(4, true));
    await u.click(within(await fila("JUEGOS")).getByRole("button", { name: "Desactivar" }));
    await waitFor(() => expect(api.activarSerie).toHaveBeenCalledWith(6, false));
  });

  it("sólo ofrece borrar las series sin uso", async () => {
    api.eliminarSerie.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const u = userEvent.setup();
    render(<CatalogosPage />);
    expect(within(await fila("JUEGOS")).queryByRole("button", { name: /Borrar/ })).not.toBeInTheDocument();
    await u.click(within(await fila("POR ERROR")).getByRole("button", { name: "Borrar serie 9" }));
    await waitFor(() => expect(api.eliminarSerie).toHaveBeenCalledWith(9));
  });

  it("sin el permiso, sólo consulta", async () => {
    sesion(["resoluciones:read"]);
    render(<CatalogosPage />);
    await screen.findByText("JUEGOS");
    expect(screen.queryByRole("button", { name: /Nueva serie/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Editar serie/ })).not.toBeInTheDocument();
    expect(screen.getByText(/hace falta el permiso/)).toBeInTheDocument();
  });
});
