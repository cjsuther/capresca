import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// LimitesPage importa getMyLimit / updateLimit, que HOY no existen en src/api/cajeros.js
// (ver src/api/cajeros.test.js). Se mockea el módulo entero.
vi.mock("../../../api/cajeros", () => ({
  getMyLimit: vi.fn(),
  updateLimit: vi.fn(),
}));

import { getMyLimit, updateLimit } from "../../../api/cajeros";
import LimitesPage from "./LimitesPage";
import { useAuthStore } from "../../../context/authStore";

const LIMITE = { daily_limit: "100000.00", per_transaction_limit: "25000.00", currency: "ARS" };

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: { id: 42, username: "ana" },
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

describe("LimitesPage", () => {
  beforeEach(() => {
    vi.mocked(getMyLimit).mockReset().mockResolvedValue(LIMITE);
    vi.mocked(updateLimit).mockReset().mockResolvedValue(LIMITE);
    sesion(["limits:write"]);
  });

  it("muestra Cargando... mientras no llegan los límites", () => {
    getMyLimit.mockReturnValue(new Promise(() => {}));
    render(<LimitesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.queryByText("Mis Límites Operativos")).not.toBeInTheDocument();
  });

  it("muestra los límites diario, por operación y la moneda", async () => {
    render(<LimitesPage />);
    expect(await screen.findByText("Mis Límites Operativos")).toBeInTheDocument();
    expect(screen.getByText("100000.00 ARS")).toBeInTheDocument();
    expect(screen.getByText("25000.00 ARS")).toBeInTheDocument();
    expect(screen.getByText("Límite diario")).toBeInTheDocument();
    expect(screen.getByText("Límite por operación")).toBeInTheDocument();
  });

  it("sin permiso limits:write no aparece el botón Editar", async () => {
    sesion([]);
    render(<LimitesPage />);
    await screen.findByText("Mis Límites Operativos");
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
  });

  it("con limits:write se puede abrir y cancelar la edición", async () => {
    const user = userEvent.setup();
    render(<LimitesPage />);
    await user.click(await screen.findByRole("button", { name: "Editar" }));

    expect(screen.getByRole("button", { name: "Guardar" })).toBeInTheDocument();
    // el formulario viene precargado con los valores actuales
    expect(screen.getAllByRole("spinbutton")[0]).toHaveValue(100000);
    expect(screen.getAllByRole("spinbutton")[1]).toHaveValue(25000);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
    expect(screen.getByText("100000.00 ARS")).toBeInTheDocument();
  });

  it("guarda los nuevos límites contra el id del usuario logueado", async () => {
    updateLimit.mockResolvedValue({ daily_limit: "200000.00", per_transaction_limit: "30000.00", currency: "USD" });
    const user = userEvent.setup();
    render(<LimitesPage />);
    await user.click(await screen.findByRole("button", { name: "Editar" }));

    const [diario, porOperacion] = screen.getAllByRole("spinbutton");
    await user.clear(diario);
    await user.type(diario, "200000");
    await user.clear(porOperacion);
    await user.type(porOperacion, "30000");
    await user.selectOptions(screen.getByRole("combobox"), "USD");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(updateLimit).toHaveBeenCalledWith(42, {
      daily_limit: "200000",
      per_transaction_limit: "30000",
      currency: "USD",
    });

    // vuelve a la vista de lectura con los datos que devolvió la API
    await waitFor(() => expect(screen.getByText("200000.00 USD")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
  });
});
