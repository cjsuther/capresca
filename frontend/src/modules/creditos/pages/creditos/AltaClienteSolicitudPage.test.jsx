import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AltaClienteSolicitudPage from "./AltaClienteSolicitudPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { ppSolicitud: vi.fn(), ppSolicitudDocs: vi.fn(), ppSolicitudPromover: vi.fn() },
}));

const EXPRESS_PORTAL = {
  id: "s2", numero: "SOL-2", estado: "EN_EVALUACION", solicitanteTipo: "NO_REGISTRADO", clienteNombre: "PEREZ, JUAN CARLOS",
  clienteDatos: { apellido_nombre: "PEREZ, JUAN CARLOS", dni: "30123456", cuil: "", email: "juan@example.com" },
  datosAdicionales: { portal_email: "juan@example.com" },
};

const montar = () => render(
  <MemoryRouter initialEntries={["/modules/creditos/solicitudes-credito/s2/alta-cliente"]}>
    <Routes>
      <Route path="/modules/creditos/solicitudes-credito/:id/alta-cliente" element={<AltaClienteSolicitudPage />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  creditos.ppSolicitud.mockResolvedValue(EXPRESS_PORTAL);
  creditos.ppSolicitudDocs.mockResolvedValue({ items: [
    { id: "doc-1", tipo: "DNI_FRENTE", nombre: "dni.png", tamano: 1000 },
    { id: "doc-2", tipo: "RECIBO", nombre: "recibo.pdf", tamano: 1000 },
  ] });
});

describe("Alta de cliente desde la solicitud (otra solapa)", () => {
  it("precarga lo que declaró el solicitante, crea el cliente y avisa a la solapa de Solicitudes", async () => {
    creditos.ppSolicitudPromover.mockResolvedValue({
      solicitud: { ...EXPRESS_PORTAL, solicitanteTipo: "REGISTRADO", clienteId: 4321 }, clienteId: 4321, yaExistia: false,
      documentos: { guardados: 2, repetidos: 0 },
    });
    const recibido = new Promise((ok) => {
      const canal = new BroadcastChannel("creditos-solicitudes");
      canal.onmessage = ({ data }) => { canal.close(); ok(data); };
    });
    const u = userEvent.setup();
    montar();
    expect(await screen.findByLabelText("Apellido")).toHaveValue("PEREZ");
    expect(screen.getByLabelText("Nombres")).toHaveValue("JUAN CARLOS");
    expect(screen.getByLabelText("DNI")).toHaveValue("30123456");
    expect(screen.getByLabelText("Email")).toHaveValue("juan@example.com");
    expect(await screen.findByLabelText(/Guardar los 2 documento/)).toBeChecked();

    await u.type(screen.getByLabelText("CUIL"), "20-30123456-9");
    await u.type(screen.getByLabelText("Localidad"), "Catamarca");
    await u.click(screen.getByRole("button", { name: "Crear cliente" }));

    await waitFor(() => expect(creditos.ppSolicitudPromover).toHaveBeenCalledWith("s2", expect.objectContaining({
      apellido_nombre: "PEREZ, JUAN CARLOS", dni: "30123456", cuil: "20301234569", localidad: "Catamarca",
      email: "juan@example.com", copiar_documentos: true })));
    expect(await screen.findByText(/Cliente creado en el módulo Clientes.*2 documento\(s\) guardado/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver ficha del cliente" })).toHaveAttribute("href", "/modules/clientes/4321");
    const msg = await recibido;
    expect(msg).toMatchObject({ tipo: "cliente-vinculado", clienteId: 4321, solicitud: { id: "s2", solicitanteTipo: "REGISTRADO" } });
  });

  it("valida el CUIL antes de enviar", async () => {
    const u = userEvent.setup();
    montar();
    await u.type(await screen.findByLabelText("CUIL"), "123");
    await u.click(screen.getByRole("button", { name: "Crear cliente" }));
    expect(screen.getByText("El CUIL debe tener 11 dígitos.")).toBeInTheDocument();
    expect(creditos.ppSolicitudPromover).not.toHaveBeenCalled();
  });

  it("si la copia de documentos falla, el cliente queda creado y lo avisa", async () => {
    creditos.ppSolicitudPromover.mockResolvedValue({
      solicitud: { ...EXPRESS_PORTAL, solicitanteTipo: "REGISTRADO", clienteId: 4321 }, clienteId: 4321, yaExistia: false,
      documentos: { guardados: 0, repetidos: 0, error: "No se pudieron copiar los documentos al cliente: timeout" },
    });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: "Crear cliente" }));
    expect(await screen.findByText(/No se pudieron copiar.*Guardar en el cliente/)).toBeInTheDocument();
  });

  it("si la solicitud ya tiene cliente, no ofrece el alta", async () => {
    creditos.ppSolicitud.mockResolvedValue({ ...EXPRESS_PORTAL, solicitanteTipo: "REGISTRADO", clienteId: 4321 });
    montar();
    expect(await screen.findByText(/ya tiene un cliente del padrón vinculado/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Crear cliente" })).toBeNull();
  });
});
