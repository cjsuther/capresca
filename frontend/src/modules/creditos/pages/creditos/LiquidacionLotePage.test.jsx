import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LiquidacionLotePage from "./LiquidacionLotePage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ctoLotesLiquidacion: vi.fn(), ctoLiquidarLote: vi.fn(), ctoMoverDeLote: vi.fn(),
              ctoCerrarLote: vi.fn(), ctoReabrirLote: vi.fn(), ctoTopesLote: vi.fn(), ctoGuardarTopesLote: vi.fn() },
}));

const RES = { id: 7, numero: 45, anio: 2026, numeroOficial: 120, fecha: "2026-03-12", importe: 2000000 };
const item = (id, extra = {}) => ({ id, tipo: "solicitud", solicitudId: id, solicitud: `SOL-${id}`, cliente: `CLIENTE ${id}`,
                                    monto: 300000, plazo: 12, estadoSolicitud: "APROBADA", ...extra });
const LOTES = {
  items: [
    { id: 11, codigo: "2026-0007", anio: 2026, numero: 7, producto: "PERSONAL", productoId: "p1", fecha: "2026-03-10",
      estado: "CON_RESOLUCION", resolucion: RES, cantidad: 2, maximo: 50, montoTotal: 600000, pendientes: 0,
      cerradoPor: "ana", cerradoEn: "2026-03-11T10:30:00", contratos: [item("a"), item("b")] },
    { id: 12, codigo: "2026-0008", anio: 2026, numero: 8, producto: "PERSONAL", productoId: "p1", fecha: "2026-03-10",
      estado: "ABIERTO", resolucion: null, cantidad: 1, maximo: 50, montoTotal: 300000, pendientes: 0,
      contratos: [item("c")] },
    { id: 13, codigo: "2026-0009", anio: 2026, numero: 9, producto: "PERSONAL", productoId: "p1", fecha: "2026-03-10",
      estado: "CERRADO", resolucion: null, cantidad: 1, maximo: 50, montoTotal: 300000, pendientes: 0,
      cerradoPor: "luis", cerradoEn: "2026-03-11T09:00:00", contratos: [item("d")] },
  ],
  maximo: 50,
  fueraDeLote: [{ id: "z", numero: "SOL-Z", cliente: "SIN CBU", producto: "PERSONAL", monto: 1000,
                  faltantes: ["CBU de acreditación (22 dígitos)"] }],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

const montar = () => render(<MemoryRouter><LiquidacionLotePage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ctoLotesLiquidacion.mockResolvedValue(LOTES);
  creditos.ctoLiquidarLote.mockResolvedValue({ desembolsados: ["c1", "c2"], pendientesAprobacion: [], errores: [] });
  creditos.ctoMoverDeLote.mockResolvedValue({ id: 12, codigo: "2026-0008" });
  creditos.ctoCerrarLote.mockResolvedValue({ id: 12, codigo: "2026-0008", estado: "CERRADO" });
  creditos.ctoReabrirLote.mockResolvedValue({ id: 13, codigo: "2026-0009", estado: "ABIERTO" });
});

