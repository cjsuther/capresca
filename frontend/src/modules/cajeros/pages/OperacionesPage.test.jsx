import { render, screen, waitForElementToBeRemoved } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// OperacionesPage importa getOperations, que HOY no existe en src/api/cajeros.js (ver cajeros.test.js).
// Mockeamos el módulo completo para poder ejercitar la pantalla.
vi.mock("../../../api/cajeros", () => ({
  getOperations: vi.fn(),
}));

import { getOperations } from "../../../api/cajeros";
import OperacionesPage from "./OperacionesPage";

const OPERACIONES = [
  { id: 1, request_id: 55, amount: "1500.00", executed_by_user_id: 3, executed_at: "2026-03-01T10:00:00Z" },
  { id: 2, request_id: 56, amount: "2500.50", executed_by_user_id: 4, executed_at: "2026-03-02T11:30:00Z" },
];

describe("OperacionesPage", () => {
  beforeEach(() => {
    getOperations.mockReset();
  });

  it("muestra el estado de carga mientras espera al backend", () => {
    getOperations.mockReturnValue(new Promise(() => {}));
    render(<OperacionesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.getByText("Historial de Operaciones")).toBeInTheDocument();
  });

  it("avisa cuando no hay operaciones registradas", async () => {
    getOperations.mockResolvedValue([]);
    render(<OperacionesPage />);
    expect(await screen.findByText("Sin operaciones registradas")).toBeInTheDocument();
    expect(getOperations).toHaveBeenCalledTimes(1);
  });

  it("lista las operaciones con solicitud, monto y ejecutor", async () => {
    getOperations.mockResolvedValue(OPERACIONES);
    render(<OperacionesPage />);
    await waitForElementToBeRemoved(() => screen.queryByText("Cargando..."));

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("Solicitud #55")).toBeInTheDocument();
    expect(screen.getByText("1500.00")).toBeInTheDocument();
    expect(screen.getByText("Usuario #3")).toBeInTheDocument();
    expect(screen.getByText("Solicitud #56")).toBeInTheDocument();
    expect(screen.getByText("2500.50")).toBeInTheDocument();
    // dos filas de datos + la de encabezados
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.queryByText("Sin operaciones registradas")).not.toBeInTheDocument();
  });

  it("renderiza todas las columnas del historial", () => {
    getOperations.mockReturnValue(new Promise(() => {}));
    render(<OperacionesPage />);
    ["#", "Solicitud", "Monto", "Ejecutado por", "Fecha"].forEach((col) =>
      expect(screen.getByRole("columnheader", { name: col })).toBeInTheDocument()
    );
  });
});
