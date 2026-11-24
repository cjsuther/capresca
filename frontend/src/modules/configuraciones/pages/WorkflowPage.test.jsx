import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkflowPage from "./WorkflowPage";
import * as api from "../../../api/configuraciones";

vi.mock("../workflow/WorkflowEditorPage", () => ({ default: () => <p>editor gráfico</p> }));
vi.mock("../../../api/configuraciones", async (original) => ({ ...(await original()), listarWorkflow: vi.fn() }));

beforeEach(() => {
  api.listarWorkflow.mockResolvedValue({ reglas: [{ id: 1, modulo: "tesoreria", objeto: "LOTE_PAGO", nombre: "Lote de pagos",
    descripcion: "", activo: true, versionPublicada: 2, niveles: [] }], roles: [], puedeEditar: false });
});

describe("Workflow de aprobaciones", () => {
  it("abre en el diagrama y deja pasar a la vista lista", async () => {
    const u = userEvent.setup();
    render(<WorkflowPage />);
    expect(await screen.findByText("editor gráfico")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Diagrama" })).toHaveAttribute("aria-selected", "true");
    await u.click(screen.getByRole("tab", { name: "Vista lista" }));
    expect(await screen.findByText("Lote de pagos")).toBeInTheDocument();
    expect(screen.getByText(/Los cambios se hacen en el Diagrama/)).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Workflow de aprobaciones" })).toHaveLength(1);
  });
});
