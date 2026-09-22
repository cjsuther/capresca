import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LineasCreditoPage from "./LineasCreditoPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { adminLineas: vi.fn(), crearLinea: vi.fn(), editarLinea: vi.fn() },
}));

const LINEAS = [
  { id: 12, nombre: "PERSONAL", cartera: 1, tipo_calculo: 1, tna: "60", por_afecta: "30", plazo_max: 36, activa: true },
  { id: 13, nombre: "ESPECIAL", cartera: 2, tipo_calculo: 3, tna: "45", por_afecta: "25", plazo_max: 24, activa: false },
];

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.adminLineas.mockResolvedValue(LINEAS);
  creditos.crearLinea.mockResolvedValue({ id: 14 });
  creditos.editarLinea.mockResolvedValue({ id: 12 });
  window.scrollTo = vi.fn();
});

describe("Líneas de crédito", () => {
  it("lista las líneas con su sistema de cálculo en castellano", async () => {
    render(<LineasCreditoPage />);
    expect(await screen.findByText("PERSONAL")).toBeInTheDocument();
    // "Francés" y "Directo" también son opciones del combo: se miran en la tabla.
    const tabla = screen.getByRole("table");
    expect(within(tabla).getByText("Francés")).toBeInTheDocument();
    expect(within(tabla).getByText("Directo")).toBeInTheDocument();
    expect(within(tabla).getByText("60%")).toBeInTheDocument();
  });

  it("crea una línea con los valores del formulario", async () => {
    const u = userEvent.setup();
    render(<LineasCreditoPage />);
    await screen.findByText("PERSONAL");

    await u.type(screen.getByLabelText("Nombre"), "NUEVA LINEA");
    await u.clear(screen.getByLabelText("TNA (%)"));
    await u.type(screen.getByLabelText("TNA (%)"), "72");
    await u.selectOptions(screen.getByLabelText("Sistema de cálculo"), "2");
    await u.click(screen.getByRole("button", { name: "Crear línea" }));

    await waitFor(() => expect(creditos.crearLinea).toHaveBeenCalledWith(
      expect.objectContaining({ nombre: "NUEVA LINEA", tna: "72", tipo_calculo: "2" })));
    expect(creditos.adminLineas).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.getByLabelText("Nombre")).toHaveValue(""));
  });

  it("clickear una fila carga la línea para editarla y guarda con PUT", async () => {
    const u = userEvent.setup();
    render(<LineasCreditoPage />);
    await u.click(await screen.findByText("PERSONAL"));

    expect(await screen.findByRole("heading", { name: "Editar línea #12" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveValue("PERSONAL");

    await u.clear(screen.getByLabelText("% afectación haber"));
    await u.type(screen.getByLabelText("% afectación haber"), "35");
    await u.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(creditos.editarLinea).toHaveBeenCalledWith(12,
      expect.objectContaining({ nombre: "PERSONAL", por_afecta: "35" })));
    expect(creditos.editarLinea.mock.calls[0][1].id).toBeUndefined();   // el id no viaja en el cuerpo
  });

  it("se puede salir de la edición sin guardar", async () => {
    const u = userEvent.setup();
    render(<LineasCreditoPage />);
    await u.click(await screen.findByText("PERSONAL"));
    await u.click(await screen.findByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("heading", { name: "Nueva línea de crédito" })).toBeInTheDocument();
    expect(creditos.editarLinea).not.toHaveBeenCalled();
  });

  it("muestra el error del backend", async () => {
    creditos.crearLinea.mockRejectedValue(new Error("Ya existe una línea con ese nombre"));
    const u = userEvent.setup();
    render(<LineasCreditoPage />);
    await screen.findByText("PERSONAL");
    await u.type(screen.getByLabelText("Nombre"), "PERSONAL");
    await u.click(screen.getByRole("button", { name: "Crear línea" }));
    expect(await screen.findByText("Ya existe una línea con ese nombre")).toBeInTheDocument();
  });

  it("en sólo lectura no hay formulario ni edición por fila", async () => {
    sesion(["creditos:read"]);
    render(<LineasCreditoPage />);
    await screen.findByText("PERSONAL");
    expect(screen.queryByRole("heading", { name: /Nueva línea/ })).toBeNull();
    expect(screen.queryByText(/clickeá una para editarla/)).toBeNull();
  });
});
