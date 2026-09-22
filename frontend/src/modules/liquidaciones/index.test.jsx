import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LiquidacionesModule, { liquidacionesMenu } from "./index";
import { useAuthStore } from "../../context/authStore";
import * as liqApi from "../../api/liquidaciones";

vi.mock("../../api/liquidaciones", () => ({
  getBatches: vi.fn(),
  getBatchDetalle: vi.fn(),
  getBatchValidaciones: vi.fn(),
  getBatchArchivos: vi.fn(),
  processZip: vi.fn(),
  uploadZip: vi.fn(),
  retryConciliacion: vi.fn(),
  getArchivoUrl: vi.fn(() => "/api/liquidaciones/batches/1/archivos/1"),
}));

// El Layout real arrastra la campana de notificaciones y su polling; acá sólo
// interesa que el módulo le pase el sidebar y renderice sus rutas.
vi.mock("../../components/Layout", () => ({
  Layout: ({ children, sidebar }) => (
    <div>
      {typeof sidebar === "function" ? sidebar(undefined) : sidebar}
      <main>{children}</main>
    </div>
  ),
}));

function montar(ruta = "/modules/liquidaciones") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/liquidaciones/*" element={<LiquidacionesModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("módulo Liquidaciones", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "tok",
      user: { username: "ana" },
      permissions: { modules: ["liquidaciones"], actions: { liquidaciones: ["liq:read"] } },
    });
    liqApi.getBatches.mockResolvedValue([]);
  });

  it("declara una única entrada de menú con su permiso", () => {
    expect(liquidacionesMenu).toHaveLength(1);
    expect(liquidacionesMenu[0]).toMatchObject({
      label: "Liquidaciones",
      path: "/modules/liquidaciones/liquidaciones",
      permission: "liq:read",
    });
  });

  it("redirige la raíz del módulo a la pantalla de liquidaciones", async () => {
    montar();
    await waitFor(() => expect(liqApi.getBatches).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Liquidaciones" })).toBeInTheDocument();
    expect(await screen.findByText("Sin lotes procesados")).toBeInTheDocument();
  });

  it("muestra el link del sidebar con el permiso liq:read y lo oculta sin él", async () => {
    montar();
    expect(await screen.findByRole("link", { name: "Liquidaciones" })).toHaveAttribute(
      "href",
      "/modules/liquidaciones/liquidaciones"
    );
  });

  it("oculta el link del sidebar sin el permiso liq:read", async () => {
    useAuthStore.setState({
      permissions: { modules: ["liquidaciones"], actions: { liquidaciones: [] } },
    });
    montar();
    await waitFor(() => expect(liqApi.getBatches).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: "Liquidaciones" })).not.toBeInTheDocument();
  });
});
