import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PendientesCobroPage from "./PendientesCobroPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { pendientesCobro: vi.fn(), verPendientesPdf: vi.fn() },
}));

const DATOS = {
  cantidad: 2, total_cuota: 150000, total_mora: 12000, total: 162000,
  items: [
    { credito_id: 900, cuota_numero: 3, cliente: "PEREZ JUAN", vencimiento: "2026-02-10", dias_mora: 30, importe_cuota: 100000, mora: 9000, total: 109000 },
    { credito_id: 901, cuota_numero: 1, cliente: "GOMEZ ANA", vencimiento: "2026-03-01", dias_mora: 10, importe_cuota: 50000, mora: 3000, total: 53000 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  creditos.pendientesCobro.mockResolvedValue(DATOS);
});
afterEach(() => vi.useRealTimers());

describe("Pendientes de cobro", () => {
  it("genera el informe y muestra los totales de cuota y mora", async () => {
    const u = userEvent.setup();
    render(<PendientesCobroPage />);

    await u.click(screen.getByRole("button", { name: "Generar" }));
    await waitFor(() => expect(creditos.pendientesCobro).toHaveBeenCalledWith("2026-03-15"));
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    // "Mora" también es encabezado de columna: se mira el KPI.
    const kpis = screen.getByText("Cuotas").closest("div").parentElement;
    expect(kpis.textContent).toContain("Mora");
    expect(screen.getByText("#900-3")).toBeInTheDocument();
  });

  it("el PDF sale con la misma fecha de corte", async () => {
    const u = userEvent.setup();
    render(<PendientesCobroPage />);
    const fecha = document.querySelector('input[type="date"]');
    await u.clear(fecha);
    await u.type(fecha, "2026-02-28");
    await u.click(screen.getByRole("button", { name: "PDF" }));
    expect(creditos.verPendientesPdf).toHaveBeenCalledWith("2026-02-28");
  });

  it("si falla lo informa", async () => {
    creditos.pendientesCobro.mockRejectedValue(new Error("Error 503"));
    const u = userEvent.setup();
    render(<PendientesCobroPage />);
    await u.click(screen.getByRole("button", { name: "Generar" }));
    expect(await screen.findByText("Error 503")).toBeInTheDocument();
  });
});
