import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnexoPage from "./AnexoPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const sol = (extra = {}) => ({
  id: 11, fecha_solicitud: "2026-05-02", cuil: "20301112223", apellido_nombre: "PEREZ JUAN",
  dni: "30111222", monto: "500000", linea: 6810, linea_nombre: "Microcrédito", estado: "A",
  cubica: "C", lote: 0, numero_resolucion: 0, en_resolucion: false, ...extra,
});

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: ["resoluciones:read", "resoluciones:write"] } },
  });
  api.getTiposAnexo.mockResolvedValue([{ tipo: 2, nombre: "Microcréditos" }, { tipo: 6, nombre: "Resto" }]);
  api.getSolicitudesAnexo.mockResolvedValue({ tipo: 6, nombre: "Resto", cantidad: 1,
                                              total: "500000", items: [sol()] });
  api.getResoluciones.mockResolvedValue({
    items: [{ id: 1, numero: 45, anio: 2026, motivo: "OTORGAMIENTO", asunto: "" }], total: 1 });
});

describe("anexo de resolución", () => {
  it("lista las candidatas del tipo elegido con su total", async () => {
    render(<AnexoPage />);
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    // El importe está en la fila y repetido en el total del pie.
    expect(screen.getAllByText("$ 500.000,00")).toHaveLength(2);
    expect(screen.getByText("1 solicitud(es)")).toBeInTheDocument();
  });

  it("cambiar el tipo vuelve a pedir las candidatas de ese rango de líneas", async () => {
    const user = userEvent.setup();
    render(<AnexoPage />);
    await screen.findByText("PEREZ JUAN");

    await user.selectOptions(await screen.findByLabelText("Tipo de anexo"), "2");
    await waitFor(() => expect(api.getSolicitudesAnexo).toHaveBeenLastCalledWith({ tipo: 2 }));
  });

  it("asigna las elegidas a una resolución en borrador", async () => {
    const user = userEvent.setup();
    api.asignarAnexo.mockResolvedValue({ asignadas: 1, total: "500000", numero: 45, anio: 2026 });
    render(<AnexoPage />);

    await user.click(await screen.findByLabelText("Elegir PEREZ JUAN"));
    await user.selectOptions(screen.getByLabelText("Resolución en borrador"), "1");
    await user.click(screen.getByRole("button", { name: /Asignar al anexo/ }));

    expect(api.asignarAnexo).toHaveBeenCalledWith({ tipo: 6, resolucion_id: 1, solicitud_ids: [11] });
    expect(await screen.findByText(/en la resolución N° 45\/2026/)).toBeInTheDocument();
  });

  it("sólo ofrece resoluciones todavía en borrador", async () => {
    render(<AnexoPage />);
    await screen.findByText("PEREZ JUAN");
    expect(api.getResoluciones).toHaveBeenCalledWith(expect.objectContaining({ estado: "B" }));
  });

  it("en la vista del anexo armado se busca por lote y se puede quitar", async () => {
    const user = userEvent.setup();
    api.quitarDelAnexo.mockResolvedValue({ quitadas: 1 });
    render(<AnexoPage />);
    await screen.findByText("PEREZ JUAN");

    await user.click(screen.getByRole("button", { name: "Ver anexo armado" }));
    await user.type(screen.getByLabelText("Lote"), "45");
    await user.click(screen.getByRole("button", { name: "Ver" }));
    await waitFor(() => expect(api.getSolicitudesAnexo).toHaveBeenLastCalledWith({ lote: 45 }));

    await user.click(await screen.findByLabelText("Elegir PEREZ JUAN"));
    await user.click(screen.getByRole("button", { name: "Quitar del anexo" }));
    expect(api.quitarDelAnexo).toHaveBeenCalledWith([11]);
  });

  it("muestra el motivo cuando el backend rechaza la asignación", async () => {
    const user = userEvent.setup();
    api.asignarAnexo.mockRejectedValue(
      { response: { data: { detail: "Estas solicitudes ya están en otra resolución: [11]." } } });
    render(<AnexoPage />);

    await user.click(await screen.findByLabelText("Elegir PEREZ JUAN"));
    await user.selectOptions(screen.getByLabelText("Resolución en borrador"), "1");
    await user.click(screen.getByRole("button", { name: /Asignar al anexo/ }));
    expect(await screen.findByText(/ya están en otra resolución/)).toBeInTheDocument();
  });
});
