import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConciliacionModule, { conciliacionMenu } from "./index";
import { useAuthStore } from "../../context/authStore";
import * as conciliacionApi from "../../api/conciliacion";

vi.mock("../../api/conciliacion", () => ({
  getConciliacion: vi.fn(),
  getSummary: vi.fn(),
  getAgencies: vi.fn(),
  updateRecord: vi.fn(),
  assignAgency: vi.fn(),
  removeLink: vi.fn(),
  downloadBoleta: vi.fn(),
  addAdjustment: vi.fn(),
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

function montar(ruta = "/modules/conciliacion") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/conciliacion/*" element={<ConciliacionModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("módulo Conciliación", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "tok",
      user: { username: "ana" },
      permissions: { modules: ["conciliacion"], actions: { conciliacion: ["read"] } },
    });
    conciliacionApi.getConciliacion.mockResolvedValue({
      reconciliation_records: [],
      interbanking_transactions: [],
    });
    conciliacionApi.getSummary.mockResolvedValue(null);
    conciliacionApi.getAgencies.mockResolvedValue([]);
  });

  it("declara una única entrada de menú con su permiso", () => {
    expect(conciliacionMenu).toHaveLength(1);
    expect(conciliacionMenu[0]).toMatchObject({
      label: "Conciliación",
      path: "/modules/conciliacion/conciliacion",
      permission: "read",   // el código tal cual lo registra security (sin prefijo del módulo)
    });
  });

  it("redirige la raíz del módulo a la pantalla de conciliación", async () => {
    montar();
    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Conciliación" })).toBeInTheDocument();
  });

  it("el sidebar muestra el link con los permisos que manda el backend", async () => {
    // El seed de security registra los permisos de este módulo como "read"/"write"/"download"
    // (sin prefijo): el menú tiene que usar esos mismos códigos o el link queda siempre oculto.
    montar();
    expect(await screen.findByRole("link", { name: "Conciliación" })).toHaveAttribute(
      "href",
      "/modules/conciliacion/conciliacion"
    );
  });

  it("sin el permiso de lectura no se muestra el link", async () => {
    useAuthStore.setState({
      permissions: { modules: ["conciliacion"], actions: { conciliacion: ["write"] } },
    });
    montar();
    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: "Conciliación" })).not.toBeInTheDocument();
  });
});
