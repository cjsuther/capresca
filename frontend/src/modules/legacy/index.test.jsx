import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LegacyModule, { legacyMenu } from "./index";
import { useAuthStore } from "../../context/authStore";
import * as legacyApi from "../../api/legacy";

vi.mock("../../api/legacy", () => ({
  getInteractions: vi.fn(),
  getDatabases: vi.fn(),
  getStatus: vi.fn(),
  drainOutbox: vi.fn(),
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

function montar(ruta = "/modules/legacy") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/legacy/*" element={<LegacyModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("módulo Legacy", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "tok",
      user: { username: "ana" },
      permissions: { modules: ["legacy"], actions: { legacy: ["interactions:read"] } },
    });
    legacyApi.getInteractions.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
    legacyApi.getDatabases.mockResolvedValue({ databases: [] });
    legacyApi.getStatus.mockResolvedValue({
      integration_enabled: false,
      write_mode: "disabled",
      outbox_pending: 0,
      smb: { mounted: false, mount_root: "/mnt/legacy", tables_present: 0, tables_total: 0 },
      sync_state: [],
    });
  });

  it("declara las dos entradas de menú con el permiso de lectura", () => {
    expect(legacyMenu.map((m) => [m.label, m.path, m.permission])).toEqual([
      ["Interacciones", "/modules/legacy/interacciones", "interactions:read"],
      ["Estado", "/modules/legacy/estado", "interactions:read"],
    ]);
  });

  it("redirige la raíz del módulo a Interacciones", async () => {
    montar();
    await waitFor(() => expect(legacyApi.getInteractions).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Interacciones con el legacy" })).toBeInTheDocument();
    expect(legacyApi.getStatus).not.toHaveBeenCalled();
  });

  it("la ruta /estado muestra la pantalla de estado", async () => {
    montar("/modules/legacy/estado");
    await waitFor(() => expect(legacyApi.getStatus).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Estado de la integración" })).toBeInTheDocument();
    expect(await screen.findByText("APAGADA")).toBeInTheDocument();
  });

  it("el sidebar muestra las dos opciones con el permiso interactions:read", async () => {
    montar();
    await waitFor(() => expect(legacyApi.getInteractions).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "Interacciones" })).toHaveAttribute(
      "href",
      "/modules/legacy/interacciones"
    );
    expect(screen.getByRole("link", { name: "Estado" })).toHaveAttribute(
      "href",
      "/modules/legacy/estado"
    );
  });

  it("sin el permiso de lectura el sidebar queda vacío", async () => {
    useAuthStore.setState({
      permissions: { modules: ["legacy"], actions: { legacy: ["admin:write"] } },
    });
    montar();
    await waitFor(() => expect(legacyApi.getInteractions).toHaveBeenCalled());
    expect(screen.queryAllByRole("link").map((a) => a.textContent)).toEqual(["Inicio"]);  // sólo la salida del módulo
  });
});
