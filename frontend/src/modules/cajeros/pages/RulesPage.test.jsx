import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/cajeros", () => ({
  getRules: vi.fn(),
  createRule: vi.fn(),
  deleteRule: vi.fn(),
}));
vi.mock("../../../api/security", () => ({
  getUsers: vi.fn(),
}));

import { getRules, createRule, deleteRule } from "../../../api/cajeros";
import { getUsers } from "../../../api/security";
import RulesPage from "./RulesPage";
import { useAuthStore } from "../../../context/authStore";

const USUARIOS = [
  { id: 10, username: "ana", full_name: "Ana Cajera" },
  { id: 20, username: "beto", full_name: null },
];

const REGLAS = [
  {
    id: 1, cajero_user_id: 10, cajero_username: "Ana Cajera",
    authorizer_user_id: 20, authorizer_username: "beto",
    currency: "ARS", amount_limit: "50000", reference: "CAJA-1", created_at: "2026-03-01T10:00:00Z",
  },
  {
    id: 2, cajero_user_id: 11, cajero_username: null,
    authorizer_user_id: 21, authorizer_username: null,
    currency: "USD", amount_limit: "1000", reference: null, created_at: null,
  },
];

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: { id: 1, username: "ana" },
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

// [0] cajero (form), [1] autorizador (form), [2] moneda (form), [3] filtro cajero, [4] filtro moneda
const combos = () => screen.getAllByRole("combobox");

// El botón que abre el formulario y el de submit tienen EXACTAMENTE el mismo rótulo
// ("Agregar Regla"), así que hay que desambiguar por posición.
const botonAbrirForm = () => screen.getAllByRole("button", { name: "Agregar Regla" })[0];
const botonSubmit = () => screen.getAllByRole("button", { name: "Agregar Regla" })[1];

const completarFormulario = async (user) => {
  await user.selectOptions(combos()[0], "10");
  await user.selectOptions(combos()[1], "20");
  await user.type(screen.getByPlaceholderText("50000.00"), "75000");
};

describe("RulesPage — listado", () => {
  beforeEach(() => {
    vi.mocked(getRules).mockReset().mockResolvedValue([]);
    vi.mocked(createRule).mockReset().mockResolvedValue({});
    vi.mocked(deleteRule).mockReset().mockResolvedValue({});
    vi.mocked(getUsers).mockReset().mockResolvedValue(USUARIOS);
    sesion(["rules:write"]);
  });

  it("muestra el estado de carga", async () => {
    getRules.mockReturnValue(new Promise(() => {}));
    render(<RulesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.getByText("Administración de Autorizaciones")).toBeInTheDocument();
    // la carga de usuarios sí resuelve: se espera para no dejar un setState fuera de act()
    await screen.findByRole("option", { name: "Ana Cajera" });
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
  });

  it("avisa cuando no hay reglas definidas", async () => {
    render(<RulesPage />);
    expect(await screen.findByText("Sin reglas definidas")).toBeInTheDocument();
  });

  it("lista las reglas con monto formateado y cae al id cuando falta el username", async () => {
    getRules.mockResolvedValue(REGLAS);
    render(<RulesPage />);

    expect(await screen.findByRole("cell", { name: "Ana Cajera" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "beto" })).toBeInTheDocument();
    expect(screen.getByText("$50.000,00")).toBeInTheDocument();
    expect(screen.getByText("$1.000,00")).toBeInTheDocument();
    expect(screen.getByText("CAJA-1")).toBeInTheDocument();
    // la segunda regla no tiene username ni referencia ni fecha
    expect(screen.getByRole("cell", { name: "11" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "21" })).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("muestra un mensaje si falla la carga de reglas", async () => {
    getRules.mockRejectedValue(new Error("500"));
    render(<RulesPage />);
    expect(await screen.findByText("Error al cargar reglas")).toBeInTheDocument();
  });

  it("si falla la carga de usuarios la pantalla sigue funcionando", async () => {
    getUsers.mockRejectedValue(new Error("403"));
    getRules.mockResolvedValue(REGLAS);
    render(<RulesPage />);

    expect(await screen.findByRole("cell", { name: "Ana Cajera" })).toBeInTheDocument();
    // el filtro de cajeros queda sólo con la opción por defecto
    expect(screen.queryAllByRole("option", { name: "Ana Cajera" })).toHaveLength(0);
  });

  it("acepta la respuesta paginada {data: [...]} de getUsers", async () => {
    getUsers.mockResolvedValue({ data: USUARIOS, total: 2 });
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");
    // aparece en el select de filtro (y en los del alta cuando se abre)
    expect(await screen.findAllByRole("option", { name: "Ana Cajera" })).not.toHaveLength(0);
  });

  it("usa el username cuando el usuario no tiene full_name", async () => {
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");
    expect(screen.getByRole("option", { name: "beto" })).toBeInTheDocument();
  });
});

describe("RulesPage — filtros", () => {
  beforeEach(() => {
    vi.mocked(getRules).mockReset().mockResolvedValue([]);
    vi.mocked(getUsers).mockReset().mockResolvedValue(USUARIOS);
    sesion(["rules:write"]);
  });

  it("la primera carga va sin filtros", async () => {
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");
    expect(getRules).toHaveBeenCalledWith({});
  });

  it("filtrar por cajero recarga con el param cajero", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.selectOptions(screen.getAllByRole("combobox")[0], "10");

    await waitFor(() => expect(getRules).toHaveBeenLastCalledWith({ cajero: "10" }));
  });

  it("filtrar por moneda recarga con el param currency", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.selectOptions(screen.getAllByRole("combobox")[1], "USD");

    await waitFor(() => expect(getRules).toHaveBeenLastCalledWith({ currency: "USD" }));
  });

  it("los dos filtros se combinan", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.selectOptions(screen.getAllByRole("combobox")[0], "20");
    await user.selectOptions(screen.getAllByRole("combobox")[1], "EUR");

    await waitFor(() => expect(getRules).toHaveBeenLastCalledWith({ cajero: "20", currency: "EUR" }));
  });
});