describe("Lotes", () => {
  it("lista los lotes con tipo, fecha, resolución y estado", async () => {
    montar();
    const fila = (await screen.findByText("2026-0007")).closest("tr");
    expect(within(fila).getByText("PERSONAL")).toBeInTheDocument();
    expect(within(fila).getByText("10/3/2026")).toBeInTheDocument();
    expect(within(fila).getByText("Resolución N° 120/2026 · 12/3/2026")).toBeInTheDocument();
    expect(within(fila).getByText("Con resolución")).toBeInTheDocument();
    expect(within(screen.getByText("2026-0008").closest("tr")).getByText("Abierto")).toBeInTheDocument();
    expect(within(screen.getByText("2026-0009").closest("tr")).getByText("Cerrado")).toBeInTheDocument();
  });

  it("un lote abierto se verifica y se cierra, con confirmación", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0008"));
    expect(screen.queryByRole("button", { name: /Liquidar lote/ })).toBeNull();
    await u.click(screen.getByRole("button", { name: "Cerrar lote" }));
    const conf = await screen.findByRole("dialog", { name: "Cerrar el lote" });
    expect(within(conf).getByText(/Despacho ya le puede asignar la resolución/)).toBeInTheDocument();
    expect(creditos.ctoCerrarLote).not.toHaveBeenCalled();
    await u.click(within(conf).getByRole("button", { name: "Cerrar lote" }));
    await waitFor(() => expect(creditos.ctoCerrarLote).toHaveBeenCalledWith(12));
    expect(await screen.findByText(/Lote 2026-0008 cerrado/)).toBeInTheDocument();
  });

  it("un lote cerrado muestra quién lo cerró y se puede reabrir", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0009"));
    expect(screen.getByText("luis")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Reabrir lote" }));
    await waitFor(() => expect(creditos.ctoReabrirLote).toHaveBeenCalledWith(13));
  });

  it("muestra las aprobadas que quedaron fuera de lote y qué les falta", async () => {
    montar();
    expect(await screen.findByText(/Aprobadas fuera de lote \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("CBU de acreditación (22 dígitos)")).toBeInTheDocument();
  });

  it("un lote con resolución se liquida completo, con confirmación", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    expect(screen.getByText("SOL-a")).toBeInTheDocument();
    await u.click(await screen.findByRole("button", { name: /Liquidar lote \(2\)/ }));
    const conf = await screen.findByRole("dialog", { name: "Liquidar el lote" });
    expect(within(conf).getByText(/lote 2026-0007 completo/)).toBeInTheDocument();
    expect(creditos.ctoLiquidarLote).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Liquidar" }));
    await waitFor(() => expect(creditos.ctoLiquidarLote).toHaveBeenCalledWith(11));
    expect(await screen.findByText(/Lote 2026-0007 \(PERSONAL, 10\/3\/2026\) procesado.*Desembolsados: 2/)).toBeInTheDocument();
    expect(creditos.ctoLotesLiquidacion).toHaveBeenCalledTimes(2);
  });

  it("un lote cerrado sin resolución no se liquida", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0009"));
    expect(await screen.findByRole("button", { name: /Liquidar lote/ })).toBeDisabled();
    expect(screen.getByText(/se la asigna Despacho/)).toBeInTheDocument();
  });

  it("si la liquidación falla lo muestra", async () => {
    creditos.ctoLiquidarLote.mockRejectedValue(new Error("El lote no se puede liquidar completo. SOL-b: falta CBU"));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    await u.click(await screen.findByRole("button", { name: /Liquidar lote \(2\)/ }));
    await u.click(screen.getByRole("button", { name: "Liquidar" }));
    expect(await screen.findByText(/no se puede liquidar completo/)).toBeInTheDocument();
  });

  it("una solicitud se mueve a otro lote abierto del mismo tipo y fecha, o a uno nuevo", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    const fila = screen.getByText("SOL-a").closest("tr");
    await u.click(within(fila).getByRole("button"));
    await u.click(await screen.findByText(/Mover a otro lote/));

    const dlg = await screen.findByRole("dialog", { name: "Mover SOL-a" });
    const combo = within(dlg).getByLabelText("Lote de destino");
    expect([...combo.options].map((o) => o.textContent)).toEqual([
      "2026-0008 · 1 solicitud(es) · Abierto", "Lote nuevo"]);
    await u.click(within(dlg).getByRole("button", { name: "Mover" }));
    await waitFor(() => expect(creditos.ctoMoverDeLote).toHaveBeenCalledWith({ solicitud_id: "a", destino_id: 12 }));
    expect(await screen.findByText("SOL-a pasó al lote 2026-0008.")).toBeInTheDocument();
  });

  it("con Tesorería, el lote lo liquida una orden de pago y se ve en cuál está", async () => {
    creditos.ctoLotesLiquidacion.mockResolvedValue({ ...LOTES, viaTesoreria: true, items: [
      LOTES.items[0],
      { ...LOTES.items[1], id: 14, codigo: "2026-0010", estado: "PARA_LIQUIDAR", resolucion: RES,
        ordenPago: { id: 4, codigo: "OP-2026-00004" } }] });
    const u = userEvent.setup();
    montar();
    const fila = (await screen.findByText("2026-0010")).closest("tr");
    expect(within(fila).getByText("Para liquidar")).toBeInTheDocument();
    expect(within(fila).getByText("Orden de pago OP-2026-00004")).toBeInTheDocument();
    await u.click(screen.getByText("2026-0007"));
    expect(screen.queryByRole("button", { name: /Liquidar lote/ })).toBeNull();
    expect(screen.getByText(/Lo liquida Tesorería/)).toBeInTheDocument();
  });

  it("se carga el tope de monto de cada tipo de crédito", async () => {
    creditos.ctoTopesLote.mockResolvedValue({ maximo: 50, items: [
      { productoId: "p1", producto: "PERSONAL", topeMonto: null },
      { productoId: "p2", producto: "JUBILADOS", topeMonto: 1000000 }] });
    creditos.ctoGuardarTopesLote.mockResolvedValue({ items: [] });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: "Topes de monto" }));
    const dlg = await screen.findByRole("dialog", { name: "Tope de monto por tipo de crédito" });
    expect(within(dlg).getByLabelText("Tope de JUBILADOS")).toHaveValue(1000000);
    await u.type(within(dlg).getByLabelText("Tope de PERSONAL"), "2500000");
    await u.click(within(dlg).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(creditos.ctoGuardarTopesLote).toHaveBeenCalledWith([
      { producto_id: "p1", tope_monto: 2500000 }, { producto_id: "p2", tope_monto: 1000000 }]));
    expect(await screen.findByText(/Topes de monto guardados/)).toBeInTheDocument();
  });

  it("en sólo lectura se ve el lote pero no se liquida", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    expect(await screen.findByText("SOL-a")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Liquidar lote/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Topes de monto" })).toBeNull();
  });

  it("sin lotes pendientes lo dice", async () => {
    creditos.ctoLotesLiquidacion.mockResolvedValue({ items: [], fueraDeLote: [] });
    montar();
    expect((await screen.findAllByText("No hay lotes pendientes.")).length).toBeGreaterThan(0);
  });
});
