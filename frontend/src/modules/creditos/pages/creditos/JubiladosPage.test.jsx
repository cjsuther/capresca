import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import JubiladosPage from "./JubiladosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { jubiladosResumen: vi.fn(), jubiladosPorDepto: vi.fn() },
}));

beforeEach(() => {
  vi.clearAllMocks();
  creditos.jubiladosResumen.mockResolvedValue({ total: 320, liquidadas: 290, monto_total: 45000000 });
  creditos.jubiladosPorDepto.mockResolvedValue([
    { departamento: "CAPITAL", cantidad: 200, monto_total: 30000000 },
    { departamento: "VALLE VIEJO", cantidad: 120, monto_total: 15000000 },
  ]);
});

describe("Jubilados / Ley 5094", () => {
  it("muestra el resumen y el detalle por departamento", async () => {
    render(<JubiladosPage />);
    expect(await screen.findByText("320")).toBeInTheDocument();
    expect(screen.getByText("Liquidadas")).toBeInTheDocument();
    expect(screen.getByText("CAPITAL")).toBeInTheDocument();
    expect(screen.getByText("VALLE VIEJO")).toBeInTheDocument();
  });

  it("si el resumen falla lo informa", async () => {
    creditos.jubiladosResumen.mockRejectedValue(new Error("Sin permisos sobre créditos"));
    render(<JubiladosPage />);
    expect(await screen.findByText("Sin permisos sobre créditos")).toBeInTheDocument();
  });
});
