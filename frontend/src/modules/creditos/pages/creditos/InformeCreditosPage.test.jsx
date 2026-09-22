import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InformeCreditosPage from "./InformeCreditosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: {
    informeCreditos: vi.fn(), lineas: vi.fn(), situacionPorCartera: vi.fn(),
    adminOrganismos: vi.fn(), descargarInformeCreditosExcel: vi.fn(),
  },
}));

const DATOS = {
  total: 300, total_capital: 90000000, total_saldo: 40000000,
  items: [
    { credito_id: 900, cliente: "PEREZ JUAN", cuil: "20-1-1", linea: "PERSONAL",
      fecha_otorgamiento: "2025-06-01", capital: 500000, saldo: 300000, estado: "A" },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.informeCreditos.mockResolvedValue(DATOS);
  creditos.lineas.mockResolvedValue([{ id: 12, nombre: "PERSONAL" }]);
  creditos.situacionPorCartera.mockResolvedValue({ por_cartera: [{ cartera: 1, nombre: "ACTIVOS" }] });
  creditos.adminOrganismos.mockResolvedValue([{ id: 3, nombre: "MINISTERIO" }]);
});

describe("Informe de créditos", () => {
  it("al entrar trae el informe sin filtros y llena los combos", async () => {
    render(<InformeCreditosPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(creditos.informeCreditos).toHaveBeenCalledWith(expect.objectContaining({
      estado: undefined, limit: 25, offset: 0, sort: "credito_id", order: "desc",
    }));
    await waitFor(() => expect(screen.getByLabelText("Línea")).toHaveTextContent("PERSONAL"));
    expect(screen.getByLabelText("Cartera")).toHaveTextContent("ACTIVOS");
    expect(screen.getByLabelText("Organismo")).toHaveTextContent("MINISTERIO");
  });

  it("los filtros se aplican recién con Generar", async () => {
    const u = userEvent.setup();
    render(<InformeCreditosPage />);
    await screen.findByText("PEREZ JUAN");
    creditos.informeCreditos.mockClear();

    await u.selectOptions(screen.getByLabelText("Estado"), "A");
    await u.selectOptions(screen.getByLabelText("Saldo"), "true");
    await u.type(screen.getByLabelText("Buscar cliente / CUIL"), "perez");
    expect(creditos.informeCreditos).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Generar" }));
    await waitFor(() => expect(creditos.informeCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "A", con_saldo: "true", q: "perez" })));
  });

  it("Limpiar vuelve al informe completo", async () => {
    const u = userEvent.setup();
    render(<InformeCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Estado"), "C");
    await u.click(screen.getByRole("button", { name: "Generar" }));
    await waitFor(() => expect(creditos.informeCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "C" })));

    await u.click(screen.getByRole("button", { name: "Limpiar" }));
    await waitFor(() => expect(creditos.informeCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: undefined })));
    expect(screen.getByLabelText("Estado")).toHaveValue("");
  });

  it("ordenar por una columna lo pide al servidor", async () => {
    const u = userEvent.setup();
    render(<InformeCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.click(screen.getByRole("columnheader", { name: /Saldo/ }));
    await waitFor(() => expect(creditos.informeCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: "saldo", order: "asc" })));
  });

  it("el Excel sale con los filtros aplicados, no con los tipeados", async () => {
    const u = userEvent.setup();
    render(<InformeCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Estado"), "A");      // sin Generar
    await u.click(screen.getByRole("button", { name: "Descargar Excel" }));
    expect(creditos.descargarInformeCreditosExcel).toHaveBeenCalledWith(
      expect.objectContaining({ estado: undefined, sort: "credito_id", order: "desc" }));
  });
});
