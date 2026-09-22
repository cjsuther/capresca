import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EstadisticasCarteraPage from "./EstadisticasCarteraPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { estadisticas: vi.fn(), verCarteraPdf: vi.fn() },
}));

const STATS = {
  creditos_activos: 1500, capital_otorgado_total: 900000000, saldo_total: 400000000,
  por_linea: [
    { linea_id: 1, linea: "PERSONAL", cartera: "ACTIVA", cantidad: 1000, capital_otorgado: 600000000, saldo: 250000000 },
    { linea_id: 2, linea: "ESPECIAL", cartera: "ACTIVA", cantidad: 500, capital_otorgado: 300000000, saldo: 150000000 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.estadisticas.mockResolvedValue(STATS);
});

describe("Estadísticas de cartera", () => {
  it("muestra los indicadores y el detalle por línea", async () => {
    render(<EstadisticasCarteraPage />);
    expect(await screen.findByText("1.500")).toBeInTheDocument();
    expect(screen.getByText("Saldo en cartera")).toBeInTheDocument();
    expect(screen.getByText("PERSONAL")).toBeInTheDocument();
    expect(screen.getByText("ESPECIAL")).toBeInTheDocument();
  });

  it("el botón descarga el PDF de cartera", async () => {
    const u = userEvent.setup();
    render(<EstadisticasCarteraPage />);
    await screen.findByText("PERSONAL");
    await u.click(screen.getByRole("button", { name: "Cartera PDF" }));
    expect(creditos.verCarteraPdf).toHaveBeenCalled();
  });

  it("si falla la consulta lo informa", async () => {
    creditos.estadisticas.mockRejectedValue(new Error("Error 500"));
    render(<EstadisticasCarteraPage />);
    expect(await screen.findByText("Error 500")).toBeInTheDocument();
  });
});
