import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SituacionClientePage from "./SituacionClientePage";
import { creditos } from "../../../../api/creditos";
import { searchClients } from "../../../../api/clientes";

vi.mock("../../../../api/creditos", () => ({ creditos: { situacionCliente: vi.fn() } }));
vi.mock("../../../../api/clientes", () => ({ searchClients: vi.fn() }));

const CLIENTE = { id: 7, code: "PH-7", human_profile: { first_name: "Ana", last_name: "Perez", document_number: "30123456" } };
const SITUACION = {
  apellido_nombre: "PEREZ, ANA", cuil: "27301234564", sueldo: 900000,
  creditos_activos: 2, saldo_total: 450000, margen_disponible: 120000,
  creditos: [
    { id: 900, linea: "PERSONAL", capital: 500000, saldo_capital: 300000, cuotas_pendientes: 8, proxima_cuota_vto: "2026-04-10", estado: "A" },
    { id: 850, linea: "ESPECIAL", capital: 200000, saldo_capital: 0, cuotas_pendientes: 0, proxima_cuota_vto: null, estado: "C" },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  searchClients.mockResolvedValue({ data: [CLIENTE] });
  creditos.situacionCliente.mockResolvedValue(SITUACION);
});

async function elegirCliente(u) {
  await u.type(screen.getByPlaceholderText(/Buscar cliente/), "perez");
  await u.click(await screen.findByText(/Perez, Ana/));
}

describe("Situación del cliente", () => {
  it("el cliente se elige en el padrón y la situación se pide por ese id", async () => {
    const u = userEvent.setup();
    render(<SituacionClientePage />);
    expect(creditos.situacionCliente).not.toHaveBeenCalled();

    await elegirCliente(u);
    await waitFor(() => expect(creditos.situacionCliente).toHaveBeenCalledWith(7));
    expect(await screen.findByText("PEREZ, ANA")).toBeInTheDocument();
    expect(screen.getByText("Créditos activos")).toBeInTheDocument();
    expect(screen.getByText("Margen disponible")).toBeInTheDocument();
    expect(screen.getByText("PERSONAL")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("Cancelado")).toBeInTheDocument();
  });

  it("sin margen calculado no muestra ese indicador", async () => {
    creditos.situacionCliente.mockResolvedValue({ ...SITUACION, margen_disponible: null });
    const u = userEvent.setup();
    render(<SituacionClientePage />);
    await elegirCliente(u);
    expect(await screen.findByText("Saldo total")).toBeInTheDocument();
    expect(screen.queryByText("Margen disponible")).toBeNull();
  });

  it("un cliente sin créditos lo dice", async () => {
    creditos.situacionCliente.mockResolvedValue({ ...SITUACION, creditos: [], creditos_activos: 0 });
    const u = userEvent.setup();
    render(<SituacionClientePage />);
    await elegirCliente(u);
    expect(await screen.findByText("El cliente no tiene créditos")).toBeInTheDocument();
  });

  it("si la consulta falla lo informa", async () => {
    creditos.situacionCliente.mockRejectedValue(new Error("Error 500"));
    const u = userEvent.setup();
    render(<SituacionClientePage />);
    await elegirCliente(u);
    expect(await screen.findByText("Error 500")).toBeInTheDocument();
  });
});
