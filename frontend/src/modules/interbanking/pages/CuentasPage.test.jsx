import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CuentasPage from "./CuentasPage";
import { getCuentas, getSaldos } from "../../../api/interbanking";

vi.mock("../../../api/interbanking", () => ({
  getCuentas: vi.fn(),
  getSaldos: vi.fn(),
}));

const CUENTA = {
  bank_id: "011",
  bank_name: "Banco Nación",
  account_number: "1234567890",
  account_label: "Operativa Capresca",
  account_type: "CC",
  currency: "ARS",
  cbu: "0".repeat(22),
};

const SALDO = {
  bank_number: "011",
  account_number: "1234567890",
  currency: "ARS",
  balances: {
    current_operating_balance: 1500000.5,
    countable_balance: 1400000,
    projected_balance_24hs: 1600000,
    projected_balance_48hs: 1700000,
  },
};

const plata = (n) =>
  `ARS ${Number(n).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const refrescar = () => screen.getByRole("button", { name: /Refrescar/ });
const actualizarSaldos = () => screen.getByRole("button", { name: /Actualizar saldos/ });

describe("CuentasPage", () => {
  beforeEach(() => {
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
    getSaldos.mockResolvedValue({ accounts: [SALDO] });
  });

  it("arranca vacía, sin pegarle a la API", () => {
    render(<CuentasPage />);
    expect(screen.getByText(/Presioná "Refrescar" para cargar las cuentas/)).toBeInTheDocument();
    expect(getCuentas).not.toHaveBeenCalled();
    expect(getSaldos).not.toHaveBeenCalled();
  });

  it("el botón de saldos está deshabilitado mientras no haya cuentas", () => {
    render(<CuentasPage />);
    expect(actualizarSaldos()).toBeDisabled();
  });

  it("refrescar trae cuentas y a continuación los saldos", async () => {
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText("Banco Nación")).toBeInTheDocument();
    expect(screen.getByText("Operativa Capresca")).toBeInTheDocument();
    expect(screen.getByText("1234567890")).toBeInTheDocument();
    expect(screen.getByText("0".repeat(22))).toBeInTheDocument();
    expect(screen.getByText("CC")).toBeInTheDocument();
    await waitFor(() => expect(getSaldos).toHaveBeenCalledTimes(1));
  });

  it("cruza los saldos con la cuenta aunque el campo del banco se llame distinto", async () => {
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText(plata(1500000.5))).toBeInTheDocument();
    expect(screen.getByText(plata(1400000))).toBeInTheDocument();
    expect(screen.getByText(plata(1600000))).toBeInTheDocument();
    expect(screen.getByText(plata(1700000))).toBeInTheDocument();
    expect(screen.getByText(/Saldos OK/)).toBeInTheDocument();
    expect(screen.getByText(/Cuentas OK/)).toBeInTheDocument();
  });

  it("si el saldo no cruza con la cuenta deja la fila en guiones", async () => {
    getSaldos.mockResolvedValue({ accounts: [{ ...SALDO, account_number: "999" }] });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    const fila = (await screen.findByText("Banco Nación")).closest("tr");
    await waitFor(() => expect(getSaldos).toHaveBeenCalled());
    expect(within(fila).getAllByText("—")).toHaveLength(4);
  });

  it("acepta la respuesta con clave 'cuentas' y cae al bank_id si no hay nombre de banco", async () => {
    getCuentas.mockResolvedValue({ cuentas: [{ ...CUENTA, bank_name: null, account_label: null }] });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    const fila = (await screen.findByText("1234567890")).closest("tr");
    expect(within(fila).getAllByText("011")).toHaveLength(2);   // nombre + código BCRA
  });

  it("acepta la respuesta como array plano", async () => {
    getCuentas.mockResolvedValue([CUENTA]);
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());
    expect(await screen.findByText("Banco Nación")).toBeInTheDocument();
  });

  it("usa la moneda del saldo cuando la cuenta no la trae", async () => {
    getCuentas.mockResolvedValue({ accounts: [{ ...CUENTA, currency: null }] });
    getSaldos.mockResolvedValue({ accounts: [{ ...SALDO, currency: "USD" }] });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText("USD")).toBeInTheDocument();
  });

  it("no pide saldos si no vino ninguna cuenta", async () => {
    getCuentas.mockResolvedValue({ accounts: [] });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    await waitFor(() => expect(screen.getByText(/Cuentas OK/)).toBeInTheDocument());
    expect(getSaldos).not.toHaveBeenCalled();
    expect(screen.getByText(/Presioná "Refrescar"/)).toBeInTheDocument();
  });

  it("muestra el detalle del backend cuando falla la consulta de cuentas", async () => {
    getCuentas.mockRejectedValue({ response: { data: { detail: "Token vencido" } } });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText("Token vencido")).toBeInTheDocument();
    expect(screen.getByText(/Cuentas Error/)).toBeInTheDocument();
    expect(getSaldos).not.toHaveBeenCalled();
  });

  it("mensaje genérico si el error de cuentas no trae detalle", async () => {
    getCuentas.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());
    expect(await screen.findByText("Error al consultar cuentas")).toBeInTheDocument();
  });

  it("muestra el error de saldos sin perder el listado de cuentas", async () => {
    getSaldos.mockRejectedValue({ response: { data: { detail: "Scope sin permiso" } } });
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText("Scope sin permiso")).toBeInTheDocument();
    expect(screen.getByText(/Saldos Error/)).toBeInTheDocument();
    expect(screen.getByText("Banco Nación")).toBeInTheDocument();
  });

  it("mensaje genérico si el error de saldos no trae detalle", async () => {
    getSaldos.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());
    expect(await screen.findByText("Error al consultar saldos")).toBeInTheDocument();
  });

  it("el botón de saldos vuelve a consultar sólo los saldos", async () => {
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());
    await waitFor(() => expect(getSaldos).toHaveBeenCalledTimes(1));

    await user.click(actualizarSaldos());
    await waitFor(() => expect(getSaldos).toHaveBeenCalledTimes(2));
    expect(getCuentas).toHaveBeenCalledTimes(1);
  });

  it("saldos sin la clave accounts no rompe la pantalla", async () => {
    getSaldos.mockResolvedValue({});
    const user = userEvent.setup();
    render(<CuentasPage />);
    await user.click(refrescar());

    expect(await screen.findByText(/Saldos OK/)).toBeInTheDocument();
    const fila = screen.getByText("Banco Nación").closest("tr");
    expect(within(fila).getAllByText("—")).toHaveLength(4);
  });
});
