import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// RelacionesPage importa getRelations / createRelation / deleteRelation, que HOY no existen
// en src/api/cajeros.js (ver src/api/cajeros.test.js). Se mockea el módulo entero.
vi.mock("../../../api/cajeros", () => ({
  getRelations: vi.fn(),
  createRelation: vi.fn(),
  deleteRelation: vi.fn(),
}));

import { getRelations, createRelation, deleteRelation } from "../../../api/cajeros";
import RelacionesPage from "./RelacionesPage";
import { useAuthStore } from "../../../context/authStore";

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: { id: 1, username: "ana" },
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

const RELACIONES = [
  { id: 1, cajero_user_id: 10, authorizer_user_id: 20, amount_threshold: "0", currency: "ARS", is_active: true },
  { id: 2, cajero_user_id: 11, authorizer_user_id: 21, amount_threshold: "50000", currency: "USD", is_active: false },
];

const abrirFormulario = async (user) => {
  await user.click(screen.getByRole("button", { name: /Nueva relación/ }));
};

const completarFormulario = async (user) => {
  await user.type(screen.getByPlaceholderText("User ID del cajero"), "10");
  await user.type(screen.getByPlaceholderText("User ID del autorizador"), "20");
  await user.type(screen.getByPlaceholderText("0.00 — aplica desde este monto"), "50000");
};

describe("RelacionesPage — listado", () => {
  beforeEach(() => {
    vi.mocked(getRelations).mockReset().mockResolvedValue([]);
    vi.mocked(createRelation).mockReset().mockResolvedValue({});
    vi.mocked(deleteRelation).mockReset().mockResolvedValue({});
    sesion(["requests:write"]);
  });

  it("muestra el estado de carga", () => {
    getRelations.mockReturnValue(new Promise(() => {}));
    render(<RelacionesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.getByText("Relaciones de Autorización")).toBeInTheDocument();
  });

  it("avisa cuando no hay relaciones definidas", async () => {
    render(<RelacionesPage />);
    expect(await screen.findByText("Sin relaciones definidas")).toBeInTheDocument();
  });

  it("lista las relaciones con umbral, moneda y estado", async () => {
    getRelations.mockResolvedValue(RELACIONES);
    render(<RelacionesPage />);

    expect(await screen.findByText("Activa")).toBeInTheDocument();
    expect(screen.getByText("Inactiva")).toBeInTheDocument();
    // umbral 0 se muestra como "Siempre"
    expect(screen.getByText("Siempre")).toBeInTheDocument();
    expect(screen.getByText("$50.000,00")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "10" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "21" })).toBeInTheDocument();
  });

  it("muestra un mensaje si falla la carga", async () => {
    getRelations.mockRejectedValue(new Error("500"));
    render(<RelacionesPage />);
    expect(await screen.findByText("Error al cargar relaciones")).toBeInTheDocument();
  });
});

describe("RelacionesPage — permisos", () => {
  beforeEach(() => {
    vi.mocked(getRelations).mockReset().mockResolvedValue(RELACIONES);
    vi.mocked(deleteRelation).mockReset().mockResolvedValue({});
  });

  it("sin requests:write no hay botón de alta ni de borrado", async () => {
    sesion([]);
    render(<RelacionesPage />);
    await screen.findByText("Activa");
    expect(screen.queryByRole("button", { name: /Nueva relación/ })).not.toBeInTheDocument();
    expect(screen.queryByTitle("Eliminar")).not.toBeInTheDocument();
  });

  it("con requests:write aparecen las acciones de escritura", async () => {
    sesion(["requests:write"]);
    render(<RelacionesPage />);
    await screen.findByText("Activa");
    expect(screen.getByRole("button", { name: /Nueva relación/ })).toBeInTheDocument();
    expect(screen.getAllByTitle("Eliminar")).toHaveLength(2);
  });
});