describe("RulesPage — permisos", () => {
  beforeEach(() => {
    vi.mocked(getRules).mockReset().mockResolvedValue(REGLAS);
    vi.mocked(getUsers).mockReset().mockResolvedValue(USUARIOS);
  });

  it("sin rules:write no hay alta ni borrado", async () => {
    sesion(["rules:read"]);
    render(<RulesPage />);
    await screen.findByRole("cell", { name: "Ana Cajera" });
    expect(screen.queryByRole("button", { name: /Agregar Regla/ })).not.toBeInTheDocument();
    expect(screen.queryByTitle("Eliminar regla")).not.toBeInTheDocument();
  });

  it("con rules:write aparecen las acciones de escritura", async () => {
    sesion(["rules:write"]);
    render(<RulesPage />);
    await screen.findByRole("cell", { name: "Ana Cajera" });
    expect(screen.getByRole("button", { name: /Agregar Regla/ })).toBeInTheDocument();
    expect(screen.getAllByTitle("Eliminar regla")).toHaveLength(2);
  });
});

describe("RulesPage — alta de reglas", () => {
  beforeEach(() => {
    vi.mocked(getRules).mockReset().mockResolvedValue([]);
    vi.mocked(createRule).mockReset().mockResolvedValue({});
    vi.mocked(getUsers).mockReset().mockResolvedValue(USUARIOS);
    sesion(["rules:write"]);
  });

  it("el botón alterna el formulario", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    expect(screen.queryByPlaceholderText("50000.00")).not.toBeInTheDocument();
    await user.click(botonAbrirForm());
    expect(screen.getByPlaceholderText("50000.00")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByPlaceholderText("50000.00")).not.toBeInTheDocument();
  });

  it("al elegir usuarios completa también el nombre visible en el payload", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.click(botonAbrirForm());
    await completarFormulario(user);
    await user.click(botonSubmit());

    expect(createRule).toHaveBeenCalledWith({
      cajero_user_id: 10,
      cajero_username: "Ana Cajera",
      authorizer_user_id: 20,
      authorizer_username: "beto",
      currency: "ARS",
      amount_limit: 75000,
      reference: null,
    });
  });

  it("manda la moneda y la referencia elegidas", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.click(botonAbrirForm());
    await completarFormulario(user);
    await user.selectOptions(combos()[2], "EUR");
    await user.type(screen.getByPlaceholderText("Dejar vacío = aplica a todas"), "CAJA-9");
    await user.click(botonSubmit());

    expect(createRule).toHaveBeenCalledWith(
      expect.objectContaining({ currency: "EUR", reference: "CAJA-9" })
    );
  });

  it("tras crear cierra el formulario y recarga la tabla", async () => {
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.click(botonAbrirForm());
    await completarFormulario(user);
    await user.click(botonSubmit());

    await waitFor(() => expect(getRules).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByPlaceholderText("50000.00")).not.toBeInTheDocument());
  });

  it("muestra el detalle de error de la API al crear", async () => {
    createRule.mockRejectedValue({ response: { data: { detail: "Ya existe una regla igual" } } });
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.click(botonAbrirForm());
    await completarFormulario(user);
    await user.click(botonSubmit());

    expect(await screen.findByText("Ya existe una regla igual")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("50000.00")).toBeInTheDocument();
  });

  it("usa un mensaje genérico si el error no trae detalle", async () => {
    createRule.mockRejectedValue(new Error("network"));
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByText("Sin reglas definidas");

    await user.click(botonAbrirForm());
    await completarFormulario(user);
    await user.click(botonSubmit());

    expect(await screen.findByText("Error al crear regla")).toBeInTheDocument();
  });
});

describe("RulesPage — baja de reglas", () => {
  beforeEach(() => {
    vi.mocked(getRules).mockReset().mockResolvedValue(REGLAS);
    vi.mocked(deleteRule).mockReset().mockResolvedValue({});
    vi.mocked(getUsers).mockReset().mockResolvedValue(USUARIOS);
    sesion(["rules:write"]);
  });

  it("elimina tras confirmar y recarga", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByRole("cell", { name: "Ana Cajera" });

    await user.click(screen.getAllByTitle("Eliminar regla")[0]);

    expect(confirmar).toHaveBeenCalledWith("¿Confirmar eliminación de esta regla?");
    expect(deleteRule).toHaveBeenCalledWith(1);
    await waitFor(() => expect(getRules).toHaveBeenCalledTimes(2));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no borra", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByRole("cell", { name: "Ana Cajera" });

    await user.click(screen.getAllByTitle("Eliminar regla")[0]);

    expect(deleteRule).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it("muestra el error si la baja falla", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteRule.mockRejectedValue({ response: { data: { detail: "Regla en uso" } } });
    const user = userEvent.setup();
    render(<RulesPage />);
    await screen.findByRole("cell", { name: "Ana Cajera" });

    await user.click(screen.getAllByTitle("Eliminar regla")[1]);

    expect(deleteRule).toHaveBeenCalledWith(2);
    expect(await screen.findByText("Regla en uso")).toBeInTheDocument();
    confirmar.mockRestore();
  });
});
