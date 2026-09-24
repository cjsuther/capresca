import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DespachoModule, { despachoMenu } from "./index";
import { useAuthStore } from "../../context/authStore";

vi.mock("../../api/despacho", () => ({
  getModelos: vi.fn(async () => []),
  crearModelo: vi.fn(), editarModelo: vi.fn(),
  getResoluciones: vi.fn(async () => ({ items: [], total: 0, pagina: 1, por_pagina: 20 })),
  getResolucion: vi.fn(), crearResolucion: vi.fn(), editarResolucion: vi.fn(),
  firmarResolucion: vi.fn(), cargarNumeroReal: vi.fn(), anularResolucion: vi.fn(),
  descargarWord: vi.fn(),
  getTiposAnexo: vi.fn(async () => []),
  getSolicitudesAnexo: vi.fn(async () => ({ items: [], cantidad: 0, total: 0 })),
  asignarAnexo: vi.fn(), quitarDelAnexo: vi.fn(), descargarAnexoWord: vi.fn(),
  getExpedientes: vi.fn(async () => []),
  getExpediente: vi.fn(), getExpedientesPorOficina: vi.fn(async () => []),
  crearExpediente: vi.fn(), pasarExpediente: vi.fn(), archivarExpediente: vi.fn(),
  subirDespacho: vi.fn(), getImportaciones: vi.fn(async () => ({ items: [] })),
  getImportacion: vi.fn(),
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
    permissions: { modules: ["despacho"], actions: { despacho: acciones } },
  });

function montar(ruta = "/modules/despacho") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/despacho/*" element={<DespachoModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("DespachoModule", () => {
  beforeEach(() => sesion(["resoluciones:read", "resoluciones:write"]));

  it("el menú arranca con las dos pantallas del despacho", () => {
    expect(despachoMenu.slice(0, 2).map((i) => i.label)).toEqual([
      "Modelo de resoluciones", "Resoluciones y disposiciones",
    ]);
    expect(despachoMenu.map((i) => i.permission)).toEqual([
      "resoluciones:read", "resoluciones:read", "resoluciones:read", "resoluciones:read", "importar",
    ]);
  });

  it("la raíz del módulo abre las resoluciones", async () => {
    montar();
    expect(await screen.findByRole("heading", { name: "Resoluciones y disposiciones" }))
      .toBeInTheDocument();
  });

  it("importar pide su propio permiso: con resoluciones:write no aparece", async () => {
    montar("/modules/despacho/resoluciones");
    await screen.findByRole("heading", { name: "Resoluciones y disposiciones" });
    expect(screen.queryByText("Importar del sistema anterior")).not.toBeInTheDocument();

    sesion(["resoluciones:read", "importar"]);
    montar("/modules/despacho/importar");
    expect(await screen.findByRole("heading", { name: "Importar del sistema anterior" }))
      .toBeInTheDocument();
  });

  it("cada pantalla del módulo tiene su ruta", async () => {
    montar("/modules/despacho/modelos");
    expect(await screen.findByRole("heading", { name: "Modelo de resoluciones" })).toBeInTheDocument();

    montar("/modules/despacho/anexo");
    expect(await screen.findByRole("heading", { name: "Anexo de resolución" })).toBeInTheDocument();

    montar("/modules/despacho/expedientes");
    expect(await screen.findByRole("heading", { name: "Expedientes y pases" })).toBeInTheDocument();
  });
});
