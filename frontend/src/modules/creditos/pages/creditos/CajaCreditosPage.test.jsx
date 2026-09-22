import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CajaCreditosPage from "./CajaCreditosPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ctoListar: vi.fn(), ctoObtener: vi.fn(), ctoActividadCaja: vi.fn() },
}));

const LISTA = {
  items: [
    { id: "c1", numero_contrato: "CTO-1", cliente_nombre: "PEREZ JUAN", estado: "ACTIVO", saldo_capital: 300000 },
    { id: "c2", numero_contrato: "CTO-2", cliente_nombre: "GOMEZ ANA", estado: "ACTIVO", saldo_capital: 150000 },
    { id: "c3", numero_contrato: "CTO-3", cliente_nombre: "CERRADO SA", estado: "CERRADO", saldo_capital: 0 },
  ],
};

const CONTRATO = {
  id: "c1", numero_contrato: "CTO-1", cliente_nombre: "PEREZ JUAN", saldo_capital: 300000,
  cuotas: [
    { numero_cuota: 1, fecha_vencimiento: "2026-02-10", total: 60000, pagado: 60000, estado: "PAGADA" },
    { numero_cuota: 2, fecha_vencimiento: "2026-03-10", total: 60000, pagado: 0, estado: "PENDIENTE" },
  ],
  actividades: [{ tipo: "PAYMENT", estado: "APLICADA", importe: 60000, fecha: "2026-03-15",
                  dato: { medio_pago: "EFECTIVO", interes_punitorio: 0 } }],
  asientos: [{ lineas: [{ cuenta: "1.1.01", nombre: "Caja", debe: 60000, haber: 0 },
                        { cuenta: "1.3.01", nombre: "Préstamos", debe: 0, haber: 60000 }] }],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ctoListar.mockResolvedValue(LISTA);
  creditos.ctoObtener.mockResolvedValue(CONTRATO);
  creditos.ctoActividadCaja.mockResolvedValue({ ok: true });
});

const abrirContrato = async (u) => u.click(await screen.findByText("CTO-1"));

describe("Caja de créditos", () => {
  it("lista sólo contratos activos y permite buscarlos", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    expect(await screen.findByText("CTO-1")).toBeInTheDocument();
    expect(screen.queryByText("CTO-3")).toBeNull();                 // cerrado

    await u.type(screen.getByLabelText("Buscar contrato o cliente"), "gomez");
    expect(screen.queryByText("CTO-1")).toBeNull();
    expect(screen.getByText("CTO-2")).toBeInTheDocument();
  });

  it("al abrir un contrato muestra saldo y próxima cuota", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);
    await waitFor(() => expect(creditos.ctoObtener).toHaveBeenCalledWith("c1"));
    expect(await screen.findByText("Próxima cuota")).toBeInTheDocument();
    expect(screen.getByText(/#2 ·/)).toBeInTheDocument();
  });

  it("cobra la cuota con el medio de pago elegido y muestra el recibo con su asiento", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);

    await u.selectOptions(await screen.findByLabelText("Medio de pago"), "TRANSFERENCIA");
    await u.click(screen.getByRole("button", { name: "Cobrar cuota" }));

    await waitFor(() => expect(creditos.ctoActividadCaja).toHaveBeenCalledWith(
      "c1", "PAYMENT", 0, "TRANSFERENCIA", undefined, undefined));
    expect(await screen.findByText(/Recibo — CTO-1/)).toBeInTheDocument();
    expect(screen.getByText("1.1.01 · Caja")).toBeInTheDocument();
  });

  it("el cobro parcial pide el importe antes de cobrar", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);

    await u.click(await screen.findByRole("button", { name: "Cobro parcial" }));
    const dialogo = await screen.findByRole("heading", { name: "Cobro parcial" });
    expect(dialogo).toBeInTheDocument();
    expect(creditos.ctoActividadCaja).not.toHaveBeenCalled();

    await u.type(screen.getByLabelText("Importe a cobrar"), "25000");
    await u.click(screen.getByRole("button", { name: "Cobrar" }));
    await waitFor(() => expect(creditos.ctoActividadCaja).toHaveBeenCalledWith(
      "c1", "PAYMENT", 25000, "EFECTIVO", undefined, undefined));
  });

  it("adelantar cuotas manda la cantidad, no el importe", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);

    await u.click(await screen.findByRole("button", { name: "Adelantar cuotas" }));
    await u.type(screen.getByLabelText(/Cuántas cuotas/), "3");
    await u.click(screen.getByRole("button", { name: "Adelantar" }));
    await waitFor(() => expect(creditos.ctoActividadCaja).toHaveBeenCalledWith(
      "c1", "PAYMENT", 0, "EFECTIVO", undefined, 3));
  });

  it("el prepago pregunta si baja cuota o plazo", async () => {
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);

    await u.click(await screen.findByRole("button", { name: "Prepago capital" }));
    await u.type(screen.getByLabelText("Importe del prepago"), "100000");
    await u.selectOptions(screen.getByLabelText(/Cómo aplicar el prepago/), "BAJA_PLAZO");
    await u.click(screen.getByRole("button", { name: "Aplicar prepago" }));

    await waitFor(() => expect(creditos.ctoActividadCaja).toHaveBeenCalledWith(
      "c1", "PARTIAL_PREPAYMENT", 100000, "EFECTIVO", "BAJA_PLAZO", undefined));
  });

  it("si el cobro falla lo informa", async () => {
    creditos.ctoActividadCaja.mockRejectedValue(new Error("La cuota ya está pagada"));
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);
    await u.click(await screen.findByRole("button", { name: "Cobrar cuota" }));
    expect(await screen.findByText("La cuota ya está pagada")).toBeInTheDocument();
  });

  it("en sólo lectura no se puede cobrar", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<CajaCreditosPage />);
    await abrirContrato(u);
    expect(await screen.findByText("Sólo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cobrar cuota" })).toBeNull();
  });
});
