import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SinDebitoPage from "./SinDebitoPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { creditosSinDebito: vi.fn(), lineas: vi.fn() },
}));

const DATOS = {
  total: 40, total_saldo: 12000000,
  items: [
    { credito_id: 900, cliente: "PEREZ JUAN", cuil: "20-1-1", linea: "PERSONAL", sueldo: 700000, saldo: 300000 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.creditosSinDebito.mockResolvedValue(DATOS);
  creditos.lineas.mockResolvedValue([{ id: 12, nombre: "PERSONAL" }, { id: 13, nombre: "ESPECIAL" }]);
});

describe("Créditos sin débito automático", () => {
  it("lista la primera página y el saldo total", async () => {
    render(<SinDebitoPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(creditos.creditosSinDebito).toHaveBeenCalledWith({ q: undefined, linea_id: undefined, limit: 25, offset: 0 });
    expect(screen.getByText(/40 créditos/)).toBeInTheDocument();
  });

  it("buscar y filtrar por línea recargan desde la primera página", async () => {
    const u = userEvent.setup();
    render(<SinDebitoPage />);
    await screen.findByText("PEREZ JUAN");

    await u.type(screen.getByPlaceholderText("Buscar cliente / CUIL"), "perez");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => expect(creditos.creditosSinDebito).toHaveBeenLastCalledWith(
      { q: "perez", linea_id: undefined, limit: 25, offset: 0 }));

    await u.selectOptions(screen.getByLabelText("Línea"), "13");
    await waitFor(() => expect(creditos.creditosSinDebito).toHaveBeenLastCalledWith(
      { q: "perez", linea_id: 13, limit: 25, offset: 0 }));
  });

  it("Limpiar filtros vuelve al listado completo", async () => {
    const u = userEvent.setup();
    render(<SinDebitoPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Línea"), "12");
    await waitFor(() => expect(creditos.creditosSinDebito).toHaveBeenLastCalledWith(
      expect.objectContaining({ linea_id: 12 })));

    await u.click(screen.getByRole("button", { name: /limpiar filtros/i }));
    await waitFor(() => expect(creditos.creditosSinDebito).toHaveBeenLastCalledWith(
      { q: undefined, linea_id: undefined, limit: 25, offset: 0 }));
  });

  it("paginar pide el offset siguiente", async () => {
    const u = userEvent.setup();
    render(<SinDebitoPage />);
    await screen.findByText("PEREZ JUAN");
    await u.click(screen.getByRole("button", { name: /Siguiente/ }));
    await waitFor(() => expect(creditos.creditosSinDebito).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 25 })));
  });

  it("si la consulta falla lo informa", async () => {
    creditos.creditosSinDebito.mockRejectedValue(new Error("Error 500"));
    render(<SinDebitoPage />);
    expect(await screen.findByText("Error 500")).toBeInTheDocument();
  });
});
