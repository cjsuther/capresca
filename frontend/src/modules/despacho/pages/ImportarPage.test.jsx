import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ImportarPage from "./ImportarPage";
import * as api from "../../../api/despacho";

vi.mock("../../../api/despacho");

const imp = (extra = {}) => ({
  id: 1, archivo: "despacho.zip", tamano: 2097152, estado: "TERMINADA", modelos: 120,
  resoluciones: 8400, beneficiarios: 15300, omitidas: 12, reparadas: 0, mensaje: "",
  creadoEn: "2026-09-24T10:00:00Z", terminadoEn: null, ...extra,
});

beforeEach(() => {
  vi.clearAllMocks();
  api.getImportaciones.mockResolvedValue({ items: [] });
});

describe("importar el despacho anterior", () => {
  it("muestra lo que trajo cada importación", async () => {
    api.getImportaciones.mockResolvedValue({ items: [imp()] });
    render(<ImportarPage />);

    expect(await screen.findByText("despacho.zip")).toBeInTheDocument();
    expect(screen.getByText("2.0 MB")).toBeInTheDocument();
    expect(screen.getByText("Terminada")).toBeInTheDocument();
    expect(screen.getByText("8.400")).toBeInTheDocument();    // resoluciones
    expect(screen.getByText("15.300")).toBeInTheDocument();   // beneficiarios
  });

  it("muestra los textos que reparó de una importación anterior", async () => {
    api.getImportaciones.mockResolvedValue({
      items: [imp({ modelos: 0, resoluciones: 0, beneficiarios: 0, reparadas: 53257 })] });
    render(<ImportarPage />);
    expect(await screen.findByText("53.257")).toBeInTheDocument();
  });

  it("avisa cuando todavía no se importó nada", async () => {
    render(<ImportarPage />);
    expect(await screen.findByText(/Todavía no se importó nada/)).toBeInTheDocument();
  });

  it("sube el backup y lo agrega a la lista", async () => {
    api.subirDespacho.mockResolvedValue(imp({ id: 2, estado: "PENDIENTE", modelos: 0,
                                              resoluciones: 0, beneficiarios: 0, omitidas: 0 }));
    render(<ImportarPage />);
    await screen.findByText(/Todavía no se importó nada/);

    const archivo = new File(["x"], "despacho.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("Backup del despacho"), { target: { files: [archivo] } });

    await waitFor(() => expect(api.subirDespacho).toHaveBeenCalledWith(archivo, expect.any(Function)));
    expect(await screen.findByText("despacho.zip")).toBeInTheDocument();
  });

  it("si el servidor lo rechaza por tamaño lo explica (nginx no manda detalle)", async () => {
    api.subirDespacho.mockRejectedValue({ response: { status: 413, data: "<html>413</html>" } });
    render(<ImportarPage />);
    await screen.findByText(/Todavía no se importó nada/);

    const archivo = new File(["x"], "despacho.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("Backup del despacho"), { target: { files: [archivo] } });
    expect(await screen.findByText(/rechazó el archivo por tamaño/)).toBeInTheDocument();
  });

  it("si la subida se corta sin respuesta lo dice, en vez de un error genérico", async () => {
    api.subirDespacho.mockRejectedValue({ code: "ECONNABORTED", message: "timeout" });
    render(<ImportarPage />);
    await screen.findByText(/Todavía no se importó nada/);

    const archivo = new File(["x"], "despacho.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("Backup del despacho"), { target: { files: [archivo] } });
    expect(await screen.findByText(/Se cortó la subida antes de terminar/)).toBeInTheDocument();
  });

  it("mientras una corre no deja subir otra y consulta el avance", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.getImportaciones.mockResolvedValue({ items: [imp({ estado: "PROCESANDO", resoluciones: 1200 })] });
    api.getImportacion.mockResolvedValue(imp({ estado: "PROCESANDO", resoluciones: 3500 }));
    render(<ImportarPage />);

    await screen.findByText("Importando");
    expect(screen.getByLabelText("Backup del despacho")).toBeDisabled();
    await vi.advanceTimersByTimeAsync(3100);
    expect(await screen.findByText("3.500")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("muestra el error de una importación que falló", async () => {
    api.getImportaciones.mockResolvedValue({
      items: [imp({ estado: "ERROR", mensaje: "El ZIP no trae resoluciones.dbf" })] });
    render(<ImportarPage />);
    expect(await screen.findByText("El ZIP no trae resoluciones.dbf")).toBeInTheDocument();
  });
});
