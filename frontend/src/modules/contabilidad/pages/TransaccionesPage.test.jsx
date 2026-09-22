import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/contabilidad", async (orig) => ({
  ...(await orig()),
  sinDefinir: vi.fn(), listarTransacciones: vi.fn(), listarCuentas: vi.fn(), listarDiarios: vi.fn(),
  crearDefinicion: vi.fn(), probarDefinicion: vi.fn(), reprocesar: vi.fn(), verTransaccion: vi.fn(),
}));

import * as api from "../../../api/contabilidad";
import TransaccionesPage from "./TransaccionesPage";
import { useAuthStore } from "../../../context/authStore";

const PENDIENTE = {
  modulo: "creditos", tipo: "DESEMBOLSO", cantidad: 2, campos: ["capital", "contrato"],
  ejemplo: { id: 1, modulo: "creditos", tipo: "DESEMBOLSO", referencia: "CTO-1", fecha: "2026-09-22",
             datos: { capital: 100000, contrato: "CTO-1" }, estado: "PENDIENTE_CONFIGURACION",
             motivo: "Falta definir cómo se contabiliza «DESEMBOLSO» de creditos." },
};
const TRANSACCIONES = {
  items: [PENDIENTE.ejemplo], total: 1, pendientes: 2, errores: 0,
};

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "conta" },
  permissions: { modules: ["contabilidad"], actions: { contabilidad: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["asientos:read", "asientos:write", "definiciones:write"]);
  api.sinDefinir.mockResolvedValue({ items: [PENDIENTE], total: 1 });
  api.listarTransacciones.mockResolvedValue(TRANSACCIONES);
  api.listarCuentas.mockResolvedValue({ items: [
    { codigo: "1.1.04", nombre: "Préstamos otorgados" }, { codigo: "1.1.02", nombre: "Bancos" }] });
  api.listarDiarios.mockResolvedValue({ items: [{ codigo: "VAR", nombre: "Varios" }, { codigo: "BANCO", nombre: "Banco" }] });
  api.crearDefinicion.mockResolvedValue({ id: 5, reproceso: { contabilizadas: 2, pendientes: 0, errores: 0 } });
  api.probarDefinicion.mockResolvedValue({ debe: 100000, haber: 100000, lineas: [
    { cuenta: "1.1.04", nombre: "Préstamos otorgados", debe: 100000, haber: 0 },
    { cuenta: "1.1.02", nombre: "Bancos", debe: 0, haber: 100000 }] });
  api.reprocesar.mockResolvedValue({ contabilizadas: 2, pendientes: 0, errores: 0 });
});

