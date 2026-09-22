import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentosCliente } from "./DocumentosCliente";
import { useAuthStore } from "../../../context/authStore";
import { getDocumentos, subirDocumento, getDocumentoArchivo, borrarDocumento } from "../../../api/clientes";

vi.mock("../../../api/clientes", () => ({
  getDocumentos: vi.fn(), subirDocumento: vi.fn(), getDocumentoArchivo: vi.fn(), borrarDocumento: vi.fn(),
}));

const DNI = { id: 1, tipo: "DNI_FRENTE", nombre: "dni frente.png", content_type: "image/png", tamano: 900000,
              origen: "Solicitud SOL-2026-00001", created_at: "2026-09-22T12:00:00Z" };
const RECIBO = { id: 2, tipo: "RECIBO", nombre: "recibo.pdf", content_type: "application/pdf", tamano: 180000,
                 origen: "Carga manual", created_at: "2026-09-22T13:00:00Z" };

const permisos = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "ana" }, permissions: { modules: ["clientes"], actions: { clientes: acciones } },
});
const archivo = (nombre, tipo, tam = 1000) => {
  const f = new File(["x"], nombre, { type: tipo });
  Object.defineProperty(f, "size", { value: tam });
  return f;
};

beforeEach(() => {
  vi.clearAllMocks();
  permisos(["clients:read", "clients:write"]);
  getDocumentos.mockResolvedValue({ items: [DNI, RECIBO] });
  subirDocumento.mockResolvedValue({});
  borrarDocumento.mockResolvedValue({});
  getDocumentoArchivo.mockResolvedValue(new Blob(["x"], { type: "image/png" }));
  globalThis.URL.createObjectURL = vi.fn(() => "blob:doc");
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("Documentos del cliente", () => {
  it("lista tipo, nombre, tamaño y de dónde vino cada documento", async () => {
    render(<DocumentosCliente clientId={7} />);
    const lista = await screen.findByRole("list", { name: "Documentos del cliente" });
    expect(within(lista).getByText("DNI (frente)")).toBeInTheDocument();
    expect(within(lista).getByText(/Solicitud SOL-2026-00001/)).toBeInTheDocument();
    expect(within(lista).getByText("879 KB")).toBeInTheDocument();
    expect(getDocumentos).toHaveBeenCalledWith(7);
  });

  it("se ven dentro de la página", async () => {
    const u = userEvent.setup();
    render(<DocumentosCliente clientId={7} />);
    await u.click(await screen.findByRole("button", { name: "dni frente.png" }));
    const visor = await screen.findByRole("dialog", { name: "DNI (frente)" });
    expect(await within(visor).findByRole("img")).toHaveAttribute("src", "blob:doc");
    expect(getDocumentoArchivo).toHaveBeenCalledWith(7, 1);
  });

  it("adjunta con el tipo elegido y recarga", async () => {
    const u = userEvent.setup();
    render(<DocumentosCliente clientId={7} />);
    await screen.findByText("dni frente.png");
    await u.selectOptions(screen.getByLabelText("Tipo de documento"), "RECIBO");
    const f = archivo("recibo-agosto.pdf", "application/pdf");
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [f] } });
    await waitFor(() => expect(subirDocumento).toHaveBeenCalledWith(7, f, "RECIBO"));
    await waitFor(() => expect(getDocumentos).toHaveBeenCalledTimes(2));
  });

  it("valida formato y tamaño antes de subir", async () => {
    render(<DocumentosCliente clientId={7} />);
    await screen.findByText("dni frente.png");
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [archivo("x.docx", "application/msword")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Formato no permitido");
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [archivo("x.pdf", "application/pdf", 11 * 1024 * 1024)] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("supera los 10 MB");
    expect(subirDocumento).not.toHaveBeenCalled();
  });

  it("muestra el motivo si el backend rechaza el archivo", async () => {
    subirDocumento.mockRejectedValue({ response: { data: { detail: "Ese archivo ya está cargado en el cliente (dni frente.png)." } } });
    render(<DocumentosCliente clientId={7} />);
    await screen.findByText("dni frente.png");
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [archivo("otra.png", "image/png")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("ya está cargado");
  });

  it("borrar pide confirmación", async () => {
    const u = userEvent.setup();
    render(<DocumentosCliente clientId={7} />);
    await u.click(await screen.findByRole("button", { name: "Borrar recibo.pdf" }));
    await u.click(within(screen.getByRole("dialog", { name: "Borrar documento" })).getByRole("button", { name: "Borrar" }));
    await waitFor(() => expect(borrarDocumento).toHaveBeenCalledWith(7, 2));
  });

  it("sin permiso de escritura sólo se ven", async () => {
    permisos(["clients:read"]);
    render(<DocumentosCliente clientId={7} />);
    await screen.findByText("dni frente.png");
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /Borrar/ })).toBeNull();
  });

  it("sin documentos lo dice", async () => {
    getDocumentos.mockResolvedValue({ items: [] });
    render(<DocumentosCliente clientId={7} />);
    expect(await screen.findByText("Sin documentos cargados")).toBeInTheDocument();
  });
});
