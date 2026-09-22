import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/contabilidad", async (orig) => ({
  ...(await orig()),
  listarDefiniciones: vi.fn(), listarCuentas: vi.fn(), listarDiarios: vi.fn(),
  crearDefinicion: vi.fn(), editarDefinicion: vi.fn(), probarDefinicion: vi.fn(),
}));

import * as api from "../../../api/contabilidad";
import DefinicionesPage from "./DefinicionesPage";
import { useAuthStore } from "../../../context/authStore";

const DEF = {
  id: 4, modulo: "creditos", tipo: "DESEMBOLSO", nombre: "Desembolso de crédito", diario: "BANCO",
  leyenda: "Desembolso {referencia}", activa: true, vigenteDesde: null, vigenteHasta: null,
  lineas: [{ dc: "DEBE", cuenta: "1.1.05.01", importe: "capital" },
           { dc: "HABER", cuenta: "1.1.02", importe: "capital" }],
};

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "conta" },
  permissions: { modules: ["contabilidad"], actions: { contabilidad: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["asientos:read", "definiciones:write"]);
  api.listarDefiniciones.mockResolvedValue({ items: [DEF], total: 1 });
  api.listarCuentas.mockResolvedValue({ items: [
    { codigo: "1.1.05.01", nombre: "Préstamos otorgados" }, { codigo: "1.1.02", nombre: "Banco" }] });
  api.listarDiarios.mockResolvedValue({ items: [{ codigo: "VAR", nombre: "Varios" }, { codigo: "BANCO", nombre: "Banco" }] });
  api.editarDefinicion.mockResolvedValue({ ...DEF, reproceso: { contabilizadas: 3 } });
  api.probarDefinicion.mockResolvedValue({ debe: 1000, haber: 1000, lineas: [
    { cuenta: "1.1.05.01", nombre: "Préstamos otorgados", debe: 1000, haber: 0 },
    { cuenta: "1.1.02", nombre: "Banco", debe: 0, haber: 1000 }] });
});

describe("Definiciones de asiento", () => {
  it("lista las definiciones con su asiento", async () => {
    render(<DefinicionesPage />);
    expect(await screen.findByText("DESEMBOLSO")).toBeInTheDocument();
    expect(screen.getByText(/D · 1.1.05.01/)).toBeInTheDocument();
    expect(screen.getByText(/H · 1.1.02/)).toBeInTheDocument();
    expect(screen.getByText("activa")).toBeInTheDocument();
  });

  it("edita una definición y avisa lo que se recontabilizó", async () => {
    const u = userEvent.setup();
    render(<DefinicionesPage />);
    await u.click(await screen.findByText("DESEMBOLSO"));
    const modal = screen.getByRole("dialog", { name: /Definición · DESEMBOLSO/ });
    await u.clear(within(modal).getByLabelText("Nombre"));
    await u.type(within(modal).getByLabelText("Nombre"), "Desembolso corregido");
    await u.click(within(modal).getByRole("button", { name: /Guardar y contabilizar/ }));
    await waitFor(() => expect(api.editarDefinicion).toHaveBeenCalledWith(4, expect.objectContaining({
      nombre: "Desembolso corregido", modulo: "creditos", tipo: "DESEMBOLSO" })));
    expect(await screen.findByText(/se contabilizaron 3 transacción/)).toBeInTheDocument();
  });

  it("prueba la definición y muestra el asiento que saldría", async () => {
    const u = userEvent.setup();
    render(<DefinicionesPage />);
    await u.click(await screen.findByText("DESEMBOLSO"));
    await u.click(screen.getByRole("button", { name: "Probar" }));
    expect(await screen.findByText(/Así queda el asiento/)).toBeInTheDocument();
    expect(screen.getByText(/1.1.05.01 Préstamos otorgados · debe/)).toBeInTheDocument();
  });

  it("sólo lectura: no deja crear ni editar", async () => {
    const u = userEvent.setup();
    sesion(["asientos:read"]);
    render(<DefinicionesPage />);
    await u.click(await screen.findByText("DESEMBOLSO"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nueva definición/ })).not.toBeInTheDocument();
  });
});
