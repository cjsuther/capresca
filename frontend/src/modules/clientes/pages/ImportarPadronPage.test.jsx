import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ImportarPadronPage from "./ImportarPadronPage";
import * as api from "../../../api/clientes";

vi.mock("../../../api/clientes");

const imp = (extra = {}) => ({
  id: 1, archivo: "maeclientes.zip", tamano: 10519820, estado: "TERMINADA",
  total: 78300, procesados: 78300, creados: 72100, actualizados: 6200, rechazados: 0,
  porcentaje: 100, mensaje: null, creadoEn: "2026-09-24T10:00:00Z", terminadoEn: null, ...extra,
});

beforeEach(() => {
  vi.clearAllMocks();
  api.getImportaciones.mockResolvedValue({ items: [] });
});

describe("importar padrón", () => {
  it("muestra las importaciones con lo que hizo cada una", async () => {
    api.getImportaciones.mockResolvedValue({ items: [imp()] });
    render(<ImportarPadronPage />);

    expect(await screen.findByText("maeclientes.zip")).toBeInTheDocument();
    expect(screen.getByText("10.0 MB")).toBeInTheDocument();
    expect(screen.getByText("Terminada")).toBeInTheDocument();
    expect(screen.getByText("72.100")).toBeInTheDocument();   // clientes nuevos
    expect(screen.getByText("6.200")).toBeInTheDocument();    // actualizados
  });

  it("avisa cuando no hay ninguna todavía", async () => {
    render(<ImportarPadronPage />);
    expect(await screen.findByText(/Todavía no se importó ningún padrón/)).toBeInTheDocument();
  });

  it("sube el archivo y lo agrega a la lista", async () => {
    const creada = imp({ id: 2, estado: "PENDIENTE", total: 0, procesados: 0, creados: 0,
                         actualizados: 0, porcentaje: 0 });
    api.subirPadron.mockResolvedValue(creada);
    render(<ImportarPadronPage />);
    await screen.findByText(/Todavía no se importó/);

    const archivo = new File(["x"], "maeclientes.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("Archivo del padrón"), { target: { files: [archivo] } });

    await waitFor(() => expect(api.subirPadron).toHaveBeenCalledWith(archivo, expect.any(Function)));
    expect(await screen.findByText("maeclientes.zip")).toBeInTheDocument();
  });

  it("mientras importa muestra el avance y lo va actualizando solo", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.getImportaciones.mockResolvedValue({
      items: [imp({ estado: "PROCESANDO", procesados: 20000, creados: 18000, porcentaje: 25.5 })],
    });
    api.getImportacion.mockResolvedValue(
      imp({ estado: "PROCESANDO", procesados: 40000, creados: 36000, porcentaje: 51 }));
    render(<ImportarPadronPage />);

    expect(await screen.findByText(/20\.000 de 78\.300 registros \(25\.5%\)/)).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(3100);
    expect(await screen.findByText(/40\.000 de 78\.300 registros \(51%\)/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("no deja subir otra mientras hay una corriendo", async () => {
    api.getImportaciones.mockResolvedValue({ items: [imp({ estado: "PROCESANDO" })] });
    render(<ImportarPadronPage />);
    expect(await screen.findByText(/Hay una importación en curso/)).toBeInTheDocument();
    expect(screen.getByLabelText("Archivo del padrón")).toBeDisabled();
  });

  it("los rechazados se descargan en CSV", async () => {
    api.getImportaciones.mockResolvedValue({ items: [imp({ rechazados: 12 })] });
    api.descargarRechazos.mockResolvedValue(new Blob(["fila;motivo"]));
    global.URL.createObjectURL = vi.fn(() => "blob:x");
    global.URL.revokeObjectURL = vi.fn();
    render(<ImportarPadronPage />);

    await userEvent.click(await screen.findByRole("button", { name: /12/ }));
    await waitFor(() => expect(api.descargarRechazos).toHaveBeenCalledWith(1));
  });

  it("muestra el motivo cuando una importación falla", async () => {
    api.getImportaciones.mockResolvedValue({
      items: [imp({ estado: "ERROR", mensaje: "El ZIP no contiene ningún archivo .dbf" })],
    });
    render(<ImportarPadronPage />);
    expect(await screen.findByText("El ZIP no contiene ningún archivo .dbf")).toBeInTheDocument();
    expect(screen.getByText("Con error")).toBeInTheDocument();
  });

  it("avisa si la subida es rechazada", async () => {
    api.subirPadron.mockRejectedValue({ response: { data: { detail: "Ya hay una importación en curso." } } });
    render(<ImportarPadronPage />);
    await screen.findByText(/Todavía no se importó/);
    fireEvent.change(screen.getByLabelText("Archivo del padrón"),
                     { target: { files: [new File(["x"], "p.zip")] } });
    expect(await screen.findByText("Ya hay una importación en curso.")).toBeInTheDocument();
  });
});
