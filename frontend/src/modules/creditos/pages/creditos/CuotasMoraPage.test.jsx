import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CuotasMoraPage from "./CuotasMoraPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({ creditos: { cuotasMora: vi.fn() } }));

const DATOS = {
  cantidad: 2, total: 180000,
  items: [
    { credito_id: 900, cuota_numero: 3, cliente: "PEREZ JUAN", vencimiento: "2026-02-10", dias_mora: 30, importe: 100000 },
    { credito_id: 901, cuota_numero: 1, cliente: "GOMEZ ANA", vencimiento: "2026-03-01", dias_mora: 10, importe: 80000 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  creditos.cuotasMora.mockResolvedValue(DATOS);
});
afterEach(() => vi.useRealTimers());

describe("Cuotas en mora", () => {
  it("no consulta hasta generar, y arranca en la fecha de hoy", () => {
    render(<CuotasMoraPage />);
    expect(creditos.cuotasMora).not.toHaveBeenCalled();
    expect(document.querySelector('input[type="date"]')).toHaveValue("2026-03-15");
    expect(screen.getByText(/Elegí la fecha de corte/)).toBeInTheDocument();
  });

  it("genera el informe a la fecha de corte y muestra el total", async () => {
    const u = userEvent.setup();
    render(<CuotasMoraPage />);

    await u.click(screen.getByRole("button", { name: "Generar" }));
    await waitFor(() => expect(creditos.cuotasMora).toHaveBeenCalledWith("2026-03-15"));
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(screen.getByText("#900-3")).toBeInTheDocument();
    expect(screen.getByText(/2 cuotas vencidas/)).toBeInTheDocument();
  });

  it("un corte sin mora muestra el vacío", async () => {
    creditos.cuotasMora.mockResolvedValue({ cantidad: 0, total: 0, items: [] });
    const u = userEvent.setup();
    render(<CuotasMoraPage />);
    await u.click(screen.getByRole("button", { name: "Generar" }));
    expect(await screen.findByText("Sin cuotas en mora")).toBeInTheDocument();
  });

  it("si falla lo informa y no deja datos viejos", async () => {
    creditos.cuotasMora.mockRejectedValue(new Error("Fecha inválida"));
    const u = userEvent.setup();
    render(<CuotasMoraPage />);
    await u.click(screen.getByRole("button", { name: "Generar" }));
    expect(await screen.findByText("Fecha inválida")).toBeInTheDocument();
    expect(screen.queryByText("PEREZ JUAN")).toBeNull();
  });
});
