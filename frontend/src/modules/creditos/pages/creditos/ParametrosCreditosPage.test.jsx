import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ParametrosCreditosPage from "./ParametrosCreditosPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { adminParametros: vi.fn(), upsertParametro: vi.fn() },
}));

const PARS = [
  { clave: "CANALES", valor: "SUCURSAL,WEB" },
  { clave: "CANAL_PORTAL", valor: "WEB" },
  { clave: "CANAL_BACKOFFICE", valor: "SUCURSAL" },
  { clave: "DECIMALES_CALCULO", valor: "4" },
  { clave: "DECIMALES_MOSTRAR", valor: "2" },
];

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.adminParametros.mockResolvedValue(PARS);
  creditos.upsertParametro.mockResolvedValue({});
});

describe("Parámetros de créditos", () => {
  it("carga sólo el ámbito creditos y muestra canales y decimales", async () => {
    render(<ParametrosCreditosPage />);
    expect(await screen.findByRole("button", { name: "Quitar SUCURSAL" })).toBeInTheDocument();
    expect(creditos.adminParametros).toHaveBeenCalledWith("creditos");
    expect(screen.getByRole("button", { name: "Quitar WEB" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Decimales para el cálculo/)).toHaveValue(4);
  });

  it("agrega un canal nuevo, normalizado en mayúsculas", async () => {
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });

    await u.type(screen.getByLabelText("Nuevo canal"), "telefono");
    await u.click(screen.getByRole("button", { name: /Agregar/ }));
    expect(screen.getByRole("button", { name: "Quitar TELEFONO" })).toBeInTheDocument();
  });

  it("quitar el canal del portal lo reemplaza por otro", async () => {
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });
    expect(screen.getByLabelText(/Canal del portal/)).toHaveValue("WEB");

    await u.click(screen.getByRole("button", { name: "Quitar WEB" }));
    expect(screen.queryByRole("button", { name: "Quitar WEB" })).toBeNull();
    expect(screen.getByLabelText(/Canal del portal/)).toHaveValue("SUCURSAL");
  });

  it("guarda los parámetros del ámbito creditos", async () => {
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });

    await u.click(screen.getByRole("button", { name: "Guardar parámetros" }));
    await waitFor(() => expect(creditos.upsertParametro).toHaveBeenCalledTimes(6));
    const claves = creditos.upsertParametro.mock.calls.map((c) => c[0].clave);
    expect(claves).toEqual(["CANALES", "CANAL_PORTAL", "CANAL_BACKOFFICE", "DECIMALES_CALCULO",
                            "DECIMALES_MOSTRAR", "PORTAL_OMITIR_VIDEOS"]);
    expect(creditos.upsertParametro.mock.calls[0][0]).toMatchObject({ valor: "SUCURSAL,WEB", ambito: "creditos" });
    expect(await screen.findByText("Parámetros de créditos guardados.")).toBeInTheDocument();
  });

  it("los decimales quedan acotados entre 0 y 6", async () => {
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });

    const campo = screen.getByLabelText(/Decimales para el cálculo/);
    await u.clear(campo);
    await u.type(campo, "9");
    expect(campo).toHaveValue(6);
  });

  it("si falla el guardado lo informa", async () => {
    creditos.upsertParametro.mockRejectedValue(new Error("Sin permisos"));
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });
    await u.click(screen.getByRole("button", { name: "Guardar parámetros" }));
    expect(await screen.findByText("Sin permisos")).toBeInTheDocument();
  });

  it("en sólo lectura no se puede editar ni guardar", async () => {
    sesion(["creditos:read"]);
    render(<ParametrosCreditosPage />);
    await screen.findByText("Canales de venta");
    expect(screen.queryByRole("button", { name: "Guardar parámetros" })).toBeNull();
    expect(screen.queryByLabelText("Nuevo canal")).toBeNull();
    expect(screen.getByLabelText(/Canal del portal/)).toBeDisabled();
  });

  // ── Videos de la solicitud del portal ───────────────────────────────────
  const omitir = () => screen.getByLabelText("Omitir los videos de la solicitud");

  it("el interruptor de los videos arranca apagado si el parámetro no está", async () => {
    render(<ParametrosCreditosPage />);
    expect(await screen.findByLabelText("Omitir los videos de la solicitud")).not.toBeChecked();
    expect(screen.getByText(/tiene que ver los videos completos/)).toBeInTheDocument();
  });

  it("refleja el parámetro guardado", async () => {
    creditos.adminParametros.mockResolvedValue([...PARS, { clave: "PORTAL_OMITIR_VIDEOS", valor: "true" }]);
    render(<ParametrosCreditosPage />);
    await waitFor(() => expect(omitir()).toBeChecked());
    expect(screen.getByText(/directo a la confirmación/)).toBeInTheDocument();
  });

  it("activarlo y guardarlo manda true", async () => {
    const u = userEvent.setup();
    render(<ParametrosCreditosPage />);
    await screen.findByRole("button", { name: "Quitar SUCURSAL" });

    await u.click(omitir());
    await u.click(screen.getByRole("button", { name: "Guardar parámetros" }));
    await waitFor(() => expect(creditos.upsertParametro).toHaveBeenCalledWith(
      expect.objectContaining({ clave: "PORTAL_OMITIR_VIDEOS", valor: "true", ambito: "creditos" })));
  });

  it("desactivarlo manda false", async () => {
    const u = userEvent.setup();
    creditos.adminParametros.mockResolvedValue([...PARS, { clave: "PORTAL_OMITIR_VIDEOS", valor: "true" }]);
    render(<ParametrosCreditosPage />);
    await waitFor(() => expect(omitir()).toBeChecked());

    await u.click(omitir());
    await u.click(screen.getByRole("button", { name: "Guardar parámetros" }));
    await waitFor(() => expect(creditos.upsertParametro).toHaveBeenCalledWith(
      expect.objectContaining({ clave: "PORTAL_OMITIR_VIDEOS", valor: "false" })));
  });

  it("en sólo lectura el interruptor no se puede tocar", async () => {
    sesion(["creditos:read"]);
    render(<ParametrosCreditosPage />);
    await waitFor(() => expect(omitir()).toBeDisabled());
  });
});
