import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FeriadosPage from "./FeriadosPage";
import * as api from "../../../api/configuraciones";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/configuraciones", async (original) => ({
  ...(await original()),
  listarPaises: vi.fn(), listarFeriados: vi.fn(), crearFeriado: vi.fn(), editarFeriado: vi.fn(),
  borrarFeriado: vi.fn(), importarFeriados: vi.fn(),
}));

const HOY = new Date().getFullYear();
const NAVIDAD = { id: 1, pais: "AR", fecha: `${HOY}-12-25`, nombre: "Navidad", tipo: "INAMOVIBLE", origen: "OFICIAL", activo: true };
const PUENTE = { id: 2, pais: "AR", fecha: `${HOY}-12-24`, nombre: "Puente navideño", tipo: "PUENTE", origen: "MANUAL", activo: false };

const sesion = (acciones) => useAuthStore.setState({
  token: "t", user: { username: "ana" },
  permissions: { modules: ["configuraciones"], actions: { configuraciones: acciones } },
});

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["feriados:read", "feriados:write"]);
  api.listarPaises.mockResolvedValue({ items: [{ codigo: "AR", nombre: "Argentina" }, { codigo: "UY", nombre: "Uruguay" }] });
  api.listarFeriados.mockResolvedValue({ items: [PUENTE, NAVIDAD], anios: [HOY] });
  api.crearFeriado.mockResolvedValue({});
  api.borrarFeriado.mockResolvedValue({ ok: true });
  api.importarFeriados.mockResolvedValue({ importados: 3, totalFuente: 11, fuente: "OFICIAL (Nager.Date)" });
});

describe("Feriados", () => {
  it("lista el año actual del país con tipo, origen y estado", async () => {
    render(<FeriadosPage />);
    const fila = (await screen.findByText("Navidad")).closest("tr");
    expect(within(fila).getByText("Inamovible")).toBeInTheDocument();
    expect(within(fila).getByText("Calendario oficial")).toBeInTheDocument();
    expect(within(screen.getByText("Puente navideño").closest("tr")).getByText("Inactivo")).toBeInTheDocument();
    expect(screen.getByText("1 vigente(s)")).toBeInTheDocument();
    expect(api.listarFeriados).toHaveBeenCalledWith("AR", HOY);
  });

  it("cambiar país o año recarga el calendario", async () => {
    const u = userEvent.setup();
    render(<FeriadosPage />);
    await screen.findByText("Navidad");
    await u.selectOptions(screen.getByLabelText("Año"), String(HOY + 1));
    await waitFor(() => expect(api.listarFeriados).toHaveBeenLastCalledWith("AR", HOY + 1));
    await u.selectOptions(screen.getByLabelText("País"), "UY");
    await waitFor(() => expect(api.listarFeriados).toHaveBeenLastCalledWith("UY", HOY + 1));
  });

  it("importa el año elegido y avisa cuántos sumó", async () => {
    const u = userEvent.setup();
    render(<FeriadosPage />);
    await u.click(await screen.findByRole("button", { name: `Importar ${HOY}` }));
    expect(await screen.findByText(/3 feriado\(s\) nuevo\(s\) de 11/)).toBeInTheDocument();
    expect(api.importarFeriados).toHaveBeenCalledWith("AR", HOY);
  });

  it("alta manual de un feriado", async () => {
    const u = userEvent.setup();
    render(<FeriadosPage />);
    await u.click(await screen.findByRole("button", { name: /Nuevo feriado/ }));
    const modal = screen.getByRole("dialog", { name: "Nuevo feriado" });
    await u.clear(within(modal).getByLabelText("Fecha"));
    await u.type(within(modal).getByLabelText("Fecha"), `${HOY}-06-17`);
    await u.type(within(modal).getByLabelText("Nombre"), "Güemes");
    await u.selectOptions(within(modal).getByLabelText("Tipo"), "TRASLADABLE");
    await u.click(within(modal).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.crearFeriado).toHaveBeenCalledWith({
      pais: "AR", fecha: `${HOY}-06-17`, nombre: "Güemes", tipo: "TRASLADABLE", activo: true }));
  });

  it("borrar pide confirmación", async () => {
    const u = userEvent.setup();
    render(<FeriadosPage />);
    await u.click(within((await screen.findByText("Navidad")).closest("tr")).getByRole("button", { name: "Borrar" }));
    const conf = screen.getByRole("dialog", { name: "Borrar feriado" });
    await u.click(within(conf).getByRole("button", { name: "Cancelar" }));
    expect(api.borrarFeriado).not.toHaveBeenCalled();
    await u.click(within(screen.getByText("Navidad").closest("tr")).getByRole("button", { name: "Borrar" }));
    await u.click(within(screen.getByRole("dialog", { name: "Borrar feriado" })).getByRole("button", { name: "Borrar" }));
    await waitFor(() => expect(api.borrarFeriado).toHaveBeenCalledWith(1));
  });

  it("con sólo lectura no se importa ni se edita", async () => {
    sesion(["feriados:read"]);
    api.listarFeriados.mockResolvedValue({ items: [], anios: [] });
    render(<FeriadosPage />);
    expect(await screen.findByText(`Sin feriados cargados para ${HOY}.`)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Importar/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Nuevo feriado/ })).toBeNull();
  });
});
