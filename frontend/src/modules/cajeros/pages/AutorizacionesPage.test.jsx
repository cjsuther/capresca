import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// AutorizacionesPage importa getRequests / approveRequest / rejectRequest, que HOY no existen
// en src/api/cajeros.js (ver src/api/cajeros.test.js). Se mockea el módulo entero.
vi.mock("../../../api/cajeros", () => ({
  getRequests: vi.fn(),
  approveRequest: vi.fn(),
  rejectRequest: vi.fn(),
}));

import { getRequests, approveRequest, rejectRequest } from "../../../api/cajeros";
import AutorizacionesPage from "./AutorizacionesPage";

const PENDIENTE = {
  id: 1, status: "PENDING", amount: "15000.00", currency: "ARS",
  cajero_user_id: 10, reason: "Retiro de caja fuerte", requested_at: "2026-03-01T10:00:00Z",
};
const OTRA_PENDIENTE = {
  id: 2, status: "PENDING", amount: "500.00", currency: "USD",
  cajero_user_id: 11, reason: null, requested_at: "2026-03-02T10:00:00Z",
};
const APROBADA = { ...PENDIENTE, id: 3, status: "APPROVED" };

describe("AutorizacionesPage", () => {
  beforeEach(() => {
    vi.mocked(getRequests).mockReset().mockResolvedValue([]);
    vi.mocked(approveRequest).mockReset().mockResolvedValue({});
    vi.mocked(rejectRequest).mockReset().mockResolvedValue({});
  });

  it("muestra el estado de carga", () => {
    getRequests.mockReturnValue(new Promise(() => {}));
    render(<AutorizacionesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.getByText("Solicitudes pendientes de autorización")).toBeInTheDocument();
  });

  it("pide al backend sólo las solicitudes a autorizar", async () => {
    render(<AutorizacionesPage />);
    await screen.findByText("No hay solicitudes pendientes");
    expect(getRequests).toHaveBeenCalledWith(true);
  });

  it("avisa cuando no hay solicitudes pendientes", async () => {
    render(<AutorizacionesPage />);
    expect(await screen.findByText("No hay solicitudes pendientes")).toBeInTheDocument();
  });

  it("filtra en cliente las solicitudes que ya no están PENDING", async () => {
    getRequests.mockResolvedValue([APROBADA]);
    render(<AutorizacionesPage />);
    expect(await screen.findByText("No hay solicitudes pendientes")).toBeInTheDocument();
  });

  it("muestra monto, moneda, cajero y motivo de cada pendiente", async () => {
    getRequests.mockResolvedValue([PENDIENTE, OTRA_PENDIENTE]);
    render(<AutorizacionesPage />);

    expect(await screen.findByText("#1 — 15000.00 ARS")).toBeInTheDocument();
    expect(screen.getByText("#2 — 500.00 USD")).toBeInTheDocument();
    expect(screen.getByText("Cajero ID: 10")).toBeInTheDocument();
    expect(screen.getByText("Retiro de caja fuerte")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Aprobar/ })).toHaveLength(2);
  });

  it("aprueba mandando las notas escritas y recarga", async () => {
    getRequests.mockResolvedValue([PENDIENTE]);
    const user = userEvent.setup();
    render(<AutorizacionesPage />);
    await screen.findByText("#1 — 15000.00 ARS");

    await user.type(screen.getByPlaceholderText("Comentario..."), "ok, verificado");
    await user.click(screen.getByRole("button", { name: /Aprobar/ }));

    expect(approveRequest).toHaveBeenCalledWith(1, { resolution_notes: "ok, verificado" });
    await waitFor(() => expect(getRequests).toHaveBeenCalledTimes(2));
  });

  it("aprueba con notas vacías si no se escribió nada", async () => {
    getRequests.mockResolvedValue([PENDIENTE]);
    const user = userEvent.setup();
    render(<AutorizacionesPage />);
    await user.click(await screen.findByRole("button", { name: /Aprobar/ }));

    expect(approveRequest).toHaveBeenCalledWith(1, { resolution_notes: "" });
  });

  it("las notas son independientes por solicitud", async () => {
    getRequests.mockResolvedValue([PENDIENTE, OTRA_PENDIENTE]);
    const user = userEvent.setup();
    render(<AutorizacionesPage />);
    await screen.findByText("#1 — 15000.00 ARS");

    const inputs = screen.getAllByPlaceholderText("Comentario...");
    await user.type(inputs[1], "segunda");

    expect(inputs[0]).toHaveValue("");
    expect(inputs[1]).toHaveValue("segunda");

    await user.click(screen.getAllByRole("button", { name: /Aprobar/ })[1]);
    expect(rejectRequest).not.toHaveBeenCalled();
    expect(approveRequest).toHaveBeenCalledWith(2, { resolution_notes: "segunda" });
  });

  it("rechaza pidiendo confirmación previa", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    getRequests.mockResolvedValue([PENDIENTE]);
    const user = userEvent.setup();
    render(<AutorizacionesPage />);

    await user.type(await screen.findByPlaceholderText("Comentario..."), "sin respaldo");
    await user.click(screen.getByRole("button", { name: /Rechazar/ }));

    expect(confirmar).toHaveBeenCalledWith("¿Rechazar esta solicitud?");
    expect(rejectRequest).toHaveBeenCalledWith(1, { resolution_notes: "sin respaldo" });
    await waitFor(() => expect(getRequests).toHaveBeenCalledTimes(2));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no rechaza", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    getRequests.mockResolvedValue([PENDIENTE]);
    const user = userEvent.setup();
    render(<AutorizacionesPage />);

    await user.click(await screen.findByRole("button", { name: /Rechazar/ }));

    expect(rejectRequest).not.toHaveBeenCalled();
    expect(getRequests).toHaveBeenCalledTimes(1);
    confirmar.mockRestore();
  });
});
