import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExpedientesPage from "./ExpedientesPage";
import * as api from "../../../api/despacho";
import { useAuthStore } from "../../../context/authStore";

vi.mock("../../../api/despacho");

const exp = (extra = {}) => ({
  id: 5, numero: "1234-2026", caratula: "SOLICITUD DE CREDITO", iniciador: "PEREZ JUAN",
  fecha_inicio: "2026-03-01", estado: "T", oficina_actual: "MESA DE ENTRADAS", ...extra,
});
const conPases = (extra = {}) => ({
  ...exp(extra),
  pases: [{ id: 1, fecha: "2026-03-01", oficina_origen: "", oficina_destino: "MESA DE ENTRADAS",
            motivo: "Alta del expediente", usuario: "ana" }],
});

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok", user: { username: "ana" },
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["resoluciones:read", "expedientes:write"]);
  api.getExpedientes.mockResolvedValue([exp()]);
  api.getExpedientesPorOficina.mockResolvedValue([{ oficina: "MESA DE ENTRADAS", cantidad: 3 }]);
});

describe("expedientes y pases", () => {
  it("lista los expedientes en trámite y el tablero por oficina", async () => {
    render(<ExpedientesPage />);
    expect(await screen.findByText("1234-2026")).toBeInTheDocument();
    expect(screen.getByText("SOLICITUD DE CREDITO")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /MESA DE ENTRADAS/ })).toBeInTheDocument();
    expect(api.getExpedientes).toHaveBeenCalledWith(expect.objectContaining({ estado: "T" }));
  });

  it("el tablero filtra por esa oficina", async () => {
    const user = userEvent.setup();
    render(<ExpedientesPage />);
    await user.click(await screen.findByRole("button", { name: /MESA DE ENTRADAS · 3/ }));
    await waitFor(() => expect(api.getExpedientes).toHaveBeenLastCalledWith(
      expect.objectContaining({ oficina: "MESA DE ENTRADAS" })));
  });

  it("el detalle muestra la historia de pases", async () => {
    const user = userEvent.setup();
    api.getExpediente.mockResolvedValue(conPases());
    render(<ExpedientesPage />);

    await user.click(await screen.findByText("1234-2026"));
    expect(await screen.findByText("Alta del expediente", { exact: false })).toBeInTheDocument();
  });

  it("registra un pase a otra oficina", async () => {
    const user = userEvent.setup();
    api.getExpediente.mockResolvedValue(conPases());
    api.pasarExpediente.mockResolvedValue(conPases({ oficina_actual: "CREDITOS" }));
    render(<ExpedientesPage />);

    await user.click(await screen.findByText("1234-2026"));
    await user.click(await screen.findByRole("button", { name: /Pasar a otra oficina/ }));
    await user.type(screen.getByLabelText("Oficina destino"), "CREDITOS");
    await user.click(screen.getByRole("button", { name: "Registrar pase" }));

    await waitFor(() => expect(api.pasarExpediente).toHaveBeenCalledWith(
      5, expect.objectContaining({ oficina_destino: "CREDITOS" })));
  });

  it("un expediente archivado ya no se pasa", async () => {
    const user = userEvent.setup();
    api.getExpediente.mockResolvedValue(conPases({ estado: "A", oficina_actual: "ARCHIVO" }));
    render(<ExpedientesPage />);

    await user.click(await screen.findByText("1234-2026"));
    await screen.findByRole("heading", { name: "Expediente 1234-2026" });
    expect(screen.queryByRole("button", { name: /Pasar a otra oficina/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Archivar/ })).not.toBeInTheDocument();
  });

  it("crea un expediente nuevo", async () => {
    const user = userEvent.setup();
    api.crearExpediente.mockResolvedValue(conPases({ id: 9, numero: "9999-2026" }));
    render(<ExpedientesPage />);
    await screen.findByText("1234-2026");

    await user.click(screen.getByRole("button", { name: /Nuevo expediente/ }));
    await user.type(screen.getByLabelText("Número"), "9999-2026");
    await user.type(screen.getByLabelText("Carátula"), "PEDIDO DE INFORME");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.crearExpediente).toHaveBeenCalledWith(
      expect.objectContaining({ numero: "9999-2026", caratula: "PEDIDO DE INFORME" })));
  });

  it("sin permiso de escritura es sólo consulta", async () => {
    sesion(["resoluciones:read"]);
    render(<ExpedientesPage />);
    await screen.findByText("1234-2026");
    expect(screen.queryByRole("button", { name: /Nuevo expediente/ })).not.toBeInTheDocument();
  });
});