describe("Transacciones de los módulos", () => {
  it("muestra lo que espera definición, con los campos que manda el módulo", async () => {
    render(<TransaccionesPage />);
    expect(await screen.findAllByText("DESEMBOLSO")).toHaveLength(2);   // el pendiente y su transacción
    expect(screen.getByText(/creditos · 2 transacción\(es\) · campos: capital, contrato/)).toBeInTheDocument();
    expect(screen.getByText("Falta definir cómo se contabiliza")).toBeInTheDocument();
  });

  it("define el asiento y contabiliza lo que estaba esperando", async () => {
    const u = userEvent.setup();
    render(<TransaccionesPage />);
    await u.click(await screen.findByRole("button", { name: "Definir asiento" }));

    const modal = screen.getByRole("dialog", { name: /Cómo se contabiliza/ });
    expect(within(modal).getByText("capital = 100000")).toBeInTheDocument();
    await u.selectOptions(within(modal).getByLabelText("Cuenta 1"), "1.1.04");
    await u.type(within(modal).getByLabelText("Importe 1"), "capital");
    await u.selectOptions(within(modal).getByLabelText("Cuenta 2"), "1.1.02");
    await u.type(within(modal).getByLabelText("Importe 2"), "capital");
    await u.click(within(modal).getByRole("button", { name: /Guardar y contabilizar/ }));

    await waitFor(() => expect(api.crearDefinicion).toHaveBeenCalled());
    const enviado = api.crearDefinicion.mock.calls[0][0];
    expect(enviado.modulo).toBe("creditos");
    expect(enviado.lineas).toEqual([
      { dc: "DEBE", cuenta: "1.1.04", importe: "capital", detalle: "" },
      { dc: "HABER", cuenta: "1.1.02", importe: "capital", detalle: "" },
    ]);
    expect(await screen.findByText(/se contabilizaron las transacciones que esperaban/)).toBeInTheDocument();
  });

  it("avisa si la definición no se puede guardar", async () => {
    api.crearDefinicion.mockRejectedValue({ response: { data: { detail: "La cuenta 1 es de agrupación" } } });
    const u = userEvent.setup();
    render(<TransaccionesPage />);
    await u.click(await screen.findByRole("button", { name: "Definir asiento" }));
    const modal = screen.getByRole("dialog", { name: /Cómo se contabiliza/ });
    await u.selectOptions(within(modal).getByLabelText("Cuenta 1"), "1.1.04");
    await u.type(within(modal).getByLabelText("Importe 1"), "capital");
    await u.selectOptions(within(modal).getByLabelText("Cuenta 2"), "1.1.02");
    await u.type(within(modal).getByLabelText("Importe 2"), "capital");
    await u.click(within(modal).getByRole("button", { name: /Guardar y contabilizar/ }));
    expect(await within(modal).findByText("La cuenta 1 es de agrupación")).toBeInTheDocument();
  });

  it("se puede definir un asiento sin esperar a que llegue una transacción", async () => {
    const u = userEvent.setup();
    render(<TransaccionesPage />);
    await u.click(await screen.findByRole("button", { name: /Definir un asiento/ }));
    const modal = screen.getByRole("dialog", { name: "Nueva definición de asiento" });
    await u.type(within(modal).getByLabelText("Módulo"), "tesoreria");
    await u.type(within(modal).getByLabelText("Tipo de transacción"), "pago_proveedor");
    await u.selectOptions(within(modal).getByLabelText("Cuenta 1"), "1.1.04");
    await u.type(within(modal).getByLabelText("Importe 1"), "importe");
    await u.selectOptions(within(modal).getByLabelText("Cuenta 2"), "1.1.02");
    await u.type(within(modal).getByLabelText("Importe 2"), "importe");
    await u.click(within(modal).getByRole("button", { name: /Guardar y contabilizar/ }));
    await waitFor(() => expect(api.crearDefinicion).toHaveBeenCalledWith(
      expect.objectContaining({ modulo: "tesoreria", tipo: "PAGO_PROVEEDOR" })));
  });

  it("el detalle muestra lo que mandó el módulo y el asiento generado", async () => {
    api.verTransaccion.mockResolvedValue({
      ...PENDIENTE.ejemplo, estado: "CONTABILIZADA", motivo: "",
      asiento: { id: 3, numero: 7, lineas: [
        { cuenta: "1.1.04", nombre: "Préstamos otorgados", debe: 100000, haber: 0 },
        { cuenta: "1.1.02", nombre: "Bancos", debe: 0, haber: 100000 }] },
    });
    const u = userEvent.setup();
    render(<TransaccionesPage />);
    await u.click(await screen.findByText("CTO-1"));
    const modal = await screen.findByRole("dialog", { name: /DESEMBOLSO · CTO-1/ });
    expect(within(modal).getByText(/Asiento generado \(N° 7\)/)).toBeInTheDocument();
    expect(within(modal).getByText(/"capital": 100000/)).toBeInTheDocument();
  });

  it("sin permiso de configurar no ofrece definir", async () => {
    sesion(["asientos:read"]);
    render(<TransaccionesPage />);
    await screen.findAllByText("DESEMBOLSO");
    expect(screen.queryByRole("button", { name: "Definir asiento" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Definir un asiento/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Volver a procesar" })).not.toBeInTheDocument();
  });
});
