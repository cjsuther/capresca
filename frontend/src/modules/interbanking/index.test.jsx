import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InterbankingModule, { interbankingMenu } from "./index";
import { useAuthStore } from "../../context/authStore";
import { getAuditoria, getConfig, getCuentas, getTokenStatus, listarTransferencias } from "../../api/interbanking";

vi.mock("../../api/interbanking", () => ({
  getConfig: vi.fn(),
  saveConfig: vi.fn(),
  testConfig: vi.fn(),
  getTokenStatus: vi.fn(),
  getCuentas: vi.fn(),
  getCuenta: vi.fn(),
  getSaldos: vi.fn(),
  listarTransferencias: vi.fn(),
  crearTransferencia: vi.fn(),
  validarCBU: vi.fn(),
  getEstadoTransferencia: vi.fn(),
  getTransferenciasLocal: vi.fn(),
  getAuditoria: vi.fn(),
  getAuditoriaEntry: vi.fn(),
  exportAuditoria: vi.fn(),
}));

vi.mock("../../api/notifications", () => ({
  getNotifications: vi.fn().mockResolvedValue({ data: [], unread_count: 0 }),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
  markAsRead: vi.fn().mockResolvedValue({}),
  markAllAsRead: vi.fn().mockResolvedValue({}),
}));

const sesion = (acciones) =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana", full_name: "Ana Pérez" },
    permissions: { modules: ["interbanking"], actions: { interbanking: acciones } },
  });

function montar(ruta = "/modules/interbanking") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/interbanking/*" element={<InterbankingModule />} />
      </Routes>
    </MemoryRouter>
  );
}

const TODOS = ["cuentas:read", "transferencias:read", "auditoria:read", "config:read"];

describe("InterbankingModule", () => {
  beforeEach(() => {
    sesion(TODOS);
    getCuentas.mockResolvedValue({ accounts: [] });
    listarTransferencias.mockResolvedValue({ transfers: [], general_data: {} });
    getAuditoria.mockResolvedValue({ data: [], total: 0 });
    getConfig.mockResolvedValue({ name: "Sandbox", base_url: "u", auth_url: "a", client_id: "c" });
    getTokenStatus.mockResolvedValue({ tokens: [] });
  });

  it("el menú declara las cuatro secciones con sus permisos", () => {
    expect(interbankingMenu.map((i) => i.permission)).toEqual(TODOS);
    expect(interbankingMenu.map((i) => i.label)).toEqual([
      "Cuentas", "Transferencias", "Auditoría", "Configuración",
    ]);
  });

  it("la raíz del módulo redirige a Cuentas", async () => {
    montar("/modules/interbanking");
    expect(await screen.findByRole("heading", { name: "Cuentas y Saldos" })).toBeInTheDocument();
  });

  it("oculta del sidebar las secciones sin permiso", () => {
    sesion(["cuentas:read"]);
    montar("/modules/interbanking/cuentas");
    expect(screen.getAllByText("Cuentas").length).toBeGreaterThan(0);
    expect(screen.queryByText("Auditoría")).not.toBeInTheDocument();
    expect(screen.queryByText("Configuración")).not.toBeInTheDocument();
  });

  it("navega desde el sidebar a Transferencias", async () => {
    const user = userEvent.setup();
    montar("/modules/interbanking/cuentas");

    await user.click(screen.getAllByText("Transferencias")[0]);
    expect(await screen.findByRole("heading", { name: "Transferencias" })).toBeInTheDocument();
    await waitFor(() => expect(listarTransferencias).toHaveBeenCalled());
  });

  it("monta la pantalla de auditoría en su ruta", async () => {
    montar("/modules/interbanking/auditoria");
    expect(await screen.findByRole("heading", { name: "Auditoría" })).toBeInTheDocument();
    await waitFor(() => expect(getAuditoria).toHaveBeenCalled());
  });

  it("monta la pantalla de configuración en su ruta", async () => {
    montar("/modules/interbanking/config");
    expect(await screen.findByRole("heading", { name: "Configuración Interbanking" })).toBeInTheDocument();
    await waitFor(() => expect(getConfig).toHaveBeenCalled());
  });
});
