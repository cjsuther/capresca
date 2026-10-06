import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResolucionesPage from "./ResolucionesPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const SERIES = [{ serie: 1, nombre: "General (créditos y ayudas sociales)" },
                { serie: 4, nombre: "Seguros" }];

const res = (extra = {}) => ({
  id: 1, numero: 45, anio: 2026, tipo: "RES", serie: 1,
  serie_nombre: "General (créditos y ayudas sociales)",
  fecha: "2026-06-10", numero_real: null,
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
    { id: 3, codigo: 103, serie: 1, descripcion: "TRANSFERENCIA", tipo: "RES",
      plantilla: "<p>VISTO…</p>" },
    { id: 9, codigo: 3, serie: 4, descripcion: "SEPELIO", tipo: "RES", plantilla: "<p>Seguro…</p>" },
  ]);
  api.getSeries.mockResolvedValue(SERIES);
  api.getLotesDeResolucion.mockResolvedValue({ lotes: [], total: "0", importe: "125000.50", disponible: "125000.50" });
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

  it("filtra por serie: cada área lleva su propia numeración", async () => {
    const user = userEvent.setup();
    render(<ResolucionesPage />);
    await screen.findByText("45/2026");

    await user.selectOptions(await screen.findByLabelText("Serie"), "4");
    await waitFor(() => expect(api.getResoluciones).toHaveBeenLastCalledWith(
      expect.objectContaining({ serie: "4" })));
  });

  it("el combo de modelos sólo ofrece los de la serie elegida", async () => {
    const user = userEvent.setup();
    render(<ResolucionesPage />);
    await screen.findByText("45/2026");

    await user.click(screen.getByRole("button", { name: /Nueva/ }));
    expect(screen.getByRole("option", { name: /TRANSFERENCIA/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /SEPELIO/ })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Serie del acto"), "4");
    expect(await screen.findByRole("option", { name: /SEPELIO/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /TRANSFERENCIA/ })).not.toBeInTheDocument();
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

    await user.click(await screen.findByRole("button", { name: /Usar el siguiente N° oficial/ }));
    expect(api.cargarNumeroReal).toHaveBeenCalledWith(1, null);
  });

  it("el N° oficial se escribe a mano (sólo dígitos) y la fecha se corrige", async () => {
    const user = userEvent.setup();
    api.getResolucion.mockResolvedValue(detalle({ estado: "F", numero_real: 812, creado_en: "2026-06-01T10:00:00" }));
    api.corregirOficial.mockResolvedValue(detalle({ estado: "F", numero_real: 813, fecha: "2026-06-12" }));
    render(<ResolucionesPage />);

    await user.click(await screen.findByText("45/2026"));
    expect(await screen.findByText("1/6/2026")).toBeInTheDocument();          // fecha de creación
    const nro = screen.getByLabelText("N° oficial");
    await user.clear(nro);
    await user.type(nro, "8a13");
    expect(nro).toHaveValue("813");
    const f = screen.getByLabelText("Fecha de la resolución");
    await user.clear(f);
    await user.type(f, "2026-06-12");
    await user.click(screen.getByRole("button", { name: "Guardar N° oficial y fecha" }));
    await waitFor(() => expect(api.corregirOficial).toHaveBeenCalledWith(1, { numero_real: 813, fecha: "2026-06-12" }));
  });

  it("muestra los lotes de créditos que otorga y lo disponible", async () => {
    const user = userEvent.setup();
    api.getResolucion.mockResolvedValue(detalle());
    api.getLotesDeResolucion.mockResolvedValue({ lotes: [{ codigo: "2026-0001" }, { codigo: "2026-0002" }],
                                                 total: "100000", importe: "125000.50", disponible: "25000.50" });
    render(<ResolucionesPage />);
    await user.click(await screen.findByText("45/2026"));
    expect(await screen.findByText(/Lotes de créditos que otorga \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/2026-0001, 2026-0002/)).toBeInTheDocument();
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
