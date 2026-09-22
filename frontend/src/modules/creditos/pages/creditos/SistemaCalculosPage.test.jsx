import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SistemaCalculosPage from "./SistemaCalculosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { sistemaCalculos: vi.fn(), sistemaCalculosDebug: vi.fn() },
}));

const CATALOGO = {
  sistemas: [
    { codigo: "FRANCES", nombre: "Sistema francés", resumen: "Cuota constante.", formula: "C = V·i/(1-(1+i)^-n)",
      variables: [["i", "tasa periódica"], ["n", "cantidad de cuotas"]], pasos: ["interés = saldo · i"], nota: "El IVA del interés entra en la cuota." },
    { codigo: "ALEMAN", nombre: "Sistema alemán", resumen: "Amortización constante.", formula: "A = V/n",
      variables: [["V", "capital"]], pasos: ["capital = V/n"], nota: "" },
  ],
  reglasComunes: [{ titulo: "Redondeo", detalle: "Se redondea cada cuota al final." }],
  certificacion: { motor: "cronograma()", certificado: true, checksum: "abc123def456",
                   checksumCorto: "abc123", precisionDecimal: 4, reglaRedondeo: "HALF_UP",
                   lineasCodigo: 420, fuenteUnica: "productos_calc.py", calculadores: [] },
  gobernanza: [],
};

const DEBUG = {
  resumen: { tna: 52, tea: 66.2, cft: 71.1, primeraCuota: 19500 },
  derivados: [{ nombre: "tasa periódica", valor: "0,0433" }],
  pasos: [
    { cuota: 1, saldoInicial: "100.000", interes: "4.330", capital: "15.170", cuota_total: "19.500", saldoFinal: "84.830", enGracia: false, detalle: ["interés = 100.000 · 0,0433"] },
    { cuota: 2, saldoInicial: "84.830", interes: "3.673", capital: "15.827", cuota_total: "19.500", saldoFinal: "69.003", enGracia: false, detalle: ["interés = 84.830 · 0,0433"] },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.sistemaCalculos.mockResolvedValue(CATALOGO);
  creditos.sistemaCalculosDebug.mockResolvedValue(DEBUG);
});

describe("Sistema de cálculos", () => {
  it("muestra la certificación del motor y la fórmula del sistema elegido", async () => {
    render(<SistemaCalculosPage />);
    expect(await screen.findByText("motor certificado")).toBeInTheDocument();
    expect(screen.getByText(/checksum/)).toHaveTextContent("abc123");
    expect(screen.getByText("Sistema francés")).toBeInTheDocument();
    expect(screen.getByText("C = V·i/(1-(1+i)^-n)")).toBeInTheDocument();
  });

  it("depura con los parámetros por defecto al entrar", async () => {
    render(<SistemaCalculosPage />);
    await waitFor(() => expect(creditos.sistemaCalculosDebug).toHaveBeenCalledWith({
      sistema: "FRANCES", monto: 100000, plazo: 6, tna: 52,
      frecuencia: "MENSUAL", gracia: 0, tipoCuota: "VENCIDA", cargoPct: 0,
    }));
    expect(await screen.findByText("TEA")).toBeInTheDocument();
    // "tasa periódica" también es una variable de la fórmula: se mira en los derivados.
    expect(screen.getByText("Parámetros derivados").closest("div").textContent).toContain("0,0433");
  });

  it("cambiar de sistema recalcula con ese sistema", async () => {
    const u = userEvent.setup();
    render(<SistemaCalculosPage />);
    await screen.findByText("Sistema francés");

    await u.click(screen.getByRole("button", { name: "Alemán" }));
    await waitFor(() => expect(creditos.sistemaCalculosDebug).toHaveBeenLastCalledWith(
      expect.objectContaining({ sistema: "ALEMAN" })));
    expect(screen.getByText("Sistema alemán")).toBeInTheDocument();
  });

  it("cambiar un parámetro del depurador recalcula", async () => {
    const u = userEvent.setup();
    render(<SistemaCalculosPage />);
    await screen.findByText("Sistema francés");

    const plazo = screen.getByLabelText("Plazo (cuotas)");
    await u.clear(plazo);
    await u.type(plazo, "12");
    await waitFor(() => expect(creditos.sistemaCalculosDebug).toHaveBeenLastCalledWith(
      expect.objectContaining({ plazo: 12 })));
  });

  it("la primera cuota viene expandida y se puede plegar", async () => {
    const u = userEvent.setup();
    render(<SistemaCalculosPage />);
    expect(await screen.findByText("interés = 100.000 · 0,0433")).toBeInTheDocument();

    await u.click(screen.getByRole("cell", { name: "1" }));
    expect(screen.queryByText("interés = 100.000 · 0,0433")).toBeNull();

    await u.click(screen.getByRole("cell", { name: "2" }));
    expect(screen.getByText("interés = 84.830 · 0,0433")).toBeInTheDocument();
  });

  it("muestra las reglas comunes", async () => {
    render(<SistemaCalculosPage />);
    expect(await screen.findByText("Redondeo")).toBeInTheDocument();
    expect(screen.getByText("Se redondea cada cuota al final.")).toBeInTheDocument();
  });

  it("si el depurador falla lo informa", async () => {
    creditos.sistemaCalculosDebug.mockRejectedValue(new Error("plazo: debe ser > 0"));
    render(<SistemaCalculosPage />);
    expect(await screen.findByText("plazo: debe ser > 0")).toBeInTheDocument();
  });
});
