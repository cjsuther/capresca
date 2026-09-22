import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CuentaCorrientePage from "./CuentaCorrientePage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({ creditos: { cuentaCorriente: vi.fn() } }));

const DATOS = {
  cantidad: 2, saldo_final: 120000,
  movimientos: [
    { fecha: "2026-01-10", cuota: 1, tipo: "O", no_recibo: null, debitos: 500000, creditos: 0,
      capital: 500000, interes: 0, iva: 0, punitorio: 0, saldo: 500000 },
    { fecha: "2026-02-10", cuota: 1, tipo: "P", no_recibo: 5501, debitos: 0, creditos: 380000,
      capital: 300000, interes: 60000, iva: 12600, punitorio: 0, saldo: 120000 },
  ],
};

const montar = (ruta = "/modules/creditos/cuenta-corriente") =>
  render(<MemoryRouter initialEntries={[ruta]}><CuentaCorrientePage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  creditos.cuentaCorriente.mockResolvedValue(DATOS);
});

describe("Cuenta corriente del crédito", () => {
  it("busca los movimientos del crédito pedido", async () => {
    const u = userEvent.setup();
    montar();
    expect(creditos.cuentaCorriente).not.toHaveBeenCalled();

    await u.type(screen.getByLabelText("N° de crédito"), "900");
    await u.click(screen.getByRole("button", { name: "Ver cuenta corriente" }));

    await waitFor(() => expect(creditos.cuentaCorriente).toHaveBeenCalledWith(900));
    expect(await screen.findByText("Otorgamiento")).toBeInTheDocument();
    expect(screen.getByText("Pago")).toBeInTheDocument();
    expect(screen.getByText(/2 movimientos/)).toBeInTheDocument();
  });

  it("si la URL trae el crédito consulta sola al entrar", async () => {
    montar("/modules/creditos/cuenta-corriente?credito=900");
    await waitFor(() => expect(creditos.cuentaCorriente).toHaveBeenCalledWith(900));
    expect(await screen.findByText("Otorgamiento")).toBeInTheDocument();
  });

  it("sin número de crédito pide uno", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(screen.getByRole("button", { name: "Ver cuenta corriente" }));
    expect(await screen.findByText("Ingresá un número de crédito.")).toBeInTheDocument();
    expect(creditos.cuentaCorriente).not.toHaveBeenCalled();
  });

  it("un crédito inexistente muestra el error del backend", async () => {
    creditos.cuentaCorriente.mockRejectedValue(new Error("Crédito no encontrado"));
    const u = userEvent.setup();
    montar();
    await u.type(screen.getByLabelText("N° de crédito"), "12345");
    await u.click(screen.getByRole("button", { name: "Ver cuenta corriente" }));
    expect(await screen.findByText("Crédito no encontrado")).toBeInTheDocument();
  });
});