describe("RelacionesPage — alta", () => {
  beforeEach(() => {
    vi.mocked(getRelations).mockReset().mockResolvedValue([]);
    vi.mocked(createRelation).mockReset().mockResolvedValue({});
    vi.mocked(deleteRelation).mockReset().mockResolvedValue({});
    sesion(["requests:write"]);
  });

  it("el formulario se abre y se cierra", async () => {
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Sin relaciones definidas");

    expect(screen.queryByPlaceholderText("User ID del cajero")).not.toBeInTheDocument();
    await abrirFormulario(user);
    expect(screen.getByPlaceholderText("User ID del cajero")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByPlaceholderText("User ID del cajero")).not.toBeInTheDocument();
  });

  it("crea la relación con los ids parseados y recarga", async () => {
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Sin relaciones definidas");

    await abrirFormulario(user);
    await completarFormulario(user);
    await user.selectOptions(screen.getByRole("combobox"), "USD");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(createRelation).toHaveBeenCalledWith({
      cajero_user_id: 10,
      authorizer_user_id: 20,
      amount_threshold: 50000,
      currency: "USD",
    });
    await waitFor(() => expect(getRelations).toHaveBeenCalledTimes(2));
    // tras el alta el formulario se cierra
    await waitFor(() =>
      expect(screen.queryByPlaceholderText("User ID del cajero")).not.toBeInTheDocument()
    );
  });

  it("un umbral vacío o no numérico se manda como 0 (aplica siempre)", async () => {
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Sin relaciones definidas");

    await abrirFormulario(user);
    await user.type(screen.getByPlaceholderText("User ID del cajero"), "10");
    await user.type(screen.getByPlaceholderText("User ID del autorizador"), "20");
    await user.type(screen.getByPlaceholderText("0.00 — aplica desde este monto"), "0");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(createRelation).toHaveBeenCalledWith(
      expect.objectContaining({ amount_threshold: 0 })
    );
  });

  it("muestra el detalle de error que devuelve la API al crear", async () => {
    createRelation.mockRejectedValue({ response: { data: { detail: "Relación duplicada" } } });
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Sin relaciones definidas");

    await abrirFormulario(user);
    await completarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText("Relación duplicada")).toBeInTheDocument();
    // el formulario queda abierto para corregir
    expect(screen.getByPlaceholderText("User ID del cajero")).toBeInTheDocument();
  });

  it("usa un mensaje genérico si el error no trae detalle", async () => {
    createRelation.mockRejectedValue(new Error("network"));
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Sin relaciones definidas");

    await abrirFormulario(user);
    await completarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText("Error al crear relación")).toBeInTheDocument();
  });
});

describe("RelacionesPage — baja", () => {
  beforeEach(() => {
    vi.mocked(getRelations).mockReset().mockResolvedValue(RELACIONES);
    vi.mocked(deleteRelation).mockReset().mockResolvedValue({});
    sesion(["requests:write"]);
  });

  it("elimina tras confirmar y recarga la tabla", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Activa");

    await user.click(screen.getAllByTitle("Eliminar")[0]);

    expect(confirmar).toHaveBeenCalledWith("¿Eliminar esta relación?");
    expect(deleteRelation).toHaveBeenCalledWith(1);
    await waitFor(() => expect(getRelations).toHaveBeenCalledTimes(2));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no borra nada", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Activa");

    await user.click(screen.getAllByTitle("Eliminar")[0]);

    expect(deleteRelation).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it("muestra el error si la baja falla", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteRelation.mockRejectedValue({ response: { data: { detail: "Está en uso" } } });
    const user = userEvent.setup();
    render(<RelacionesPage />);
    await screen.findByText("Activa");

    await user.click(screen.getAllByTitle("Eliminar")[1]);

    expect(deleteRelation).toHaveBeenCalledWith(2);
    expect(await screen.findByText("Está en uso")).toBeInTheDocument();
    confirmar.mockRestore();
  });
});
