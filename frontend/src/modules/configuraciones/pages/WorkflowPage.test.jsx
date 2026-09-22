import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkflowPage from "./WorkflowPage";
import * as api from "../../../api/configuraciones";

vi.mock("../../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarWorkflow: vi.fn(), editarRegla: vi.fn(), agregarNivel: vi.fn(), editarNivel: vi.fn(),
  borrarNivel: vi.fn(), agregarOverride: vi.fn(), borrarOverride: vi.fn(),
}));

const nivel = (id, orden, nombre, rol = "APROBAR", usuarios = []) =>
  ({ id, orden, nombre, rol, cuatroOjos: true, usuarios });
const LINEA = { id: 1, modulo: "creditos", objeto: "LINEA", nombre: "Publicación de línea de crédito",
  descripcion: "Aprobar/publicar una versión", activo: false, niveles: [nivel(11, 1, "Aprobación")] };
const DESEMBOLSO = { id: 3, modulo: "creditos", objeto: "DESEMBOLSO", nombre: "Otorgamiento / desembolso", descripcion: "",
  activo: true, niveles: [nivel(31, 1, "Analista", "APROBAR", [{ id: 5, username: "pz.juan", modo: "EXCLUIR" }]),
                          nivel(32, 2, "Gerencia", "SUPERVISAR")] };
const respuesta = (puedeEditar = true) => ({ reglas: [LINEA, DESEMBOLSO], roles: ["APROBAR", "SUPERVISAR"], puedeEditar });

beforeEach(() => {
  vi.clearAllMocks();
  api.listarWorkflow.mockResolvedValue(respuesta());
  for (const f of ["editarRegla", "agregarNivel", "editarNivel", "borrarNivel", "agregarOverride", "borrarOverride"]) {
    api[f].mockResolvedValue({});
  }
});

const tarjeta = async (nombre) => (await screen.findByRole("heading", { name: nombre })).closest("div.rounded-xl");

describe("Workflow de aprobaciones", () => {
  it("agrupa por módulo y muestra niveles, roles y excepciones", async () => {
    render(<WorkflowPage />);
    expect(await screen.findByRole("heading", { name: "Créditos" })).toBeInTheDocument();
    const niveles = screen.getByRole("list", { name: /Niveles de Otorgamiento/ });
    expect(within(niveles).getAllByRole("listitem")).toHaveLength(2);
    expect(within(niveles).getByText(/Supervisor/)).toBeInTheDocument();
    expect(within(niveles).getByText(/pz.juan/)).toBeInTheDocument();
  });

  it("activar una regla se confirma y avisa cuántos niveles exige", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    await u.click(within(await tarjeta("Publicación de línea de crédito")).getByRole("button", { name: "Activar" }));
    const conf = screen.getByRole("dialog", { name: "Activar la regla" });
    expect(within(conf).getByText(/1 nivel\(es\)/)).toBeInTheDocument();
    await u.click(within(conf).getByRole("button", { name: "Activar" }));
    await waitFor(() => expect(api.editarRegla).toHaveBeenCalledWith(1, { activo: true }));
    expect(api.listarWorkflow).toHaveBeenCalledTimes(2);
  });

  it("desactivar advierte que se pierde el cuatro-ojos", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    await u.click(within(await tarjeta("Otorgamiento / desembolso")).getByRole("button", { name: "Desactivar" }));
    const conf = screen.getByRole("dialog", { name: "Desactivar la regla" });
    expect(within(conf).getByText(/sin cuatro-ojos/)).toBeInTheDocument();
    await u.click(within(conf).getByRole("button", { name: "Desactivar" }));
    await waitFor(() => expect(api.editarRegla).toHaveBeenCalledWith(3, { activo: false }));
  });

  it("agrega un nivel de supervisión", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    await u.click(within(await tarjeta("Publicación de línea de crédito")).getByRole("button", { name: /Agregar nivel/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo nivel" });
    await u.type(within(modal).getByLabelText("Nombre del nivel"), "Gerencia");
    await u.selectOptions(within(modal).getByLabelText("Aprueba"), "SUPERVISAR");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.agregarNivel).toHaveBeenCalledWith(1, { nombre: "Gerencia", rol: "SUPERVISAR", cuatroOjos: true }));
  });

  it("edita un nivel y muestra el error de la API en el modal", async () => {
    api.editarNivel.mockRejectedValue({ response: { data: { detail: "Rol inválido" } } });
    const u = userEvent.setup();
    render(<WorkflowPage />);
    const item = within(await tarjeta("Otorgamiento / desembolso")).getByText("Gerencia").closest("li");
    await u.click(within(item).getByRole("button", { name: "Editar" }));
    const modal = screen.getByRole("dialog", { name: "Editar nivel 2" });
    await u.click(within(modal).getByLabelText(/Cuatro-ojos/));
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.editarNivel).toHaveBeenCalledWith(32, { nombre: "Gerencia", rol: "SUPERVISAR", cuatroOjos: false }));
    expect(await within(modal).findByText("Rol inválido")).toBeInTheDocument();
  });

  it("quitar un nivel se confirma; con un solo nivel no se ofrece", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    expect(within(await tarjeta("Publicación de línea de crédito")).queryByRole("button", { name: "Quitar" })).toBeNull();
    const item = within(await tarjeta("Otorgamiento / desembolso")).getByText("Gerencia").closest("li");
    await u.click(within(item).getByRole("button", { name: "Quitar" }));
    await u.click(within(screen.getByRole("dialog", { name: "Quitar nivel" })).getByRole("button", { name: "Quitar" }));
    await waitFor(() => expect(api.borrarNivel).toHaveBeenCalledWith(32));
  });

  it("agrega y quita excepciones por usuario", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    const item = within(await tarjeta("Publicación de línea de crédito")).getByText("Aprobación").closest("li");
    await u.click(within(item).getByRole("button", { name: "Excepción" }));
    const modal = screen.getByRole("dialog", { name: /Excepción en/ });
    await u.type(within(modal).getByLabelText(/Usuario/), "pz.gerente");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.agregarOverride).toHaveBeenCalledWith(11, { username: "pz.gerente", modo: "INCLUIR" }));
    await u.click(screen.getByRole("button", { name: "Quitar pz.juan" }));
    await waitFor(() => expect(api.borrarOverride).toHaveBeenCalledWith(5));
  });

  it("sin permiso de escritura es sólo lectura", async () => {
    api.listarWorkflow.mockResolvedValue(respuesta(false));
    render(<WorkflowPage />);
    expect(await screen.findByText(/requiere el permiso configuraciones:workflow:write/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Activar|Desactivar|Agregar nivel|Editar|Excepción/ })).toBeNull();
  });
});
