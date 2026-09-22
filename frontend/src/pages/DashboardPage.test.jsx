import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import DashboardPage, { ALL_MODULES } from "./DashboardPage";
import { useAuthStore } from "../context/authStore";

function montar() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/modules/cajeros" element={<p>módulo cajeros</p>} />
        <Route path="/modules/creditos" element={<p>módulo creditos</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "tok", user: { username: "ana", full_name: "Ana" }, permissions: { modules: [] } });
    delete window.location;
    window.location = { assign: vi.fn(), href: "" };
  });

  it("sólo muestra los módulos habilitados", () => {
    useAuthStore.setState({ permissions: { modules: ["cajeros", "creditos"], actions: {} } });
    montar();
    expect(screen.getByText("Cajeros")).toBeInTheDocument();
    expect(screen.getByText("Créditos")).toBeInTheDocument();
    expect(screen.queryByText("Seguridad")).not.toBeInTheDocument();
    expect(screen.queryByText("Liquidaciones")).not.toBeInTheDocument();
  });

  it("avisa cuando no hay módulos habilitados", () => {
    montar();
    expect(screen.getByText("No tienes módulos habilitados.")).toBeInTheDocument();
  });

  it("navega por el router a un módulo interno", async () => {
    useAuthStore.setState({ permissions: { modules: ["cajeros"], actions: {} } });
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText("Cajeros"));
    expect(screen.getByText("módulo cajeros")).toBeInTheDocument();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("Créditos navega por el router como el resto de los módulos", async () => {
    useAuthStore.setState({ permissions: { modules: ["creditos"], actions: {} } });
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText("Créditos"));
    expect(screen.getByText("módulo creditos")).toBeInTheDocument();
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});

// ── Colores de los módulos ───────────────────────────────────────────────────────────────────────
describe("acentos del dashboard", () => {
  const css = readFileSync(join(process.cwd(), "src/index.css"), "utf8");
  const bloque = (selector) => {
    const i = css.indexOf(`${selector} {`, css.indexOf("Acentos de los módulos"));
    return css.slice(i, css.indexOf("}", i));
  };
  const tokens = (selector) =>
    Object.fromEntries([...bloque(selector).matchAll(/--(acc-[\w-]+):\s*(#[0-9a-f]{6})/g)].map((m) => [m[1], m[2]]));

  it("cada módulo tiene su color, en tema claro y oscuro", () => {
    const claro = tokens(":root");
    const oscuro = tokens(".dark");
    for (const m of ALL_MODULES) {
      expect(claro[`acc-${m.code}`], m.code).toBeTruthy();
      expect(claro[`acc-${m.code}-bg`], m.code).toBeTruthy();
      expect(oscuro[`acc-${m.code}`], `${m.code} (oscuro)`).toBeTruthy();
      expect(oscuro[`acc-${m.code}-bg`], `${m.code} (oscuro)`).toBeTruthy();
    }
  });

  it("no se repite ningún color entre módulos", () => {
    for (const selector of [":root", ".dark"]) {
      const valores = Object.entries(tokens(selector))
        .filter(([k]) => !k.endsWith("-bg"))
        .map(([, v]) => v);
      expect(new Set(valores).size, `colores repetidos en ${selector}`).toBe(valores.length);
    }
  });

  it("las tarjetas usan el acento de su módulo y el mismo estilo de superficie", () => {
    useAuthStore.setState({ permissions: { modules: ALL_MODULES.map((m) => m.code), actions: {} } });
    montar();
    const tarjeta = screen.getByRole("button", { name: /Tesorería/ });
    expect(tarjeta).toHaveStyle({ "--acc": "var(--acc-tesoreria)" });
    expect(tarjeta.className).toContain("bg-surface");
    // ninguna tarjeta trae colores propios de Tailwind (romperían el tema oscuro)
    screen.getAllByRole("button").forEach((b) => expect(b.className).not.toMatch(/bg-(blue|green|purple|indigo|rose|teal|amber|slate)-/));
  });
});
