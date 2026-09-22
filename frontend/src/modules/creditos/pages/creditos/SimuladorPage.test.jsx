import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SimuladorPage from "./SimuladorPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({ creditos: { lineas: vi.fn(), simular: vi.fn() } }));

const LINEAS = [
  { id: 12, nombre: "PERSONAL", tipo_calculo: 1, tna: "60", por_afecta: "30", plazo_max: 36, monto_max: "1000000" },
  { id: 15, nombre: "CUOTA FIJA", tipo_calculo: 5, tna: "0", por_afecta: "30", plazo_max: 60, monto_max: "500000" },
];
const RESULTADO = {
  cantidad_cuotas: 2, total_a_pagar: 620000, cuota_promedio: 310000,
  margen_disponible: 120000, puede_tomar_credito: true, advertencias: [],
  cuotas: [
    { numero: 1, vencimiento: "2026-04-10", saldo_capital: 500000, amortizacion: 250000, interes: 50000, iva_interes: 10500, seguro: 500, gastos_adm: 0, total: 311000 },
    { numero: 2, vencimiento: "2026-05-10", saldo_capital: 250000, amortizacion: 250000, interes: 25000, iva_interes: 5250, seguro: 250, gastos_adm: 0, total: 280500 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  creditos.lineas.mockResolvedValue(LINEAS);
  creditos.simular.mockResolvedValue(RESULTADO);
});
afterEach(() => vi.useRealTimers());

describe("Simulador de crédito", () => {
  it("arranca con la primera línea y calcula el plan", async () => {
    const u = userEvent.setup();
    render(<SimuladorPage />);
    await waitFor(() => expect(screen.getByLabelText("Línea de crédito")).toHaveValue("12"));

    await u.click(screen.getByRole("button", { name: "Calcular plan de cuotas" }));
    await waitFor(() => expect(creditos.simular).toHaveBeenCalledWith({
      linea_id: 12, capital: "500000", plazo: 12,
      fecha_primer_vencimiento: "2026-03-15", sueldo: "650000", total_afectado: "0",
    }));
    expect(await screen.findByText("Cuota promedio")).toBeInTheDocument();
    const tabla = screen.getByRole("table");
    expect(within(tabla).getAllByRole("row")).toHaveLength(3);        // encabezado + 2 cuotas
  });

  it("con línea de cuota fija bloquea el plazo y manda la cuota", async () => {
    const u = userEvent.setup();
    render(<SimuladorPage />);
    await waitFor(() => expect(screen.getByLabelText("Línea de crédito")).toHaveValue("12"));

    await u.selectOptions(screen.getByLabelText("Línea de crédito"), "15");
    expect(screen.getByLabelText(/Plazo \(lo calcula el motor\)/)).toBeDisabled();

    await u.type(screen.getByLabelText("Cuota fija"), "45000");
    await u.click(screen.getByRole("button", { name: "Calcular plan de cuotas" }));
    await waitFor(() => expect(creditos.simular).toHaveBeenCalledWith(
      expect.objectContaining({ linea_id: 15, cuota_fija: "45000" })));
  });

  it("avisa cuando el margen no alcanza", async () => {
    creditos.simular.mockResolvedValue({ ...RESULTADO, puede_tomar_credito: false, margen_disponible: -5000 });
    const u = userEvent.setup();
    render(<SimuladorPage />);
    await waitFor(() => expect(screen.getByLabelText("Línea de crédito")).toHaveValue("12"));
    await u.click(screen.getByRole("button", { name: "Calcular plan de cuotas" }));
    expect(await screen.findByText(/NO puede tomar el crédito/)).toBeInTheDocument();
  });

  it("muestra las advertencias del motor", async () => {
    creditos.simular.mockResolvedValue({ ...RESULTADO, advertencias: ["El plazo supera el máximo de la línea"] });
    const u = userEvent.setup();
    render(<SimuladorPage />);
    await waitFor(() => expect(screen.getByLabelText("Línea de crédito")).toHaveValue("12"));
    await u.click(screen.getByRole("button", { name: "Calcular plan de cuotas" }));
    expect(await screen.findByText("El plazo supera el máximo de la línea")).toBeInTheDocument();
  });

  it("si el motor rechaza los datos lo muestra", async () => {
    creditos.simular.mockRejectedValue(new Error("capital: debe ser > 0"));
    const u = userEvent.setup();
    render(<SimuladorPage />);
    await waitFor(() => expect(screen.getByLabelText("Línea de crédito")).toHaveValue("12"));
    await u.click(screen.getByRole("button", { name: "Calcular plan de cuotas" }));
    expect(await screen.findByText("capital: debe ser > 0")).toBeInTheDocument();
  });
});
