import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IndicesPage from "./IndicesPage";
import * as api from "../../../api/configuraciones";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarIndices: vi.fn(), crearIndice: vi.fn(), editarIndice: vi.fn(), bajaIndice: vi.fn(), reactivarIndice: vi.fn(),
}));

const BADLAR = { id: 1, codigo: "BADLAR", nombre: "BADLAR privados", valor: 45.5, fuente: "BCRA", fecha_valor: "2026-09-01", activo: true };

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "ana" },
  permissions: { modules: ["configuraciones"], actions: { configuraciones: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["indices:read", "indices:write"]);
  api.listarIndices.mockResolvedValue({ items: [BADLAR] });
  api.editarIndice.mockResolvedValue({});
  api.crearIndice.mockResolvedValue({});
  api.bajaIndice.mockResolvedValue({});
});

describe("Índices de referencia", () => {
  it("muestra el valor vigente y la fecha", async () => {
    render(<IndicesPage />);
    const fila = (await screen.findByText("BADLAR")).closest("tr");
    expect(within(fila).getByText("45,5 %")).toBeInTheDocument();
    expect(within(fila).getByText("1/9/2026")).toBeInTheDocument();
  });

  it("actualiza el valor de un índice", async () => {
    const u = userEvent.setup();
    render(<IndicesPage />);
    await u.click(within((await screen.findByText("BADLAR")).closest("tr")).getByRole("button", { name: "Actualizar" }));
    const modal = screen.getByRole("dialog", { name: "Actualizar BADLAR" });
    await u.clear(within(modal).getByLabelText(/Valor \(%/));
    await u.type(within(modal).getByLabelText(/Valor \(%/), "48");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.editarIndice).toHaveBeenCalledWith(1, expect.objectContaining({ valor: 48, codigo: "BADLAR" })));
  });

  it("alta de un índice nuevo", async () => {
    const u = userEvent.setup();
    render(<IndicesPage />);
    await u.click(await screen.findByRole("button", { name: /Nuevo índice/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo índice" });
    await u.type(within(modal).getByLabelText("Código"), "CER");
    await u.type(within(modal).getByLabelText("Nombre"), "Coeficiente de estabilización");
    await u.type(within(modal).getByLabelText(/Valor \(%/), "33");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.crearIndice).toHaveBeenCalledWith(expect.objectContaining({ codigo: "CER", valor: 33, fecha_valor: null })));
  });

  it("la baja avisa que las líneas publicadas siguen cotizando", async () => {
    const u = userEvent.setup();
    render(<IndicesPage />);
    await u.click(within((await screen.findByText("BADLAR")).closest("tr")).getByRole("button", { name: "Dar de baja" }));
    const conf = screen.getByRole("dialog", { name: "Dar de baja el índice" });
    expect(within(conf).getByText(/siguen cotizando/)).toBeInTheDocument();
    await u.click(within(conf).getByRole("button", { name: "Dar de baja" }));
    await waitFor(() => expect(api.bajaIndice).toHaveBeenCalledWith(1));
  });

  it("con sólo lectura no se edita", async () => {
    sesion(["indices:read"]);
    render(<IndicesPage />);
    await screen.findByText("BADLAR");
    expect(screen.queryByRole("button", { name: "Actualizar" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Nuevo índice/ })).toBeNull();
  });
});
