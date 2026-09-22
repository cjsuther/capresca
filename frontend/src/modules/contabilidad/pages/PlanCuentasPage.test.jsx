import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/contabilidad", async (orig) => ({
  ...(await orig()),
  listarCuentas: vi.fn(), crearCuenta: vi.fn(), editarCuenta: vi.fn(), borrarCuenta: vi.fn(),
}));

import * as api from "../../../api/contabilidad";
import PlanCuentasPage from "./PlanCuentasPage";
import { useAuthStore } from "../../../context/authStore";

const cuenta = (codigo, nombre, extra = {}) => ({
  id: codigo.length, codigo, nombre, rubro: "ACTIVO", imputable: true, saldoNormal: "DEUDOR",
  moneda: "ARS", ajustable: false, requiereCentro: false, descripcion: "", activa: true,
  movimientos: 0, enUso: false, ...extra,
});

const CUENTAS = [
  cuenta("1", "Activo", { imputable: false }),
  cuenta("1.1", "Activo corriente", { imputable: false }),
  cuenta("1.1.01", "Caja"),
  cuenta("1.1.02", "Banco", { movimientos: 3, enUso: true }),
  cuenta("2", "Pasivo", { rubro: "PASIVO", imputable: false, saldoNormal: "ACREEDOR" }),
  cuenta("2.1.01", "IVA débito fiscal", { rubro: "PASIVO", saldoNormal: "ACREEDOR" }),
];

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "conta" },
  permissions: { modules: ["contabilidad"], actions: { contabilidad: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["asientos:read", "definiciones:write"]);
  api.listarCuentas.mockResolvedValue({ items: CUENTAS, total: CUENTAS.length,
                                        rubros: ["ACTIVO", "PASIVO", "PATRIMONIO", "INGRESO", "EGRESO", "ORDEN"] });
  api.crearCuenta.mockResolvedValue(cuenta("1.1.03", "Nueva"));
  api.editarCuenta.mockResolvedValue(cuenta("1.1.01", "Caja chica"));
  api.borrarCuenta.mockResolvedValue({});
});

describe("Plan de cuentas", () => {
  it("muestra el árbol jerárquico y se puede plegar una rama", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    expect(await screen.findByText("Activo corriente")).toBeInTheDocument();
    expect(screen.getByText("Caja")).toBeInTheDocument();

    await u.click(screen.getByLabelText("Plegar 1.1"));
    expect(screen.queryByText("Caja")).toBeNull();          // se plegó la rama
    expect(screen.getByText("Activo corriente")).toBeInTheDocument();
  });

  it("al elegir una cuenta muestra sus datos a la derecha", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    expect(screen.getByText("Datos de la cuenta")).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveValue("Caja");
    expect(screen.getByLabelText("Código")).toHaveValue("1.1.01");
    expect(screen.getByText("Sin movimientos")).toBeInTheDocument();
  });

  it("una cuenta en uso no deja cambiar el código ni el rubro", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Banco"));
    expect(screen.getByText("3 movimiento(s) registrados")).toBeInTheDocument();
    expect(screen.getByLabelText("Código")).toBeDisabled();
    expect(screen.getByLabelText("Rubro")).toBeDisabled();
    expect(screen.getByLabelText("Nombre")).toBeEnabled();
  });

  it("el ＋ de una rama propone el próximo código y crea la subcuenta", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await screen.findByText("Activo corriente");

    await u.click(screen.getByLabelText("Agregar subcuenta de 1.1"));
    expect(screen.getByText("Nueva cuenta")).toBeInTheDocument();
    expect(screen.getByLabelText("Código")).toHaveValue("1.1.03");     // sigue a 1.1.02
    expect(screen.getByText("Nueva cuenta…")).toBeInTheDocument();      // aparece en el árbol

    await u.type(screen.getByLabelText("Nombre"), "Recaudaciones");
    await u.click(screen.getByRole("button", { name: "Crear cuenta" }));
    await waitFor(() => expect(api.crearCuenta).toHaveBeenCalledWith(expect.objectContaining({
      codigo: "1.1.03", nombre: "Recaudaciones", rubro: "ACTIVO", saldo_normal: "DEUDOR" })));
  });

  it("la subcuenta hereda el rubro del padre y su saldo normal", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await screen.findByText("Pasivo");
    await u.click(screen.getByLabelText("Agregar subcuenta de 2"));
    expect(screen.getByLabelText("Rubro")).toHaveValue("PASIVO");
    expect(screen.getByLabelText("Saldo normal")).toHaveValue("ACREEDOR");
  });

  it("duplicar una cuenta propone el próximo código y el nombre con (copia)", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    await u.click(screen.getByLabelText("Duplicar cuenta"));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Caja (copia)");
    expect(screen.getByLabelText("Código")).toHaveValue("1.1.03");
  });

  it("avisa antes de perder cambios sin guardar", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    await u.type(screen.getByLabelText("Nombre"), " chica");
    await u.click(screen.getByText("Banco"));
    const dialogo = screen.getByRole("dialog", { name: "Cambios sin guardar" });
    await u.click(within(dialogo).getByRole("button", { name: "Descartar" }));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Banco");
  });

  it("el buscador filtra el árbol manteniendo la rama", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await screen.findByText("Caja");
    await u.type(screen.getByLabelText("Buscar cuenta"), "iva");
    expect(screen.getByText("IVA débito fiscal")).toBeInTheDocument();
    expect(screen.getByText("Pasivo")).toBeInTheDocument();     // la rama que la contiene
    expect(screen.queryByText("Caja")).toBeNull();
  });

  it("guarda los cambios de una cuenta existente", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    await u.clear(screen.getByLabelText("Nombre"));
    await u.type(screen.getByLabelText("Nombre"), "Caja chica");
    await u.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.editarCuenta).toHaveBeenCalledWith(6, expect.objectContaining({
      nombre: "Caja chica" })));
  });

  it("borrar pide confirmación", async () => {
    const u = userEvent.setup();
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    await u.click(screen.getByLabelText("Borrar cuenta"));
    const dialogo = screen.getByRole("dialog", { name: /Borrar la cuenta 1.1.01/ });
    await u.click(within(dialogo).getByRole("button", { name: "Borrar" }));
    await waitFor(() => expect(api.borrarCuenta).toHaveBeenCalledWith(6));
  });

  it("sólo lectura: se ve el árbol y los datos, sin editar", async () => {
    const u = userEvent.setup();
    sesion(["asientos:read"]);
    render(<PlanCuentasPage />);
    await u.click(await screen.findByText("Caja"));
    expect(screen.getByLabelText("Nombre")).toBeDisabled();
    expect(screen.queryByLabelText("Agregar subcuenta de 1.1")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Borrar cuenta")).not.toBeInTheDocument();
  });
});
