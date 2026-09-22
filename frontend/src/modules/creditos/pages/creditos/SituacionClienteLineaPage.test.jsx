import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SituacionClienteLineaPage from "./SituacionClienteLineaPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: {
    ctoSituacion: vi.fn(), ctoObtener: vi.fn(), ctoActividad: vi.fn(), ctoDevengar: vi.fn(),
    ctoDesembolsar: vi.fn(), ctoReversar: vi.fn(), ctoRefinanciar: vi.fn(), ctoPdf: vi.fn(),
    ctoCarteraExcel: vi.fn(), ppPreview: vi.fn(),
  },
}));

const SITUACION = {
  resumen: { contratos: 2, activos: 1, enMora: 1, capitalColocado: 900000, saldoVigente: 400000 },
  items: [
    { id: "c1", cliente: "PEREZ JUAN", numero: "CTO-1", sistema: "FRANCES", monto: 500000, saldo: 300000,
      cuotasPagadas: 4, cuotasPendientes: 8, enMora: false, moraAlDia: 0, estado: "ACTIVO",
      proximaCuota: { numero: 5, vencimiento: "2026-04-10", total: 60000 } },
    { id: "c2", cliente: "PEREZ JUAN", numero: "CTO-2", sistema: "ALEMAN", monto: 400000, saldo: 100000,
      cuotasPagadas: 9, cuotasPendientes: 3, enMora: true, moraAlDia: 15000, estado: "ACTIVO", proximaCuota: null },
  ],
};

const CONTRATO = {
  id: "c1", numero_contrato: "CTO-1", cliente_nombre: "PEREZ JUAN", estado: "ACTIVO",
  saldo_capital: 300000, sistema: "FRANCES", tasa: 60, plazo: 12, fecha_valor: "2026-01-01",
  snapshot: { producto: "PERSONAL", version: 2, tna: 60 },
  cuotas: [
    { numero_cuota: 4, fecha_vencimiento: "2026-03-10", capital: 40000, interes: 20000, total: 60000, saldo_final: 300000, estado: "PAGADA" },
    { numero_cuota: 5, fecha_vencimiento: "2026-04-10", capital: 42000, interes: 18000, total: 60000, saldo_final: 258000, estado: "PENDIENTE" },
  ],
  actividades: [
    { id: "a1", tipo: "DISBURSEMENT", importe: 500000, fecha: "2026-01-02", detalle: "desembolso", por: "ana", estado: "APLICADA" },
    { id: "a2", tipo: "PAYMENT", importe: 60000, fecha: "2026-03-10", detalle: "cuota 4", por: "ana", estado: "APLICADA" },
  ],
  asientos: [{ id: 11, fecha: "2026-03-10", concepto: "Cobro cuota", origen: "pp",
               lineas: [{ cuenta: "1.1.01", nombre: "Caja", debe: 60000, haber: 0 }] }],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ctoSituacion.mockResolvedValue(SITUACION);
  creditos.ctoObtener.mockResolvedValue(CONTRATO);
  creditos.ctoActividad.mockResolvedValue({ ...CONTRATO, saldo_capital: 250000 });
  creditos.ctoReversar.mockResolvedValue(CONTRATO);
  creditos.ctoDevengar.mockResolvedValue(CONTRATO);
});

const abrirContrato = async (u) => u.click(await screen.findByText("CTO-1"));

