import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PorCarteraPage from "./PorCarteraPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { situacionPorCartera: vi.fn(), verPorCarteraPdf: vi.fn() },
}));

const DATOS = {
  anomalias_saldo_negativo: 0,
  por_cartera: [
    { cartera: 1, nombre: "ACTIVOS", activos: 1000, cancelados: 200, capital: 600000000, saldo: 250000000 },
    { cartera: 2, nombre: "JUBILADOS", activos: 300, cancelados: 50, capital: 90000000, saldo: 30000000 },
  ],
  total: { activos: 1300, cancelados: 250, capital: 690000000, saldo: 280000000 },
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.situacionPorCartera.mockResolvedValue(DATOS);
});

describe("Créditos por cartera", () => {
  it("muestra cada cartera y la fila de totales", async () => {
    render(<PorCarteraPage />);
    expect(await screen.findByText(/ACTIVOS/)).toBeInTheDocument();
    expect(screen.getByText(/JUBILADOS/)).toBeInTheDocument();
    expect(screen.getByText("1.000")).toBeInTheDocument();
    expect(screen.getByText("Total").closest("tr").textContent).toContain("1.300");
  });

  it("avisa de los saldos negativos del backup", async () => {
    creditos.situacionPorCartera.mockResolvedValue({ ...DATOS, anomalias_saldo_negativo: 3 });
    render(<PorCarteraPage />);
    expect(await screen.findByText(/3 crédito\(s\) con saldo negativo/)).toBeInTheDocument();
  });

  it("sin créditos no muestra totales", async () => {
    creditos.situacionPorCartera.mockResolvedValue({ ...DATOS, por_cartera: [] });
    render(<PorCarteraPage />);
    expect(await screen.findByText("Sin créditos")).toBeInTheDocument();
    expect(screen.queryByText("Total")).toBeNull();
  });

  it("descarga el PDF", async () => {
    const u = userEvent.setup();
    render(<PorCarteraPage />);
    await screen.findByText(/ACTIVOS/);
    await u.click(screen.getByRole("button", { name: "Descargar PDF" }));
    expect(creditos.verPorCarteraPdf).toHaveBeenCalled();
  });
});
