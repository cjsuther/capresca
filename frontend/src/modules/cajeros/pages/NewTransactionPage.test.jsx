import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/cajeros", () => ({
  createTransaction: vi.fn(),
}));

import { createTransaction } from "../../../api/cajeros";
import NewTransactionPage from "./NewTransactionPage";

function montar() {
  return render(
    <MemoryRouter initialEntries={["/modules/cajeros/transactions/new"]}>
      <Routes>
        <Route path="/modules/cajeros/transactions/new" element={<NewTransactionPage />} />
        <Route path="/modules/cajeros/transactions" element={<p>listado de transacciones</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const monto = () => screen.getByPlaceholderText("0.00");
const enviar = () => screen.getByRole("button", { name: "Registrar Transacción" });

describe("NewTransactionPage", () => {
  beforeEach(() => {
    createTransaction.mockReset();
  });

  it("el botón de envío arranca deshabilitado hasta que haya monto", async () => {
    const user = userEvent.setup();
    montar();
    expect(enviar()).toBeDisabled();
    await user.type(monto(), "100");
    expect(enviar()).toBeEnabled();
  });

  it("envía el formulario con el monto parseado y los opcionales en null", async () => {
    createTransaction.mockResolvedValue({ id: 7, status: "PROCESADA" });
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "1500.50");
    await user.click(enviar());

    expect(createTransaction).toHaveBeenCalledWith({
      currency: "ARS",
      amount: 1500.5,
      reference: null,
      description: null,
    });
  });

  it("manda moneda, referencia y descripción cuando se completan", async () => {
    createTransaction.mockResolvedValue({ id: 8, status: "PROCESADA" });
    const user = userEvent.setup();
    montar();

    await user.selectOptions(screen.getByRole("combobox"), "USD");
    await user.type(monto(), "200");
    await user.type(screen.getByPlaceholderText("Referencia de la operación"), "REF-9");
    await user.type(screen.getByPlaceholderText("Descripción libre"), "pago proveedor");
    await user.click(enviar());

    expect(createTransaction).toHaveBeenCalledWith({
      currency: "USD",
      amount: 200,
      reference: "REF-9",
      description: "pago proveedor",
    });
  });

  it("muestra el comprobante de transacción procesada", async () => {
    createTransaction.mockResolvedValue({ id: 7, status: "PROCESADA" });
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "100");
    await user.click(enviar());

    expect(await screen.findByText("Transacción procesada correctamente")).toBeInTheDocument();
    expect(screen.getByText("La transacción #7 fue procesada exitosamente.")).toBeInTheDocument();
    // el formulario ya no está
    expect(screen.queryByPlaceholderText("0.00")).not.toBeInTheDocument();
  });

  it("avisa cuando la transacción queda pendiente de autorización", async () => {
    createTransaction.mockResolvedValue({ id: 22, status: "PENDIENTE_AUTORIZACION" });
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "999999");
    await user.click(enviar());

    expect(await screen.findByText("Transacción pendiente de autorización")).toBeInTheDocument();
    expect(
      screen.getByText("La transacción #22 queda pendiente. Se envió una notificación al autorizador.")
    ).toBeInTheDocument();
  });

  it("desde el comprobante se puede ir al listado de transacciones", async () => {
    createTransaction.mockResolvedValue({ id: 7, status: "PROCESADA" });
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "100");
    await user.click(enviar());
    await user.click(await screen.findByRole("button", { name: "Ver transacciones" }));

    expect(screen.getByText("listado de transacciones")).toBeInTheDocument();
  });

  it("muestra el detalle de error que devuelve la API", async () => {
    createTransaction.mockRejectedValue({ response: { data: { detail: "Supera el límite diario" } } });
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "100");
    await user.click(enviar());

    expect(await screen.findByText("Supera el límite diario")).toBeInTheDocument();
    // el formulario sigue disponible para reintentar
    expect(enviar()).toBeEnabled();
  });

  it("usa un mensaje genérico si el error no trae detalle", async () => {
    createTransaction.mockRejectedValue(new Error("network"));
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "100");
    await user.click(enviar());

    expect(await screen.findByText("Error al registrar transacción")).toBeInTheDocument();
  });

  it("deshabilita el botón mientras se está registrando", async () => {
    let resolver;
    createTransaction.mockReturnValue(new Promise((res) => { resolver = res; }));
    const user = userEvent.setup();
    montar();

    await user.type(monto(), "100");
    await user.click(enviar());

    expect(await screen.findByRole("button", { name: "Registrando..." })).toBeDisabled();
    resolver({ id: 1, status: "PROCESADA" });
    expect(await screen.findByText("Transacción procesada correctamente")).toBeInTheDocument();
  });

  it("Cancelar vuelve al listado sin llamar a la API", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(screen.getByText("listado de transacciones")).toBeInTheDocument();
    expect(createTransaction).not.toHaveBeenCalled();
  });
});
