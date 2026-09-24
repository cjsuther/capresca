import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResolucionesPage from "./ResolucionesPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const res = (extra = {}) => ({
  id: 1, numero: 45, anio: 2026, tipo: "RES", fecha: "2026-06-10", numero_real: null,
  fecha_real: null, organo: "DIRECTORIO", asunto: "Transferencia", motivo: "TRANSFERENCIA",
  motivo_codigo: 103, importe: "125000.50", modelo_id: 3, origen: "EXP C 1234 2026", nro_op: null,
  estado: "B", anulada: false, motivo_anulacion: "", creado_por: "ana", creado_en: null, ...extra,
});
const detalle = (extra = {}) => ({ ...res(extra), texto: "<p>Cuerpo</p>", beneficiarios: [] });

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "resoluciones:write", "resoluciones:firmar"]);
  api.getResoluciones.mockResolvedValue({ items: [res()], total: 1, pagina: 1, por_pagina: 20 });
  api.getModelos.mockResolvedValue([
    { id: 3, codigo: 103, descripcion: "TRANSFERENCIA", tipo: "RES", plantilla: "<p>VISTO…</p>" },
  ]);
  document.execCommand = vi.fn();
});

describe("resoluciones y disposiciones", () => {
  it("lista con el correlativo, el N° oficial y el estado", async () => {
    render(<ResolucionesPage />);
    expect(await screen.findByText("45/2026")).toBeInTheDocument();
    expect(screen.getByText("TRANSFERENCIA")).toBeInTheDocument();
    expect(screen.getByText("Borrador")).toBeInTheDocument();
    expect(screen.getByText("$ 125.000,50")).toBeInTheDocument();
  });

  it("una firmada con N° real se muestra como oficial", async () => {
    api.getResoluciones.mockResolvedValue({
      items: [res({ estado: "F", numero_real: 812 })], total: 1, pagina: 1, por_pagina: 20 });
    render(<ResolucionesPage />);
    expect(await screen.findByText("812/2026")).toBeInTheDocument();
    expect(screen.getByText("Oficial")).toBeInTheDocument();
  });

  it("filtra por tipo y estado pidiéndoselo al servidor", async () => {
    const user = userEvent.setup();
    render(<ResolucionesPage />);
    await screen.findByText("45/2026");

    await user.selectOptions(screen.getByLabelText("Tipo"), "DIS");
    await waitFor(() => expect(api.getResoluciones).toHaveBeenLastCalledWith(
      expect.objectContaining({ tipo: "DIS", pagina: 1 })));

    await user.selectOptions(screen.getByLabelText("Estado"), "ANULADA");
    await waitFor(() => expect(api.getResoluciones).toHaveBeenLastCalledWith(
      expect.objectContaining({ estado: "ANULADA" })));
  });

  it("al elegir un modelo ofrece su plantilla como cuerpo inicial", async () => {
    const user = userEvent.setup();
    render(<ResolucionesPage />);
    await screen.findByText("45/2026");

    await user.click(screen.getByRole("button", { name: /Nueva/ }));
    await user.selectOptions(screen.getByLabelText("Modelo a utilizar"), "3");

    expect(screen.getByRole("textbox", { name: "Texto del instrumento" }).innerHTML)
      .toContain("VISTO");
  });

  it("firmar y cargar el N° oficial usan los endpoints propios", async () => {
    const user = userEvent.setup();
    api.getResolucion.mockResolvedValue(detalle());
    api.firmarResolucion.mockResolvedValue(detalle({ estado: "F" }));
    api.cargarNumeroReal.mockResolvedValue(detalle({ estado: "F", numero_real: 812 }));
    render(<ResolucionesPage />);

    await user.click(await screen.findByText("45/2026"));
    await user.click(await screen.findByRole("button", { name: /Firmar/ }));
    expect(api.firmarResolucion).toHaveBeenCalledWith(1);

    await user.click(await screen.findByRole("button", { name: /Cargar N° oficial/ }));
    expect(api.cargarNumeroReal).toHaveBeenCalledWith(1, null);
  });

  it("un instrumento ya emitido no ofrece editarse", async () => {
    const user = userEvent.setup();
    api.getResolucion.mockResolvedValue(detalle({ estado: "F", numero_real: 812 }));
    render(<ResolucionesPage />);

    await user.click(await screen.findByText("45/2026"));
    await screen.findByRole("heading", { name: /N° 45\/2026/ });
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
  });

  it("sin permiso de escritura no aparece el alta", async () => {
    sesion(["resoluciones:read"]);
    render(<ResolucionesPage />);
    await screen.findByText("45/2026");
    expect(screen.queryByRole("button", { name: /Nueva/ })).not.toBeInTheDocument();
  });

  it("muestra el motivo cuando el backend rechaza la acción", async () => {
    const user = userEvent.setup();
    api.getResolucion.mockResolvedValue(detalle());
    api.firmarResolucion.mockRejectedValue(
      { response: { data: { detail: "La resolución está anulada." } } });
    render(<ResolucionesPage />);

    await user.click(await screen.findByText("45/2026"));
    await user.click(await screen.findByRole("button", { name: /Firmar/ }));
    expect(await screen.findByText("La resolución está anulada.")).toBeInTheDocument();
  });
});
