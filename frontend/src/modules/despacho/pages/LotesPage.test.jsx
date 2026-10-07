import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LotesPage from "./LotesPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const LOTES = {
  items: [
    { id: 1, codigo: "2026-0001", producto: "Préstamo personal", productoId: "p1", fecha: "2026-10-01",
      cantidad: 2, montoTotal: 300000, estado: "CERRADO", resolucion: null, resolucion_despacho: null,
      cerradoPor: "ana", cerradoEn: "2026-10-01T15:20:00" },
    { id: 2, codigo: "2026-0002", producto: "Préstamo personal", productoId: "p1", fecha: "2026-10-02",
      cantidad: 1, montoTotal: 150000, estado: "CERRADO", resolucion: null, resolucion_despacho: null,
      cerradoPor: "luis", cerradoEn: "2026-10-02T11:00:00" },
    { id: 4, codigo: "2026-0004", producto: "Vivienda", productoId: "p2", fecha: "2026-10-03",
      cantidad: 3, montoTotal: 50000, estado: "ABIERTO", resolucion: null, resolucion_despacho: null },
    { id: 3, codigo: "2026-0003", producto: "Vivienda", productoId: "p2", fecha: "2026-10-02",
      cantidad: 1, montoTotal: 90000, estado: "CON_RESOLUCION",
      resolucion: { id: 9, numero: 40, anio: 2026, numeroOficial: 120 },
      resolucion_despacho: { id: 9, numero: 40, anio: 2026, numero_real: 120 } },
  ],
  cantidad: 3, total: 540000,
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "resoluciones:write"]);
  api.getTiposLotes.mockResolvedValue([{ tipo: "", nombre: "Todos los tipos" }, { tipo: "p1", nombre: "Préstamo personal" }]);
  api.getLotes.mockResolvedValue(LOTES);
  api.getResoluciones.mockResolvedValue({ items: [
    { id: 5, numero: 45, anio: 2026, importe: "400000.00", motivo: "OTORGAMIENTO", anulada: false }] });
  api.getLotesDeResolucion.mockResolvedValue({ lotes: [], total: "0", importe: "400000.00", disponible: "400000.00" });
  api.asignarLotes.mockResolvedValue({ numero: 45, anio: 2026, asignados: ["2026-0001"], disponible: "100000.00" });
  api.quitarResolucionLote.mockResolvedValue({ lote: "2026-0003", estado: "ABIERTO" });
});

describe("Lotes de créditos (Despacho)", () => {
  it("lista los lotes con tipo, fecha, importe, resolución y estado", async () => {
    render(<LotesPage />);
    const fila = (await screen.findByText("2026-0003")).closest("tr");
    expect(within(fila).getByText("Vivienda")).toBeInTheDocument();
    expect(within(fila).getByText("N° 120/2026")).toBeInTheDocument();
    expect(within(fila).getByText("Con resolución")).toBeInTheDocument();
    expect(api.getLotes).toHaveBeenCalledWith({ estado: "CERRADO", tipo: "" });
  });

  it("sólo se eligen los lotes cerrados, y se ve quién los cerró", async () => {
    render(<LotesPage />);
    const cerrado = (await screen.findByText("2026-0001")).closest("tr");
    expect(within(cerrado).getByText("Cerrado")).toBeInTheDocument();
    expect(within(cerrado).getByText(/Cerrado por ana/)).toBeInTheDocument();
    expect(screen.getByLabelText("Elegir 2026-0001")).toBeInTheDocument();
    const abierto = screen.getByText("2026-0004").closest("tr");
    expect(within(abierto).getByText("Abierto")).toBeInTheDocument();
    expect(screen.queryByLabelText("Elegir 2026-0004")).toBeNull();
  });

  it("asigna una resolución a los lotes elegidos", async () => {
    const u = userEvent.setup();
    render(<LotesPage />);
    await u.click(await screen.findByLabelText("Elegir 2026-0001"));
    await u.selectOptions(screen.getByLabelText("Resolución en borrador"), "5");
    expect(await screen.findByText(/Disponible de la resolución/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Asignar resolución/ }));
    await waitFor(() => expect(api.asignarLotes).toHaveBeenCalledWith({ resolucion_id: 5, lote_ids: [1] }));
    expect(await screen.findByText(/asignada a 1 lote\(s\): 2026-0001/)).toBeInTheDocument();
  });

  it("no deja asignar si lo elegido supera lo disponible de la resolución", async () => {
    api.getLotesDeResolucion.mockResolvedValue({ lotes: [], total: "300000", importe: "400000", disponible: "100000" });
    const u = userEvent.setup();
    render(<LotesPage />);
    await u.click(await screen.findByLabelText("Elegir 2026-0002"));
    await u.selectOptions(screen.getByLabelText("Resolución en borrador"), "5");
    expect(await screen.findByText(/lo elegido lo supera/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Asignar resolución/ })).toBeDisabled();
  });

  it("muestra el motivo si Créditos rechaza la asignación", async () => {
    api.asignarLotes.mockRejectedValue({ response: { data: { detail: "La suma de los lotes supera el importe de la resolución." } } });
    const u = userEvent.setup();
    render(<LotesPage />);
    await u.click(await screen.findByLabelText("Elegir 2026-0001"));
    await u.selectOptions(screen.getByLabelText("Resolución en borrador"), "5");
    await u.click(await screen.findByRole("button", { name: /Asignar resolución/ }));
    expect(await screen.findByText(/supera el importe/)).toBeInTheDocument();
  });

  it("se le puede quitar la resolución a un lote", async () => {
    const u = userEvent.setup();
    render(<LotesPage />);
    const fila = (await screen.findByText("2026-0003")).closest("tr");
    await u.click(within(fila).getByRole("button", { name: "Quitar resolución" }));
    await waitFor(() => expect(api.quitarResolucionLote).toHaveBeenCalledWith(3));
  });

  it("en sólo lectura no se asigna ni se quita", async () => {
    sesion(["resoluciones:read"]);
    const u = userEvent.setup();
    render(<LotesPage />);
    await u.click(await screen.findByLabelText("Elegir 2026-0001"));
    expect(screen.queryByRole("button", { name: /Asignar resolución/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Quitar resolución" })).toBeNull();
  });
});
