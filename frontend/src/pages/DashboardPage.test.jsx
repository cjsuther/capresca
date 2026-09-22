import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./DashboardPage";
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
