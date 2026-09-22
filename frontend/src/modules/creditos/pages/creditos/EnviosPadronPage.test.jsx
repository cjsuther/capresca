import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EnviosPadronPage from "./EnviosPadronPage";
import { creditos } from "../../../../api/creditos";

vi.mock("../../../../api/creditos", () => ({
  creditos: { envios: vi.fn(), descargarEnviosExcel: vi.fn() },
}));

const DATOS = {
  cantidad: 1, total: 58000,
  items: [{ credito_id: 900, cliente: "PEREZ JUAN", cbu: "0".repeat(22), cuota_numero: 4, vencimiento: "2026-04-10", importe: 58000 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  creditos.envios.mockResolvedValue(DATOS);
});

describe("Envíos — padrón de débito", () => {
  it("genera el padrón del período elegido", async () => {
    const u = userEvent.setup();
    render(<EnviosPadronPage />);
    const [desde, hasta] = document.querySelectorAll('input[type="date"]');
    expect(desde).toHaveValue("2026-01-01");
    expect(hasta).toHaveValue("2026-12-31");

    await u.clear(desde); await u.type(desde, "2026-03-01");
    await u.clear(hasta); await u.type(hasta, "2026-03-31");
    await u.click(screen.getByRole("button", { name: "Generar" }));

    await waitFor(() => expect(creditos.envios).toHaveBeenCalledWith("2026-03-01", "2026-03-31"));
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(screen.getByText(/1 cuotas/)).toBeInTheDocument();
  });

  it("la descarga del Excel usa el mismo período", async () => {
    const u = userEvent.setup();
    render(<EnviosPadronPage />);
    await u.click(screen.getByRole("button", { name: "Padrón Excel" }));
    expect(creditos.descargarEnviosExcel).toHaveBeenCalledWith("2026-01-01", "2026-12-31");
  });

  it("un período sin cuotas muestra el vacío", async () => {
    creditos.envios.mockResolvedValue({ cantidad: 0, total: 0, items: [] });
    const u = userEvent.setup();
    render(<EnviosPadronPage />);
    await u.click(screen.getByRole("button", { name: "Generar" }));
    expect(await screen.findByText("Sin cuotas en el período")).toBeInTheDocument();
  });
});
