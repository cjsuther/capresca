import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/contabilidad", async (orig) => ({
  ...(await orig()),
  listarCuentas: vi.fn(), verConciliacion: vi.fn(), cargarExtracto: vi.fn(), borrarExtracto: vi.fn(),
  conciliar: vi.fn(), desconciliar: vi.fn(), conciliarAutomatica: vi.fn(),
}));

import * as api from "../../../api/contabilidad";
import ConciliacionPage from "./ConciliacionPage";
import { useAuthStore } from "../../../context/authStore";

const DATOS = {
  cuenta: { codigo: "1.1.02", nombre: "Bancos" },
  extracto: [
    { id: 1, fecha: "2026-09-20", descripcion: "Transferencia recibida", importe: 3000, conciliada: false },
    { id: 2, fecha: "2026-09-21", descripcion: "Gastos bancarios", importe: -500, conciliada: true },
  ],
  movimientos: [
    { asientoLineaId: 11, asientoId: 5, numero: 5, fecha: "2026-09-20", concepto: "Cobro", importe: 3000, conciliada: false },
  ],
  totales: { saldoExtracto: 2500, saldoMayor: 3000, diferencia: -500, pendienteExtracto: 3000,
             pendienteMayor: 3000, conciliadas: 1 },
};

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "conta" },
  permissions: { modules: ["contabilidad"], actions: { contabilidad: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["asientos:read", "asientos:write"]);
  api.listarCuentas.mockResolvedValue({ items: [{ codigo: "1.1.02", nombre: "Bancos" }, { codigo: "4.1.04", nombre: "Ingresos" }] });
  api.verConciliacion.mockResolvedValue(DATOS);
  api.conciliar.mockResolvedValue({ conciliada: true });
  api.conciliarAutomatica.mockResolvedValue({ conciliadas: 1 });
  api.cargarExtracto.mockResolvedValue({ id: 3 });
});

describe("Conciliación bancaria", () => {
  it("muestra las dos columnas y la diferencia", async () => {
    render(<ConciliacionPage />);
    expect(await screen.findByText("Transferencia recibida")).toBeInTheDocument();
    expect(screen.getByText("Cobro")).toBeInTheDocument();
    expect(screen.getAllByText("-$ 500,00").length).toBe(2);        // la diferencia y el gasto del extracto
    expect(screen.getAllByText("conciliada").length).toBeGreaterThan(0);
  });

  it("concilia eligiendo la línea del extracto y su movimiento", async () => {
    const u = userEvent.setup();
    render(<ConciliacionPage />);
    await u.click(await screen.findByText("Transferencia recibida"));
    expect(screen.getByText("seleccionada")).toBeInTheDocument();
    await u.click(screen.getByText("Cobro"));
    await waitFor(() => expect(api.conciliar).toHaveBeenCalledWith(1, 11));
  });

  it("avisa si se elige un movimiento sin haber elegido el extracto", async () => {
    const u = userEvent.setup();
    render(<ConciliacionPage />);
    await u.click(await screen.findByText("Cobro"));
    expect(screen.getByText("Elegí primero una línea del extracto.")).toBeInTheDocument();
    expect(api.conciliar).not.toHaveBeenCalled();
  });

  it("carga una línea del extracto", async () => {
    const u = userEvent.setup();
    render(<ConciliacionPage />);
    await screen.findByText("Transferencia recibida");
    await u.type(screen.getByLabelText("Importe del extracto"), "-1200");
    await u.click(screen.getByRole("button", { name: "Agregar" }));
    await waitFor(() => expect(api.cargarExtracto).toHaveBeenCalledWith(
      expect.objectContaining({ cuenta_codigo: "1.1.02", importe: -1200 })));
  });

  it("concilia automáticamente y muestra el resultado", async () => {
    const u = userEvent.setup();
    render(<ConciliacionPage />);
    await screen.findByText("Transferencia recibida");
    await u.click(screen.getByRole("button", { name: /Conciliar automáticamente/ }));
    expect(await screen.findByText("1 par(es) conciliado(s) automáticamente.")).toBeInTheDocument();
  });

  it("sólo lectura: no ofrece cargar ni conciliar", async () => {
    sesion(["asientos:read"]);
    render(<ConciliacionPage />);
    await screen.findByText("Transferencia recibida");
    expect(screen.queryByLabelText("Importe del extracto")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conciliar automáticamente/ })).not.toBeInTheDocument();
  });
});
