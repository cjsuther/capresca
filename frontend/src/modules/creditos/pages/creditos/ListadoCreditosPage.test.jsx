import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ListadoCreditosPage from "./ListadoCreditosPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { listadoCreditos: vi.fn(), descargarListadoCreditosExcel: vi.fn() },
}));

const DATOS = {
  total: 800, total_saldo: 250000000,
  items: [
    { credito_id: 900, cliente: "PEREZ JUAN", linea: "PERSONAL", capital: 500000, saldo: 300000, estado: "A" },
    { credito_id: 901, cliente: "GOMEZ ANA", linea: "ESPECIAL", capital: 200000, saldo: 0, estado: "C" },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.listadoCreditos.mockResolvedValue(DATOS);
});

describe("Listado de créditos", () => {
  it("carga la cartera con capital, saldo y estado en castellano", async () => {
    render(<ListadoCreditosPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(creditos.listadoCreditos).toHaveBeenCalledWith(
      { estado: undefined, q: undefined, limit: 25, offset: 0, sort: "credito_id", order: "desc" });
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("Cancelado")).toBeInTheDocument();
    expect(screen.getByText(/800 créditos/)).toBeInTheDocument();
  });

  it("filtra por estado y por texto", async () => {
    const u = userEvent.setup();
    render(<ListadoCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Estado"), "A");
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "A" })));

    await u.type(screen.getByPlaceholderText("Buscar cliente / CUIL"), "perez");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "perez", estado: "A" })));
  });

  it("ordenar por una columna lo pide al servidor e invierte al segundo clic", async () => {
    const u = userEvent.setup();
    render(<ListadoCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.click(screen.getByText("Saldo"));
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: "saldo", order: "asc" })));
    await u.click(screen.getByText("Saldo"));
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: "saldo", order: "desc" })));
  });

  it("Limpiar filtros vuelve al listado completo", async () => {
    const u = userEvent.setup();
    render(<ListadoCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Estado"), "C");
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "C" })));

    await u.click(screen.getByRole("button", { name: /limpiar filtros/i }));
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: undefined, q: undefined })));
  });

  it("el Excel usa los filtros y el orden vigentes", async () => {
    const u = userEvent.setup();
    render(<ListadoCreditosPage />);
    await screen.findByText("PEREZ JUAN");

    await u.selectOptions(screen.getByLabelText("Estado"), "A");
    await waitFor(() => expect(creditos.listadoCreditos).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "A" })));
    await u.click(screen.getByRole("button", { name: "Descargar Excel" }));
    expect(creditos.descargarListadoCreditosExcel).toHaveBeenCalledWith(
      { estado: "A", q: undefined, sort: "credito_id", order: "desc" });
  });
});
