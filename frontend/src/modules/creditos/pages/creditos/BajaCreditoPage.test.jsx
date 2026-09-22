import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BajaCreditoPage from "./BajaCreditoPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { credito: vi.fn(), bajaCredito: vi.fn() },
}));

const CREDITO = { id: 900, estado: "A", capital: 500000, saldo_capital: 300000 };

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

async function buscarCredito(u, nro = "900") {
  await u.type(screen.getByLabelText("N° de crédito"), nro);
  await u.click(screen.getByRole("button", { name: "Buscar" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.credito.mockResolvedValue(CREDITO);
  creditos.bajaCredito.mockResolvedValue({ id: 900, estado: "B" });
});

describe("Baja de crédito", () => {
  it("busca el crédito y muestra capital y saldo", async () => {
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    await waitFor(() => expect(creditos.credito).toHaveBeenCalledWith(900));
    expect(await screen.findByText(/Crédito 900 — estado A/)).toBeInTheDocument();
  });

  it("sin número de crédito no consulta", async () => {
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByText("Ingresá un número de crédito.")).toBeInTheDocument();
    expect(creditos.credito).not.toHaveBeenCalled();
  });

  it("el motivo es obligatorio para poder dar de baja", async () => {
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    const boton = await screen.findByRole("button", { name: "Dar de baja el crédito" });
    expect(boton).toBeDisabled();
    await u.type(screen.getByLabelText("Motivo de baja"), "cargado por error");
    expect(boton).toBeEnabled();
  });

  it("la baja se confirma antes de ejecutarse", async () => {
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    await u.type(await screen.findByLabelText("Motivo de baja"), "cargado por error");
    await u.click(screen.getByRole("button", { name: "Dar de baja el crédito" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(creditos.bajaCredito).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(creditos.bajaCredito).not.toHaveBeenCalled();
  });

  it("confirmada, da de baja y avisa el nuevo estado", async () => {
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    await u.type(await screen.findByLabelText("Motivo de baja"), "cargado por error");
    await u.click(screen.getByRole("button", { name: "Dar de baja el crédito" }));
    await u.click(await screen.findByRole("button", { name: "Dar de baja" }));

    await waitFor(() => expect(creditos.bajaCredito).toHaveBeenCalledWith(900, "cargado por error"));
    expect(await screen.findByText(/dado de baja \(estado B\)/)).toBeInTheDocument();
  });

  it("si el backend rechaza la baja lo muestra", async () => {
    creditos.bajaCredito.mockRejectedValue(new Error("El crédito tiene cuotas pagadas"));
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    await u.type(await screen.findByLabelText("Motivo de baja"), "error");
    await u.click(screen.getByRole("button", { name: "Dar de baja el crédito" }));
    await u.click(await screen.findByRole("button", { name: "Dar de baja" }));
    expect(await screen.findByText("El crédito tiene cuotas pagadas")).toBeInTheDocument();
  });

  it("en sólo lectura no se ofrece la baja", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<BajaCreditoPage />);
    await buscarCredito(u);
    expect(await screen.findByText("Tu usuario sólo puede consultar créditos.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dar de baja el crédito" })).toBeNull();
  });
});
