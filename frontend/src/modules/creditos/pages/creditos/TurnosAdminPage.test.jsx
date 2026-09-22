import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TurnosAdminPage from "./TurnosAdminPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { turnosPreview: vi.fn(), turnosGenerar: vi.fn(), turnoAsignar: vi.fn() },
}));

const PREVIA = {
  dias_habiles: 2, turnos_por_dia: 50, resto: 0, total: 100, ya_existen: 0,
  distribucion: [{ fecha: "2026-04-01", cantidad: 50 }, { fecha: "2026-04-02", cantidad: 50 }],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  sesion(["creditos:read", "creditos:write"]);
  creditos.turnosPreview.mockResolvedValue(PREVIA);
  creditos.turnosGenerar.mockResolvedValue({ generados: 100, periodo: "202604" });
  creditos.turnoAsignar.mockResolvedValue({ numero: 17, fecha: "2026-04-01", apellido_nombre: "PEREZ JUAN" });
});
afterEach(() => vi.useRealTimers());

describe("Turnos de crédito · generación", () => {
  it("arranca en el período del mes siguiente y previsualiza la distribución", async () => {
    const u = userEvent.setup();
    render(<TurnosAdminPage />);
    expect(screen.getByLabelText("Período (YYYYMM)")).toHaveValue("202604");

    await u.click(screen.getByRole("button", { name: "Previsualizar distribución" }));
    await waitFor(() => expect(creditos.turnosPreview).toHaveBeenCalledWith("202604", 100));
    expect(await screen.findByText(/Días hábiles:/)).toBeInTheDocument();
    expect(screen.getByText("1/4/2026")).toBeInTheDocument();
  });

  it("generar pide confirmación y avisa cuántos turnos creó", async () => {
    const u = userEvent.setup();
    render(<TurnosAdminPage />);
    await u.click(screen.getByRole("button", { name: "Previsualizar distribución" }));
    await u.click(await screen.findByRole("button", { name: "Confirmar y generar" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(creditos.turnosGenerar).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Generar turnos" }));
    await waitFor(() => expect(creditos.turnosGenerar).toHaveBeenCalledWith({ periodo: "202604", cantidad: 100 }));
    expect(await screen.findByText(/Generados 100 turnos/)).toBeInTheDocument();
  });

  it("si el período ya tiene turnos avisa y no deja generar", async () => {
    creditos.turnosPreview.mockResolvedValue({ ...PREVIA, ya_existen: 100 });
    const u = userEvent.setup();
    render(<TurnosAdminPage />);
    await u.click(screen.getByRole("button", { name: "Previsualizar distribución" }));
    expect(await screen.findByText(/Ya existen 100 turnos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar y generar" })).toBeDisabled();
  });
});

describe("Turnos de crédito · asignación", () => {
  it("asigna el próximo turno libre a un CUIL", async () => {
    const u = userEvent.setup();
    render(<TurnosAdminPage />);

    await u.type(screen.getByLabelText("CUIL"), "20301234567");
    await u.type(screen.getByLabelText("Apellido y nombre"), "PEREZ JUAN");
    await u.click(screen.getByRole("button", { name: "Asignar turno" }));

    await waitFor(() => expect(creditos.turnoAsignar).toHaveBeenCalledWith({
      periodo: "202604", cuil: "20301234567", apellido_nombre: "PEREZ JUAN", numero: undefined,
    }));
    expect(await screen.findByText(/Turno N° 17 \(1\/4\/2026\) asignado a PEREZ JUAN/)).toBeInTheDocument();
  });

  it("sin CUIL no se puede asignar", () => {
    render(<TurnosAdminPage />);
    expect(screen.getByRole("button", { name: "Asignar turno" })).toBeDisabled();
  });

  it("si el turno pedido no está disponible lo informa", async () => {
    creditos.turnoAsignar.mockRejectedValue(new Error("El turno 17 ya está asignado"));
    const u = userEvent.setup();
    render(<TurnosAdminPage />);
    await u.type(screen.getByLabelText("CUIL"), "20301234567");
    await u.type(screen.getByLabelText(/N° \(excepcional/), "17");
    await u.click(screen.getByRole("button", { name: "Asignar turno" }));
    expect(await screen.findByText("El turno 17 ya está asignado")).toBeInTheDocument();
  });

  it("en sólo lectura no se ofrece asignar ni generar", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<TurnosAdminPage />);
    expect(screen.queryByRole("button", { name: "Asignar turno" })).toBeNull();
    await u.click(screen.getByRole("button", { name: "Previsualizar distribución" }));
    await screen.findByText(/Días hábiles:/);
    expect(screen.queryByRole("button", { name: "Confirmar y generar" })).toBeNull();
  });
});
