import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TurnosOtorgadosPage from "./TurnosOtorgadosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { turnosOtorgados: vi.fn(), descargarTurnosExcel: vi.fn() },
}));

const DATOS = {
  total: 80,
  items: [
    { fecha: "2026-03-01", periodo: "2026-03", tipo: "TODO", numero: 15, apellido_nombre: "PEREZ JUAN",
      cuil: "20-1-1", sueldo: 700000, usado: true, autorizado: false },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.turnosOtorgados.mockResolvedValue(DATOS);
});

describe("Turnos otorgados", () => {
  it("lista los turnos del período", async () => {
    render(<TurnosOtorgadosPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(creditos.turnosOtorgados).toHaveBeenCalledWith(
      { q: undefined, tipo: undefined, usado: undefined, limit: 25, offset: 0 });
    expect(screen.getByText("80 turnos")).toBeInTheDocument();
  });

  it("filtra por tipo y por uso", async () => {
    const u = userEvent.setup();
    render(<TurnosOtorgadosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Tipo"), "AGAP");
    await waitFor(() => expect(creditos.turnosOtorgados).toHaveBeenLastCalledWith(
      expect.objectContaining({ tipo: "AGAP" })));

    await u.selectOptions(screen.getByLabelText("Uso"), "no");
    await waitFor(() => expect(creditos.turnosOtorgados).toHaveBeenLastCalledWith(
      expect.objectContaining({ tipo: "AGAP", usado: false })));
  });

  it("buscar por solicitante recarga desde la primera página", async () => {
    const u = userEvent.setup();
    render(<TurnosOtorgadosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.type(screen.getByPlaceholderText("Buscar solicitante / CUIL"), "perez");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => expect(creditos.turnosOtorgados).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "perez", offset: 0 })));
  });

  it("Limpiar filtros vuelve al listado completo", async () => {
    const u = userEvent.setup();
    render(<TurnosOtorgadosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Tipo"), "TODO");
    await waitFor(() => expect(creditos.turnosOtorgados).toHaveBeenLastCalledWith(
      expect.objectContaining({ tipo: "TODO" })));

    await u.click(screen.getByRole("button", { name: /limpiar filtros/i }));
    await waitFor(() => expect(creditos.turnosOtorgados).toHaveBeenLastCalledWith(
      { q: undefined, tipo: undefined, usado: undefined, limit: 25, offset: 0 }));
  });

  it("el Excel sale con los mismos filtros", async () => {
    const u = userEvent.setup();
    render(<TurnosOtorgadosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Uso"), "si");
    await u.click(screen.getByRole("button", { name: "Excel" }));
    expect(creditos.descargarTurnosExcel).toHaveBeenCalledWith(
      { q: undefined, tipo: undefined, usado: true });
  });
});
