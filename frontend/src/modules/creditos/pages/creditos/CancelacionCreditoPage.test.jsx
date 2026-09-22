import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CancelacionCreditoPage from "./CancelacionCreditoPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { simularCancelacion: vi.fn(), cancelarCredito: vi.fn(), verReciboPdf: vi.fn() },
}));

const DETALLE = {
  total: 420000, capital: 300000, interes: 90000, iva: 18900, punitorio: 11100, iva_punit: 0,
  items: [
    { cuota: 5, vencida: true, capital: 100000, interes: 30000, iva: 6300, punitorio: 11100, subtotal: 147400 },
    { cuota: 6, vencida: false, capital: 200000, interes: 0, iva: 0, punitorio: 0, subtotal: 200000 },
  ],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

async function calcular(u, nro = "900") {
  await u.type(screen.getByLabelText("N° de crédito"), nro);
  await u.click(screen.getByRole("button", { name: "Calcular cancelación" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  sesion(["creditos:read", "creditos:write"]);
  creditos.simularCancelacion.mockResolvedValue(DETALLE);
  creditos.cancelarCredito.mockResolvedValue({ id: 77, numero: 5501, cliente_nombre: "PEREZ JUAN", total: 420000 });
});
afterEach(() => vi.useRealTimers());

describe("Cancelación anticipada de crédito", () => {
  it("calcula la cancelación a la fecha y detalla cuota por cuota", async () => {
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await calcular(u);

    await waitFor(() => expect(creditos.simularCancelacion).toHaveBeenCalledWith(900, "2026-03-15"));
    expect(await screen.findByText("Total a cancelar")).toBeInTheDocument();
    expect(screen.getByText("Vencida")).toBeInTheDocument();
    expect(screen.getByText("Futura (s/ int.)")).toBeInTheDocument();
  });

  it("sin número de crédito no calcula", async () => {
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await u.click(screen.getByRole("button", { name: "Calcular cancelación" }));
    expect(await screen.findByText("Ingresá un número de crédito.")).toBeInTheDocument();
    expect(creditos.simularCancelacion).not.toHaveBeenCalled();
  });

  it("la cancelación se confirma antes de mover dinero", async () => {
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await calcular(u);
    await u.click(await screen.findByRole("button", { name: /Confirmar cancelación/ }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(creditos.cancelarCredito).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(creditos.cancelarCredito).not.toHaveBeenCalled();
  });

  it("confirmada, emite el recibo y ofrece el PDF", async () => {
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await calcular(u);
    await u.click(await screen.findByRole("button", { name: /Confirmar cancelación/ }));
    await u.click(await screen.findByRole("button", { name: "Cancelar y emitir recibo" }));

    await waitFor(() => expect(creditos.cancelarCredito).toHaveBeenCalledWith(
      900, { fecha_pago: "2026-03-15", via_pago: "EFECTIVO" }));
    expect(await screen.findByText(/Recibo N° 5501/)).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Ver recibo PDF" }));
    expect(creditos.verReciboPdf).toHaveBeenCalledWith(77);
  });

  it("si la cancelación falla lo muestra y no emite recibo", async () => {
    creditos.cancelarCredito.mockRejectedValue(new Error("El crédito ya está cancelado"));
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await calcular(u);
    await u.click(await screen.findByRole("button", { name: /Confirmar cancelación/ }));
    await u.click(await screen.findByRole("button", { name: "Cancelar y emitir recibo" }));

    expect(await screen.findByText("El crédito ya está cancelado")).toBeInTheDocument();
    expect(screen.queryByText(/Recibo N°/)).toBeNull();
  });

  it("en sólo lectura se puede calcular pero no cancelar", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<CancelacionCreditoPage />);
    await calcular(u);
    expect(await screen.findByText("Total a cancelar")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirmar cancelación/ })).toBeNull();
  });
});
