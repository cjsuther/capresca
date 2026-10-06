import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LiquidacionLotePage from "./LiquidacionLotePage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ctoLotesLiquidacion: vi.fn(), ctoLiquidarLote: vi.fn(), ctoMoverDeLote: vi.fn() },
}));

const RES = { id: 7, numero: 45, anio: 2026, numeroOficial: 120, fecha: "2026-03-12", importe: 2000000 };
const item = (id, extra = {}) => ({ id, tipo: "solicitud", solicitudId: id, solicitud: `SOL-${id}`, cliente: `CLIENTE ${id}`,
                                    monto: 300000, plazo: 12, estadoSolicitud: "APROBADA", ...extra });
const LOTES = {
  items: [
    { id: 11, codigo: "2026-0007", anio: 2026, numero: 7, producto: "PERSONAL", productoId: "p1", fecha: "2026-03-10",
      estado: "CON_RESOLUCION", resolucion: RES, cantidad: 2, maximo: 50, montoTotal: 600000, pendientes: 0,
      contratos: [item("a"), item("b")] },
    { id: 12, codigo: "2026-0008", anio: 2026, numero: 8, producto: "PERSONAL", productoId: "p1", fecha: "2026-03-10",
      estado: "ABIERTO", resolucion: null, cantidad: 1, maximo: 50, montoTotal: 300000, pendientes: 0,
      contratos: [item("c")] },
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
});

describe("Lotes", () => {
  it("lista los lotes con tipo, fecha, resolución y estado", async () => {
    montar();
    const fila = (await screen.findByText("2026-0007")).closest("tr");
    expect(within(fila).getByText("PERSONAL")).toBeInTheDocument();
    expect(within(fila).getByText("10/3/2026")).toBeInTheDocument();
    expect(within(fila).getByText("Resolución N° 120/2026 · 12/3/2026")).toBeInTheDocument();
    expect(within(fila).getByText("Con resolución")).toBeInTheDocument();
    expect(within(screen.getByText("2026-0008").closest("tr")).getByText("Esperando resolución")).toBeInTheDocument();
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

  it("sin resolución el lote no se liquida", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0008"));
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

  it("una solicitud se mueve a otro lote del mismo tipo y fecha, o a uno nuevo", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    const fila = screen.getByText("SOL-a").closest("tr");
    await u.click(within(fila).getByRole("button"));
    await u.click(await screen.findByText(/Mover a otro lote/));

    const dlg = await screen.findByRole("dialog", { name: "Mover SOL-a" });
    const combo = within(dlg).getByLabelText("Lote de destino");
    expect([...combo.options].map((o) => o.textContent)).toEqual([
      "2026-0008 · 1 solicitud(es) · Esperando resolución", "Lote nuevo"]);
    await u.click(within(dlg).getByRole("button", { name: "Mover" }));
    await waitFor(() => expect(creditos.ctoMoverDeLote).toHaveBeenCalledWith({ solicitud_id: "a", destino_id: 12 }));
    expect(await screen.findByText("SOL-a pasó al lote 2026-0008.")).toBeInTheDocument();
  });

  it("en sólo lectura se ve el lote pero no se liquida", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("2026-0007"));
    expect(await screen.findByText("SOL-a")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Liquidar lote/ })).toBeNull();
  });

  it("sin lotes pendientes lo dice", async () => {
    creditos.ctoLotesLiquidacion.mockResolvedValue({ items: [], fueraDeLote: [] });
    montar();
    expect((await screen.findAllByText("No hay lotes pendientes.")).length).toBeGreaterThan(0);
  });
});
