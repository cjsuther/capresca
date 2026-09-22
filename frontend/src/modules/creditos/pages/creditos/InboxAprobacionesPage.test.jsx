import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InboxAprobacionesPage from "./InboxAprobacionesPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { inboxAprobaciones: vi.fn(), inboxAprobarPendiente: vi.fn(), inboxRechazarPendiente: vi.fn() },
}));

const navegar = vi.fn();
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig()),
  useNavigate: () => navegar,
}));

const TAREAS = {
  items: [
    { tipo: "SOLICITUD", id: "p1", titulo: "Solicitud SOL-9", estado: "PENDIENTE", accion: "aprobar-inline",
      solicitante: "ana", fecha: "2026-03-10", detalle: "PEREZ JUAN · $500.000", ruta: "/x" },
    { tipo: "DESEMBOLSO", id: "p2", titulo: "Desembolso CTO-3", estado: "PENDIENTE", accion: "aprobar",
      solicitante: "luis", fecha: "2026-03-11", detalle: "$300.000", ruta: "/modules/creditos/liquidacion-lote",
      deepLink: { clave: "lote", valor: "2026-03-11" } },
    { tipo: "RAREZA", id: "p3", titulo: "Otra cosa", estado: "PENDIENTE", accion: "resolver",
      solicitante: "ana", fecha: "", detalle: "—", ruta: "/y" },
  ],
};

const montar = () => render(<MemoryRouter><InboxAprobacionesPage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  creditos.inboxAprobaciones.mockResolvedValue(TAREAS);
  creditos.inboxAprobarPendiente.mockResolvedValue({ ejecutado: true });
  creditos.inboxRechazarPendiente.mockResolvedValue({});
});

describe("Inbox de aprobaciones", () => {
  it("muestra el panel de agrupaciones con su conteo", async () => {
    montar();
    expect(await screen.findByText("Solicitudes de crédito")).toBeInTheDocument();
    expect(screen.getByText("3 pendientes")).toBeInTheDocument();
    expect(screen.getByText("Otros")).toBeInTheDocument();                   // tipo desconocido
    expect(screen.getByRole("button", { name: /Refinanciaciones/ })).toBeDisabled();
  });

  it("entrar a un grupo lista sus tareas y se puede volver al panel", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: /Solicitudes de crédito/ }));

    expect(await screen.findByText("Solicitud SOL-9")).toBeInTheDocument();
    expect(screen.queryByText("Desembolso CTO-3")).toBeNull();

    await u.click(screen.getByRole("button", { name: "← Panel" }));
    expect(screen.getByText("Desembolsos")).toBeInTheDocument();
  });

  it("aprueba una tarea inline y avisa si quedó ejecutada", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: /Solicitudes de crédito/ }));
    await u.click(await screen.findByRole("button", { name: "Aprobar" }));

    await waitFor(() => expect(creditos.inboxAprobarPendiente).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Aprobado y ejecutado.")).toBeInTheDocument();
    expect(creditos.inboxAprobaciones).toHaveBeenCalledTimes(2);
  });

  it("si faltan niveles lo aclara", async () => {
    creditos.inboxAprobarPendiente.mockResolvedValue({ ejecutado: false, faltan: 2 });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: /Solicitudes de crédito/ }));
    await u.click(await screen.findByRole("button", { name: "Aprobar" }));
    expect(await screen.findByText("Aprobado. Faltan 2 nivel(es).")).toBeInTheDocument();
  });

  it("rechazar pide el motivo y lo manda", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: /Solicitudes de crédito/ }));
    await u.click(await screen.findByRole("button", { name: "Rechazar" }));

    const dialogo = await screen.findByRole("dialog", { name: "Rechazar" });
    await u.type(screen.getByLabelText("Motivo del rechazo"), "faltan papeles");
    await u.click(within(dialogo).getByRole("button", { name: "Rechazar" }));

    await waitFor(() => expect(creditos.inboxRechazarPendiente).toHaveBeenCalledWith("p1", "faltan papeles"));
  });

  it("una tarea que se resuelve en otra pantalla navega y deja el deep link", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByRole("button", { name: /Desembolsos/ }));
    await u.click(await screen.findByRole("button", { name: /Aprobar →/ }));

    expect(sessionStorage.getItem("lote")).toBe("2026-03-11");
    expect(navegar).toHaveBeenCalledWith("/modules/creditos/liquidacion-lote");
  });

  it("sin tareas pendientes lo dice", async () => {
    creditos.inboxAprobaciones.mockResolvedValue({ items: [] });
    montar();
    expect(await screen.findByText("No tenés tareas pendientes.")).toBeInTheDocument();
  });

  it("si el inbox falla lo informa", async () => {
    creditos.inboxAprobaciones.mockRejectedValue(new Error("Error 503"));
    montar();
    expect(await screen.findByText("Error 503")).toBeInTheDocument();
  });
});
