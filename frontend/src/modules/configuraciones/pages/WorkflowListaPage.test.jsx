import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkflowPage from "./WorkflowListaPage";
import * as api from "../../../api/configuraciones";

vi.mock("../../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarWorkflow: vi.fn(),
}));

const nivel = (id, orden, nombre, rol = "APROBAR", usuarios = []) =>
  ({ id, orden, nombre, rol, cuatroOjos: true, usuarios });
const LINEA = { id: 1, modulo: "creditos", objeto: "LINEA", nombre: "Publicación de línea de crédito",
  descripcion: "Aprobar/publicar una versión", activo: false, versionPublicada: 1, niveles: [nivel(11, 1, "Aprobación")] };
const DESEMBOLSO = { id: 3, modulo: "creditos", objeto: "DESEMBOLSO", nombre: "Otorgamiento / desembolso", descripcion: "",
  activo: true, versionPublicada: 4,
  niveles: [nivel(31, 1, "Analista", "APROBAR", [{ id: 5, username: "pz.juan", modo: "EXCLUIR" }]),
            nivel(32, 2, "Gerencia", "SUPERVISAR")] };

beforeEach(() => {
  vi.clearAllMocks();
  api.listarWorkflow.mockResolvedValue({ reglas: [LINEA, DESEMBOLSO], roles: ["APROBAR", "SUPERVISAR"], puedeEditar: false });
});

describe("Workflow de aprobaciones · vista lista", () => {
  it("agrupa por módulo y muestra niveles, roles, excepciones y la versión vigente", async () => {
    render(<WorkflowPage />);
    expect(await screen.findByRole("heading", { name: "Créditos" })).toBeInTheDocument();
    const niveles = screen.getByRole("list", { name: /Niveles de Otorgamiento/ });
    expect(within(niveles).getAllByRole("listitem")).toHaveLength(2);
    expect(within(niveles).getByText(/Supervisor/)).toBeInTheDocument();
    expect(within(niveles).getByText(/pz.juan/)).toBeInTheDocument();
    expect(screen.getByText("Versión 4")).toBeInTheDocument();
    expect(screen.getByText("Activa")).toBeInTheDocument();
  });

  it("es de sólo lectura y explica dónde se edita", async () => {
    render(<WorkflowPage />);
    expect(await screen.findByText(/Vista de sólo lectura/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("muestra el error de la API", async () => {
    api.listarWorkflow.mockRejectedValue({ response: { data: { detail: "Configuraciones no responde" } } });
    render(<WorkflowPage />);
    expect(await screen.findByText("Configuraciones no responde")).toBeInTheDocument();
  });
});
