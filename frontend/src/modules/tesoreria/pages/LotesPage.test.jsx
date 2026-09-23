import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/tesoreria", async (orig) => ({ ...(await orig()), listarLotes: vi.fn() }));

import { listarLotes } from "../../../api/tesoreria";
import LotesPage from "./LotesPage";
import { useAuthStore } from "../../../context/authStore";

const LOTE = { id: 3, codigo: "LOT-2026-00003", origen: "CREDITOS", descripcion: "Desembolsos del día", referencia_origen: "x",
               estado: "PENDIENTE_APROBACION", simulado: false, cantidad: 2, excluidos: 1, total: 800000, creado_en: "2026-09-22T10:00:00" };

function montar(acciones = ["lotes:read", "lotes:write"]) {
  useAuthStore.setState({ token: "t", user: { username: "teso" },
                          permissions: { modules: ["tesoreria"], actions: { tesoreria: acciones } } });
  render(
    <MemoryRouter initialEntries={["/lotes"]}>
      <Routes>
        <Route path="/lotes" element={<LotesPage />} />
        <Route path="/modules/tesoreria/lotes/:id" element={<p>detalle</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LotesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listarLotes.mockResolvedValue({ items: [LOTE], pendientes: 4, envio_simulado: true });
  });

  it("arranca mostrando lo pendiente, con KPIs y aviso de simulación", async () => {
    montar();
    expect(await screen.findByText("LOT-2026-00003")).toBeInTheDocument();
    expect(listarLotes).toHaveBeenCalledWith({ estado: "PENDIENTE_APROBACION,APROBADO" });
    expect(screen.getByText("Pendiente de aprobación")).toBeInTheDocument();
    expect(screen.getByText("2 (+1 excl.)")).toBeInTheDocument();
    expect(screen.getByText(/Modo simulación/)).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("filtra por origen y abre el detalle al hacer clic", async () => {
    montar();
    await screen.findByText("LOT-2026-00003");
    await userEvent.selectOptions(screen.getByLabelText("Origen"), "CONCILIACION");
    await waitFor(() => expect(listarLotes).toHaveBeenLastCalledWith({ estado: "PENDIENTE_APROBACION,APROBADO", origen: "CONCILIACION" }));
    await userEvent.click(await screen.findByText("LOT-2026-00003"));
    expect(await screen.findByText("detalle")).toBeInTheDocument();
  });

  it("sin permiso de escritura no ofrece cargar lotes", async () => {
    montar(["lotes:read"]);
    await screen.findByText("LOT-2026-00003");
    expect(screen.queryByRole("button", { name: /Nuevo lote/ })).not.toBeInTheDocument();
  });
});
