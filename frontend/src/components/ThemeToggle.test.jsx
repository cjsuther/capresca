import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "./ThemeToggle";
import { useThemeStore } from "../context/themeStore";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = "";
  useThemeStore.setState({ tema: "system" });
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});

describe("selector de tema", () => {
  it("ofrece claro, oscuro y sistema, con el activo marcado", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("radio", { name: "Claro" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "Oscuro" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "Sistema" })).toHaveAttribute("aria-checked", "true");
  });

  it("cambiar a oscuro aplica el tema y queda marcado", async () => {
    const u = userEvent.setup();
    render(<ThemeToggle />);
    await u.click(screen.getByRole("radio", { name: "Oscuro" }));

    expect(useThemeStore.getState().tema).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("radio", { name: "Oscuro" })).toHaveAttribute("aria-checked", "true");
  });

  it("volver a claro destildar el oscuro", async () => {
    const u = userEvent.setup();
    render(<ThemeToggle />);
    await u.click(screen.getByRole("radio", { name: "Oscuro" }));
    await u.click(screen.getByRole("radio", { name: "Claro" }));

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(screen.getByRole("radio", { name: "Claro" })).toHaveAttribute("aria-checked", "true");
  });
});
