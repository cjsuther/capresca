import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TableroCarteraPage from "./TableroCarteraPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ctoTablero: vi.fn(), ctoCarteraExcel: vi.fn(async () => {}) },
}));

const TABLERO = {
  generadoEn: "2026-03-15",
  kpis: {
    saldoVigente: 4000000, activos: 12, capitalColocado: 9000000, contratos: 20, ticketPromedio: 450000,
    cobrado: 5000000, cuotasPagadas: 130, moraMonto: 250000, moraPct: 6.3, contratosEnMora: 3,
    recaudadoMes: 600000, aLiquidarMonto: 800000, aLiquidarN: 2, vencen30Monto: 500000,
    vencen30Cuotas: 15, tnaPromedioPond: 58.4, plazoPromedio: 18,
  },
  porEstado: [
    { estado: "ACTIVO", contratos: 12, capital: 6000000 },
    { estado: "A_LIQUIDAR", contratos: 2, capital: 800000 },
    { estado: "CERRADO", contratos: 6, capital: 2200000 },
  ],
  evolucion: [
    { mes: "2026-02", originadoMonto: 900000, originadoN: 3, cobradoMonto: 400000 },
    { mes: "2026-03", originadoMonto: 500000, originadoN: 2, cobradoMonto: 600000 },
  ],
  aging: [
    { bucket: "Al día", contratos: 9, saldo: 3000000 },
    { bucket: "31–60", contratos: 3, saldo: 250000 },
  ],
  porProducto: [{ id: "pp_1", nombre: "PERSONAL", codigo: "CP", contratos: 14, capital: 7000000, saldo: 3500000, mora: 250000, moraPct: 7 }],
  contratos: [
    { id: "c1", numero: "CTO-1", cliente: "PEREZ JUAN", producto: "PERSONAL", productoId: "pp_1",
      estado: "ACTIVO", monto: 500000, saldo: 300000, diasAtraso: 0, moraBucket: "Al día", proxVenc: "2026-04-10", proxCuota: 5 },
    { id: "c2", numero: "CTO-2", cliente: "GOMEZ ANA", producto: "PERSONAL", productoId: "pp_1",
      estado: "A_LIQUIDAR", monto: 400000, saldo: 400000, diasAtraso: 45, moraBucket: "31–60", proxVenc: null },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.ctoTablero.mockResolvedValue(TABLERO);
});

describe("Tablero de cartera", () => {
  it("muestra los indicadores de la cartera", async () => {
    render(<TableroCarteraPage />);
    // "Saldo vigente" es también encabezado de la tabla por línea: se mira el KPI.
    expect(await screen.findByText("12 contratos activos")).toBeInTheDocument();
    expect(screen.getAllByText("Saldo vigente").length).toBeGreaterThan(0);
    expect(screen.getByText(/6\.3% de la cartera · 3 contratos/)).toBeInTheDocument();
    expect(screen.getByText(/datos al 2026-03-15/)).toBeInTheDocument();
  });

  it("el donut y su leyenda describen la composición por estado", async () => {
    render(<TableroCarteraPage />);
    const grafico = await screen.findByRole("img", { name: /Composición de la cartera/ });
    expect(grafico).toBeInTheDocument();
    // Los estados sin color propio se agrupan en "Otros", pero la leyenda los lista igual.
    expect(grafico.getAttribute("aria-label")).toContain("Otros");
    expect(screen.getByText("CERRADO")).toBeInTheDocument();
  });

  it("clickear un estado de la leyenda abre el detalle de esos contratos", async () => {
    const u = userEvent.setup();
    render(<TableroCarteraPage />);
    await u.click(await screen.findByText("ACTIVO"));

    expect(await screen.findByText(/Detalle · ACTIVO/)).toBeInTheDocument();
    expect(screen.getByText("CTO-1")).toBeInTheDocument();
    expect(screen.queryByText("CTO-2")).toBeNull();
  });

  it("el KPI de mora abre los contratos atrasados", async () => {
    const u = userEvent.setup();
    render(<TableroCarteraPage />);
    // El KPI "Mora" es un botón; "Mora" también titula una columna de la tabla por línea.
    await u.click(await screen.findByRole("button", { name: /^Mora/ }));

    expect(await screen.findByText(/Detalle · En mora/)).toBeInTheDocument();
    expect(screen.getByText("CTO-2")).toBeInTheDocument();
    expect(screen.getByText("45 d")).toBeInTheDocument();
  });

  it("un tramo del aging filtra por ese bucket", async () => {
    const u = userEvent.setup();
    render(<TableroCarteraPage />);
    await u.click(await screen.findByText("31–60"));
    expect(await screen.findByText(/Detalle · Atraso 31–60/)).toBeInTheDocument();
    expect(screen.getByText("CTO-2")).toBeInTheDocument();
  });

  it("una línea de crédito filtra sus contratos y el detalle se cierra", async () => {
    const u = userEvent.setup();
    render(<TableroCarteraPage />);
    const tablaLineas = (await screen.findAllByRole("table"))[1];
    await u.click(within(tablaLineas).getByText("PERSONAL"));

    expect(await screen.findByText(/Detalle · PERSONAL/)).toBeInTheDocument();
    expect(screen.getByText("2 contrato(s)")).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: /Cerrar detalle/ }));
    expect(screen.queryByText(/Detalle ·/)).toBeNull();
  });

  it("exporta la cartera a Excel", async () => {
    const u = userEvent.setup();
    render(<TableroCarteraPage />);
    await u.click(await screen.findByRole("button", { name: /Exportar/ }));
    expect(creditos.ctoCarteraExcel).toHaveBeenCalled();
  });

  it("si el tablero falla lo informa", async () => {
    creditos.ctoTablero.mockRejectedValue(new Error("Error 503"));
    render(<TableroCarteraPage />);
    expect(await screen.findByText("Error 503")).toBeInTheDocument();
  });
});
