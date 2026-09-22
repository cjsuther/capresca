import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VisorDocumento } from "./VisorDocumento";

const DOCS = [
  { id: "d1", tipo: "DNI_FRENTE", nombre: "Captura 11.46.03 a. m.png", tamano: 900000 },
  { id: "d2", tipo: "RECIBO", nombre: "recibo.pdf", tamano: 180000 },
];
const ETIQUETAS = { DNI_FRENTE: "DNI (frente)", RECIBO: "Recibo de sueldo" };
const blob = (tipo) => new Blob(["x"], { type: tipo });

beforeEach(() => {
  let n = 0;
  globalThis.URL.createObjectURL = vi.fn(() => `blob:doc-${++n}`);
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("VisorDocumento", () => {
  it("muestra la imagen dentro de la página, con su nombre y botón de descarga", async () => {
    const cargar = vi.fn().mockResolvedValue(blob("image/png"));
    render(<VisorDocumento docs={DOCS} cargar={cargar} etiquetas={ETIQUETAS} onClose={vi.fn()} />);
    const img = await screen.findByRole("img", { name: /DNI \(frente\)/ });
    expect(img).toHaveAttribute("src", "blob:doc-1");
    expect(cargar).toHaveBeenCalledWith(DOCS[0]);
    const descargar = screen.getByRole("link", { name: "Descargar" });
    expect(descargar).toHaveAttribute("download", DOCS[0].nombre);
  });

  it("un PDF se muestra embebido", async () => {
    const cargar = vi.fn().mockResolvedValue(blob("application/pdf"));
    render(<VisorDocumento docs={DOCS} inicial={1} cargar={cargar} etiquetas={ETIQUETAS} onClose={vi.fn()} />);
    expect(await screen.findByTitle("recibo.pdf")).toHaveAttribute("src", "blob:doc-1");
  });

  it("se pasa de un documento al otro y libera el anterior", async () => {
    const cargar = vi.fn((d) => Promise.resolve(blob(d.id === "d1" ? "image/png" : "application/pdf")));
    const u = userEvent.setup();
    render(<VisorDocumento docs={DOCS} cargar={cargar} etiquetas={ETIQUETAS} onClose={vi.fn()} />);
    await screen.findByRole("img");
    await u.click(within(screen.getByRole("tablist")).getByRole("tab", { name: "Recibo de sueldo" }));
    expect(await screen.findByTitle("recibo.pdf")).toBeInTheDocument();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:doc-1");
  });

  it("si no se puede abrir lo informa", async () => {
    const cargar = vi.fn().mockRejectedValue(new Error("No se pudo abrir el archivo"));
    render(<VisorDocumento docs={DOCS} cargar={cargar} etiquetas={ETIQUETAS} onClose={vi.fn()} />);
    expect(await screen.findByText("No se pudo abrir el archivo")).toBeInTheDocument();
  });

  it("un formato sin vista previa ofrece descargarlo", async () => {
    const cargar = vi.fn().mockResolvedValue(blob("application/zip"));
    render(<VisorDocumento docs={DOCS} cargar={cargar} etiquetas={ETIQUETAS} onClose={vi.fn()} />);
    expect(await screen.findByText(/no tiene vista previa/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "Descargar" })).toBeInTheDocument());
  });
});
