import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ImpuestosPage from "./ImpuestosPage";
import * as api from "../../../api/configuraciones";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarImpuestos: vi.fn(), crearImpuesto: vi.fn(), editarImpuesto: vi.fn(),
  bajaImpuesto: vi.fn(), reactivarImpuesto: vi.fn(),
}));

const IVA = { id: 1, codigo: "IVA21", nombre: "IVA 21%", tipo: "IVA", alicuota: 21, base: "INTERES",
  cuenta_contable: "2.1.07.01", jurisdiccion: "", vigente_desde: null, vigente_hasta: null, activo: true };
const IIBB = { ...IVA, id: 2, codigo: "IIBB-CAT", nombre: "Ingresos Brutos", tipo: "IIBB", alicuota: 4, base: "TOTAL",
  vigente_desde: "2026-01-01", vigente_hasta: null, activo: false };

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "ana" },
  permissions: { modules: ["configuraciones"], actions: { configuraciones: acciones } },
});
const tabla = () => screen.getByRole("table");

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["impuestos:read", "impuestos:write"]);
  api.listarImpuestos.mockResolvedValue({ items: [IVA, IIBB] });
  api.crearImpuesto.mockResolvedValue({});
  api.editarImpuesto.mockResolvedValue({});
  api.bajaImpuesto.mockResolvedValue({});
  api.reactivarImpuesto.mockResolvedValue({});
});

describe("Impuestos", () => {
  it("lista alícuota, base, vigencia y estado", async () => {
    render(<ImpuestosPage />);
    const fila = (await screen.findByText("IVA21")).closest("tr");
    expect(within(fila).getByText("21 %")).toBeInTheDocument();
    expect(within(fila).getByText("Interés")).toBeInTheDocument();
    expect(within(fila).getByText("Sin límite")).toBeInTheDocument();
    const iibb = screen.getByText("IIBB-CAT").closest("tr");
    expect(within(iibb).getByText("De baja")).toBeInTheDocument();
    expect(within(iibb).getByText(/1\/1\/2026/)).toBeInTheDocument();
  });

  it("filtra por texto y por activos", async () => {
    const u = userEvent.setup();
    render(<ImpuestosPage />);
    await screen.findByText("IVA21");
    await u.click(screen.getByLabelText("Sólo activos"));
    expect(within(tabla()).queryByText("IIBB-CAT")).toBeNull();
    await u.click(screen.getByRole("button", { name: /Limpiar filtros/ }));
    await u.type(screen.getByPlaceholderText("Código o nombre"), "brutos");
    expect(within(tabla()).queryByText("IVA21")).toBeNull();
    expect(within(tabla()).getByText("IIBB-CAT")).toBeInTheDocument();
  });

  it("da de alta un impuesto con la alícuota numérica", async () => {
    const u = userEvent.setup();
    render(<ImpuestosPage />);
    await u.click(await screen.findByRole("button", { name: /Nuevo impuesto/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo impuesto" });
    await u.type(within(modal).getByLabelText("Código"), "PERC");
    await u.type(within(modal).getByLabelText("Nombre"), "Percepción");
    await u.selectOptions(within(modal).getByLabelText("Tipo"), "PERCEPCION");
    await u.type(within(modal).getByLabelText("Alícuota (%)"), "3.5");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.crearImpuesto).toHaveBeenCalledWith(expect.objectContaining({
      codigo: "PERC", tipo: "PERCEPCION", alicuota: 3.5, vigente_desde: null })));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.listarImpuestos).toHaveBeenCalledTimes(2);
  });

  it("el error de la API queda en el formulario", async () => {
    api.crearImpuesto.mockRejectedValue({ response: { data: { detail: "Ya existe un impuesto con ese código" } } });
    const u = userEvent.setup();
    render(<ImpuestosPage />);
    await u.click(await screen.findByRole("button", { name: /Nuevo impuesto/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo impuesto" });
    await u.type(within(modal).getByLabelText("Código"), "IVA21");
    await u.type(within(modal).getByLabelText("Nombre"), "dup");
    await u.type(within(modal).getByLabelText("Alícuota (%)"), "21");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    expect(await within(modal).findByText("Ya existe un impuesto con ese código")).toBeInTheDocument();
  });

  it("edita un impuesto existente", async () => {
    const u = userEvent.setup();
    render(<ImpuestosPage />);
    await u.click(within((await screen.findByText("IVA21")).closest("tr")).getByRole("button", { name: "Editar" }));
    const modal = screen.getByRole("dialog", { name: "Editar IVA21" });
    await u.clear(within(modal).getByLabelText("Nombre"));
    await u.type(within(modal).getByLabelText("Nombre"), "IVA general");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.editarImpuesto).toHaveBeenCalledWith(1, expect.objectContaining({ nombre: "IVA general", alicuota: 21 })));
  });

  it("la baja se confirma; la reactivación es directa", async () => {
    const u = userEvent.setup();
    render(<ImpuestosPage />);
    await u.click(within((await screen.findByText("IVA21")).closest("tr")).getByRole("button", { name: "Dar de baja" }));
    const conf = screen.getByRole("dialog", { name: "Dar de baja el impuesto" });
    expect(api.bajaImpuesto).not.toHaveBeenCalled();
    await u.click(within(conf).getByRole("button", { name: "Dar de baja" }));
    await waitFor(() => expect(api.bajaImpuesto).toHaveBeenCalledWith(1));
    await u.click(within(screen.getByText("IIBB-CAT").closest("tr")).getByRole("button", { name: "Reactivar" }));
    await waitFor(() => expect(api.reactivarImpuesto).toHaveBeenCalledWith(2));
  });

  it("con sólo lectura no hay altas ni acciones", async () => {
    sesion(["impuestos:read"]);
    render(<ImpuestosPage />);
    await screen.findByText("IVA21");
    expect(screen.queryByRole("button", { name: /Nuevo impuesto/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Editar" })).toBeNull();
  });

  it("si la carga falla lo informa", async () => {
    api.listarImpuestos.mockRejectedValue({ response: { data: { detail: "Falta el permiso configuraciones:impuestos:read" } } });
    render(<ImpuestosPage />);
    expect(await screen.findByText(/Falta el permiso/)).toBeInTheDocument();
  });
});
