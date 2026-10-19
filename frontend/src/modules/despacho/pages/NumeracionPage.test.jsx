import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NumeracionPage from "./NumeracionPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const ANIO = new Date().getFullYear();
const fila = (extra = {}) => ({
  anio: ANIO, serie: 1, nombre: "GENERAL", ultimoNumero: 6, ultimoOficial: 6,
  desdeNumero: null, desdeOficial: null, proximoNumero: 7, proximoOficial: 7, actualizadoPor: null, actualizadoEn: null,
  ...extra,
});

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "resoluciones:firmar"]);
  api.getNumeracion.mockResolvedValue([fila(), fila({ serie: 4, nombre: "SEGUROS", ultimoNumero: null, ultimoOficial: null,
                                                       proximoNumero: 1, proximoOficial: 1 })]);
});

describe("numeración de resoluciones", () => {
  it("muestra por serie el último número y el próximo", async () => {
    render(<NumeracionPage />);
    const general = (await screen.findByText(/1 · GENERAL/)).closest("tr");
    expect(api.getNumeracion).toHaveBeenCalledWith(ANIO);
    expect(general).toHaveTextContent("Va a ser el 7");
  });

  it("fija desde qué número sigue la serie", async () => {
    api.fijarNumeracion.mockResolvedValue(fila({ desdeNumero: 1500, desdeOficial: 870, proximoNumero: 1500, proximoOficial: 870,
                                                 actualizadoPor: "ana", actualizadoEn: "2026-10-08T15:30:00" }));
    const u = userEvent.setup();
    render(<NumeracionPage />);
    const general = (await screen.findByText(/1 · GENERAL/)).closest("tr");
    await u.type(within(general).getByLabelText("Próximo correlativo serie 1"), "1500");
    await u.type(within(general).getByLabelText("Próximo N° oficial serie 1"), "870");
    await u.click(within(general).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.fijarNumeracion).toHaveBeenCalledWith(ANIO, 1, { desde_numero: 1500, desde_oficial: 870 }));
    expect(await screen.findByText(/el próximo correlativo es el 1500 y el próximo N° oficial el 870/)).toBeInTheDocument();
    expect(screen.getByText(/Fijado por ana/)).toBeInTheDocument();
  });

  it("muestra el motivo si el número ya se usó", async () => {
    api.fijarNumeracion.mockRejectedValue({ response: { data: { detail: "Ya se usó el correlativo 6 en 2026 para esta serie: el próximo tiene que ser mayor que 6." } } });
    const u = userEvent.setup();
    render(<NumeracionPage />);
    const general = (await screen.findByText(/1 · GENERAL/)).closest("tr");
    await u.type(within(general).getByLabelText("Próximo correlativo serie 1"), "3");
    await u.click(within(general).getByRole("button", { name: "Guardar" }));
    expect(await within(general).findByText(/tiene que ser mayor que 6/)).toBeInTheDocument();
  });

  it("sin el permiso de firmar no se puede cambiar", async () => {
    sesion(["resoluciones:read"]);
    render(<NumeracionPage />);
    const general = (await screen.findByText(/1 · GENERAL/)).closest("tr");
    expect(within(general).getByLabelText("Próximo correlativo serie 1")).toBeDisabled();
    expect(within(general).queryByRole("button", { name: "Guardar" })).toBeNull();
    expect(screen.getByText(/Sólo quien firma/)).toBeInTheDocument();
  });

  it("cambiar el año recarga la numeración de ese año", async () => {
    const u = userEvent.setup();
    render(<NumeracionPage />);
    await screen.findByText(/1 · GENERAL/);
    await u.selectOptions(screen.getByLabelText("Año"), String(ANIO - 1));
    await waitFor(() => expect(api.getNumeracion).toHaveBeenLastCalledWith(ANIO - 1));
  });
});
