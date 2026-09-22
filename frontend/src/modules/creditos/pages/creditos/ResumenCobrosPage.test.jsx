import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResumenCobrosPage from "./ResumenCobrosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({ creditos: { resumenCobros: vi.fn() } }));

const DATOS = {
  items: [
    { periodo: "2026-08", cuotas: 10, creditos: 5, capital: 5000, interes: 300, iva: 30, mora: 20, seguro: 10, gastos: 5, total: 5365 },
    { periodo: "2026-07", cuotas: 8, creditos: 4, capital: 4000, interes: 200, iva: 20, mora: 10, seguro: 5, gastos: 5, total: 4235 },
  ],
  total: { cuotas: 18, capital: 9000, interes: 500, mora: 30, total: 9600 },
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.resumenCobros.mockResolvedValue(DATOS);
});

describe("Resumen de cobros de créditos", () => {
  it("carga el resumen completo al entrar, con sus indicadores", async () => {
    render(<ResumenCobrosPage />);
    expect(await screen.findByText("2026-08")).toBeInTheDocument();
    expect(creditos.resumenCobros).toHaveBeenCalledWith({ desde: undefined, hasta: undefined });
    expect(screen.getByText("Cuotas cobradas")).toBeInTheDocument();
    expect(screen.getByText("Total cobrado")).toBeInTheDocument();
  });

  it("filtra por período", async () => {
    const u = userEvent.setup();
    render(<ResumenCobrosPage />);
    await screen.findByText("2026-08");

    const [desde, hasta] = document.querySelectorAll('input[type="date"]');
    await u.type(desde, "2026-01-01");
    await u.type(hasta, "2026-06-30");
    await u.click(screen.getByRole("button", { name: "Ver" }));
    await waitFor(() => expect(creditos.resumenCobros).toHaveBeenLastCalledWith(
      { desde: "2026-01-01", hasta: "2026-06-30" }));
  });

  it("Limpiar filtros recarga sin arrastrar el período viejo (H-206)", async () => {
    const u = userEvent.setup();
    render(<ResumenCobrosPage />);
    await screen.findByText("2026-08");

    const [desde] = document.querySelectorAll('input[type="date"]');
    await u.type(desde, "2026-01-01");
    await u.click(screen.getByRole("button", { name: "Ver" }));
    await waitFor(() => expect(creditos.resumenCobros).toHaveBeenLastCalledWith(
      { desde: "2026-01-01", hasta: undefined }));

    await u.click(screen.getByRole("button", { name: /limpiar filtros/i }));
    await waitFor(() => expect(creditos.resumenCobros).toHaveBeenLastCalledWith(
      { desde: undefined, hasta: undefined }));
    expect(desde).toHaveValue("");
  });

  it("ordena en el cliente por la columna elegida", async () => {
    const u = userEvent.setup();
    render(<ResumenCobrosPage />);
    await screen.findByText("2026-08");

    await u.click(screen.getByRole("columnheader", { name: /Capital/ }));   // el KPI también dice "Capital"
    expect(document.querySelectorAll("tbody tr")[0].textContent).toContain("2026-07");
  });

  it("un período sin cobros muestra el vacío", async () => {
    creditos.resumenCobros.mockResolvedValue({ items: [], total: null });
    render(<ResumenCobrosPage />);
    expect(await screen.findByText("Sin cobros en el período.")).toBeInTheDocument();
    expect(screen.queryByText("Cuotas cobradas")).toBeNull();
  });
});