describe("Situación del cliente (línea nueva)", () => {
  it("agrupa los contratos por cliente con su resumen", async () => {
    render(<SituacionClienteLineaPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(screen.getByText("· 2 préstamos")).toBeInTheDocument();
    expect(screen.getByText("1 en mora")).toBeInTheDocument();
    expect(screen.getByText("Capital colocado")).toBeInTheDocument();
  });

  it("buscar consulta por el nombre tipeado", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await screen.findByText("PEREZ JUAN");

    await u.type(screen.getByLabelText("Buscar por nombre de cliente"), "gomez");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => expect(creditos.ctoSituacion).toHaveBeenLastCalledWith("gomez"));
  });

  it("si llega con un cliente preseleccionado lo busca solo", async () => {
    sessionStorage.setItem("situacion_cliente_q", "PEREZ");
    render(<SituacionClienteLineaPage />);
    await waitFor(() => expect(creditos.ctoSituacion).toHaveBeenCalledWith("PEREZ"));
    expect(sessionStorage.getItem("situacion_cliente_q")).toBeNull();
  });

  it("desplegar un contrato trae su servicing (plan, actividades y asientos)", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    await waitFor(() => expect(creditos.ctoObtener).toHaveBeenCalledWith("c1"));
    expect(await screen.findByText("Actividades (servicing)")).toBeInTheDocument();
    expect(screen.getByText(/Asientos contables \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("1.1.01 · Caja")).toBeInTheDocument();
  });

  it("paga la próxima cuota con la fecha valor indicada", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    await u.type(await screen.findByLabelText(/Fecha valor/), "2026-03-20");
    await u.click(screen.getByRole("button", { name: "Pagar próxima cuota" }));
    await waitFor(() => expect(creditos.ctoActividad).toHaveBeenCalledWith(
      "c1", "PAYMENT", 0, "", "2026-03-20", undefined));
  });

  it("el prepago pide importe y modo", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    await u.click(await screen.findByRole("button", { name: "Prepago capital" }));
    await u.type(screen.getByLabelText("Importe del prepago"), "50000");
    await u.selectOptions(screen.getByLabelText(/Cómo aplicar el prepago/), "BAJA_PLAZO");
    await u.click(screen.getByRole("button", { name: "Aplicar prepago" }));

    await waitFor(() => expect(creditos.ctoActividad).toHaveBeenCalledWith(
      "c1", "PARTIAL_PREPAYMENT", 50000, "", undefined, "BAJA_PLAZO"));
  });

  it("la cancelación total se confirma antes de ejecutarse", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    await u.click(await screen.findByRole("button", { name: "Cancelación total" }));
    const dialogo = await screen.findByRole("dialog", { name: /Cancelación total/ });
    expect(creditos.ctoActividad).not.toHaveBeenCalled();

    await u.click(within(dialogo).getByRole("button", { name: "Cancelar contrato" }));
    await waitFor(() => expect(creditos.ctoActividad).toHaveBeenCalledWith(
      "c1", "PAYOFF", 0, "", undefined, undefined));
  });

  it("una actividad reversable se reversa tras confirmar; el desembolso no se puede reversar", async () => {
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    expect(await screen.findByRole("button", { name: "Reversar PAYMENT" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reversar DISBURSEMENT" })).toBeNull();

    await u.click(screen.getByRole("button", { name: "Reversar PAYMENT" }));
    await u.click(await screen.findByRole("button", { name: "Reversar", exact: true }));
    await waitFor(() => expect(creditos.ctoReversar).toHaveBeenCalledWith("c1", "a2"));
  });

  it("un contrato a liquidar ofrece desembolsar en vez de las acciones de servicing", async () => {
    creditos.ctoObtener.mockResolvedValue({ ...CONTRATO, estado: "A_LIQUIDAR", liquidacion: { neto: 480000 } });
    creditos.ctoDesembolsar.mockResolvedValue({ ...CONTRATO, estado: "ACTIVO" });
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    // Mientras está A_LIQUIDAR sólo se ofrece desembolsar; el servicing aparece una vez desembolsado.
    expect(await screen.findByRole("button", { name: /Desembolsar/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pagar próxima cuota" })).toBeNull();

    await u.click(screen.getByRole("button", { name: /Desembolsar/ }));
    await waitFor(() => expect(creditos.ctoDesembolsar).toHaveBeenCalledWith("c1"));
    expect(await screen.findByRole("button", { name: "Pagar próxima cuota" })).toBeInTheDocument();
  });

  it("en sólo lectura no se opera el contrato", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);

    expect(await screen.findByText("Sólo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pagar próxima cuota" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reversar PAYMENT" })).toBeNull();
  });

  it("si el servicing falla lo informa", async () => {
    creditos.ctoActividad.mockRejectedValue(new Error("El ejercicio está cerrado"));
    const u = userEvent.setup();
    render(<SituacionClienteLineaPage />);
    await abrirContrato(u);
    await u.click(await screen.findByRole("button", { name: "Pagar próxima cuota" }));
    expect(await screen.findByText("El ejercicio está cerrado")).toBeInTheDocument();
  });
});
