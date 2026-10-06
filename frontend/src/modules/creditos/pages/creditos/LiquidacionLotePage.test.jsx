import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LiquidacionLotePage from "./LiquidacionLotePage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ctoLotesLiquidacion: vi.fn(), ctoLiquidarLote: vi.fn() },
}));

const LOTES = {
  items: [
    { id: 11, codigo: "2026-0007", anio: 2026, numero: 7, producto: "PERSONAL", fecha: "2026-03-10",
      cantidad: 2, ocupados: 2, maximo: 50, montoTotal: 900000, pendientes: 0,
      contratos: [
        { id: "c1", numero: "CTO-1", solicitud: "SOL-2026-00007", cliente: "PEREZ JUAN", producto: "PERSONAL", monto: 500000, plazo: 12 },
        { id: "c2", numero: "CTO-2", cliente: "GOMEZ ANA", producto: "PERSONAL", monto: 400000, plazo: 24 },
      ] },
    { id: 12, codigo: "2026-0008", anio: 2026, numero: 8, producto: "ESPECIAL", fecha: "2026-03-11",
      cantidad: 1, ocupados: 3, maximo: 50, montoTotal: 300000, pendientes: 1,
      contratos: [{ id: "c3", numero: "CTO-3", cliente: "LOPEZ SA", producto: "ESPECIAL", monto: 300000, plazo: 6, pendienteAprobacion: true }] },
  ],
  maximo: 50,
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ctoLotesLiquidacion.mockResolvedValue(LOTES);
  creditos.ctoLiquidarLote.mockResolvedValue({ desembolsados: ["c1", "c2"], pendientesAprobacion: [], errores: [] });
});

describe("Liquidación por lote", () => {
  it("lista los lotes con su número, tipo de crédito y fecha, y marca los que esperan aprobación", async () => {
    render(<LiquidacionLotePage />);
    const fila = (await screen.findByText("2026-0007")).closest("tr");
    expect(within(fila).getByText("PERSONAL")).toBeInTheDocument();
    expect(within(fila).getByText("10/3/2026")).toBeInTheDocument();
    // Del lote 8 quedan 1 por liquidar de los 3 que tuvo.
    expect(within(screen.getByText("2026-0008").closest("tr")).getByText("1 de 3")).toBeInTheDocument();
    expect(screen.getByText(/hasta 50 créditos por lote/)).toBeInTheDocument();
    expect(screen.getByText("A liquidar")).toBeInTheDocument();
    expect(screen.getByText("1 esperando aprobación")).toBeInTheDocument();
    expect(screen.getByText(/2 lote\(s\) pendientes/)).toBeInTheDocument();
  });

  it("clickear un lote abre sus créditos", async () => {
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0007"));

    const modal = await screen.findByRole("heading", { name: /2 crédito\(s\)/ });
    expect(modal).toBeInTheDocument();
    expect(screen.getByText("CTO-1")).toBeInTheDocument();
    expect(screen.getByText("GOMEZ ANA")).toBeInTheDocument();
    expect(screen.getByText("SOL-2026-00007")).toBeInTheDocument();   // la solicitud que lo originó
  });

  it("liquidar pide confirmación y resume el resultado", async () => {
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0007"));
    await u.click(await screen.findByRole("button", { name: /Liquidar lote \(2\)/ }));

    // Sobre el detalle del lote se abre la confirmación (dos diálogos superpuestos).
    expect(await screen.findByRole("dialog", { name: "Liquidar el lote" })).toBeInTheDocument();
    expect(creditos.ctoLiquidarLote).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Liquidar" }));
    await waitFor(() => expect(creditos.ctoLiquidarLote).toHaveBeenCalledWith(11));
    expect(await screen.findByText(/Lote 2026-0007 \(PERSONAL, 10\/3\/2026\) procesado.*Desembolsados: 2/)).toBeInTheDocument();
    expect(creditos.ctoLotesLiquidacion).toHaveBeenCalledTimes(2);      // recarga
  });

  it("informa los créditos que quedaron esperando aprobación", async () => {
    creditos.ctoLiquidarLote.mockResolvedValue({ desembolsados: ["c1"], pendientesAprobacion: ["c2"], errores: [] });
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0007"));
    await u.click(await screen.findByRole("button", { name: /Liquidar lote \(2\)/ }));
    await u.click(screen.getByRole("button", { name: "Liquidar" }));
    expect(await screen.findByText(/Pendientes de aprobación: 1/)).toBeInTheDocument();
  });

  it("un lote con créditos en aprobación lo avisa dentro del detalle", async () => {
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0008"));
    expect(await screen.findByText(/1 crédito\(s\) de este lote ya están esperando/)).toBeInTheDocument();
  });

  it("si la liquidación falla lo muestra", async () => {
    creditos.ctoLiquidarLote.mockRejectedValue(new Error("El ejercicio contable está cerrado"));
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0007"));
    await u.click(await screen.findByRole("button", { name: /Liquidar lote \(2\)/ }));
    await u.click(screen.getByRole("button", { name: "Liquidar" }));
    expect(await screen.findByText("El ejercicio contable está cerrado")).toBeInTheDocument();
  });

  it("en sólo lectura se ve el lote pero no se liquida", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<LiquidacionLotePage />);
    await u.click(await screen.findByText("2026-0007"));
    expect(await screen.findByText("CTO-1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Liquidar lote/ })).toBeNull();
  });

  it("sin lotes pendientes lo dice", async () => {
    creditos.ctoLotesLiquidacion.mockResolvedValue({ items: [] });
    render(<LiquidacionLotePage />);
    expect(await screen.findByText("No hay créditos pendientes de liquidar.")).toBeInTheDocument();
  });
});
