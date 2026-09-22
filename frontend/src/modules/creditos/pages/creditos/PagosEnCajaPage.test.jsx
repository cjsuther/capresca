import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PagosEnCajaPage from "./PagosEnCajaPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { pagosEnCaja: vi.fn(), descargarPagosEnCajaExcel: vi.fn() },
}));

const DATOS = {
  total: 120, total_pagado: 8000000,
  items: [
    { credito_id: 900, cuota: 3, cliente: "PEREZ JUAN", nro_recibo: 5501, via_pago: "EFECTIVO",
      cajero: "ana", fecha_pago: "2026-03-02", total_pagado: 58000 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.pagosEnCaja.mockResolvedValue(DATOS);
});

describe("Pagos de créditos en caja", () => {
  it("carga la primera página al entrar", async () => {
    render(<PagosEnCajaPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(creditos.pagosEnCaja).toHaveBeenCalledWith(
      { desde: undefined, hasta: undefined, credito_id: undefined, limit: 25, offset: 0 });
    expect(screen.getByText(/120 pagos/)).toBeInTheDocument();
  });

  it("filtra por período y número de crédito", async () => {
    const u = userEvent.setup();
    render(<PagosEnCajaPage />);
    await screen.findByText("PEREZ JUAN");

    const [desde, hasta] = document.querySelectorAll('input[type="date"]');
    await u.type(desde, "2026-03-01");
    await u.type(hasta, "2026-03-31");
    await u.type(screen.getByLabelText("N° crédito"), "900");
    await u.click(screen.getByRole("button", { name: "Filtrar" }));

    await waitFor(() => expect(creditos.pagosEnCaja).toHaveBeenLastCalledWith(
      { desde: "2026-03-01", hasta: "2026-03-31", credito_id: 900, limit: 25, offset: 0 }));
  });

  it("el Excel sale con los mismos filtros", async () => {
    const u = userEvent.setup();
    render(<PagosEnCajaPage />);
    await screen.findByText("PEREZ JUAN");

    await u.type(screen.getByLabelText("N° crédito"), "900");
    await u.click(screen.getByRole("button", { name: "Descargar Excel" }));
    expect(creditos.descargarPagosEnCajaExcel).toHaveBeenCalledWith(
      { desde: undefined, hasta: undefined, credito_id: 900 });
  });

  it("sin pagos en el período lo dice", async () => {
    creditos.pagosEnCaja.mockResolvedValue({ total: 0, total_pagado: 0, items: [] });
    render(<PagosEnCajaPage />);
    expect(await screen.findByText("Sin pagos en el período")).toBeInTheDocument();
  });
});
