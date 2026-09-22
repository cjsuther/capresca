import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// SolicitudesPage importa getRequests / createRequest, que HOY no existen en src/api/cajeros.js
// (ver src/api/cajeros.test.js). Se mockea el módulo entero.
vi.mock("../../../api/cajeros", () => ({
  getRequests: vi.fn(),
  createRequest: vi.fn(),
}));

import { getRequests, createRequest } from "../../../api/cajeros";
import SolicitudesPage from "./SolicitudesPage";
import { useAuthStore } from "../../../context/authStore";

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: { id: 1, username: "ana" },
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

const SOLICITUDES = [
  { id: 1, amount: "1000.00", currency: "ARS", reason: "caja chica", status: "PENDING", requested_at: "2026-03-01T10:00:00Z" },
  { id: 2, amount: "2000.00", currency: "USD", reason: null, status: "APPROVED", requested_at: "2026-03-02T10:00:00Z" },
  { id: 3, amount: "3000.00", currency: "ARS", reason: "otra", status: "REJECTED", requested_at: "2026-03-03T10:00:00Z" },
  { id: 4, amount: "4000.00", currency: "ARS", reason: "vieja", status: "EXPIRED", requested_at: "2026-03-04T10:00:00Z" },
];

describe("SolicitudesPage — listado", () => {
  beforeEach(() => {
    vi.mocked(getRequests).mockReset().mockResolvedValue([]);
    vi.mocked(createRequest).mockReset().mockResolvedValue({});
    sesion(["requests:write"]);
  });

  it("muestra el estado de carga", () => {
    getRequests.mockReturnValue(new Promise(() => {}));
    render(<SolicitudesPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    expect(screen.getByText("Mis Solicitudes")).toBeInTheDocument();
  });

  it("pide las solicitudes propias (no las de autorización)", async () => {
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");
    expect(getRequests).toHaveBeenCalledWith(false);
  });

  it("avisa cuando no hay solicitudes", async () => {
    render(<SolicitudesPage />);
    expect(await screen.findByText("Sin solicitudes")).toBeInTheDocument();
  });

  it("traduce los cuatro estados posibles y muestra guión si no hay motivo", async () => {
    getRequests.mockResolvedValue(SOLICITUDES);
    render(<SolicitudesPage />);

    expect(await screen.findByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText("Aprobada")).toBeInTheDocument();
    expect(screen.getByText("Rechazada")).toBeInTheDocument();
    expect(screen.getByText("Expirada")).toBeInTheDocument();
    expect(screen.getByText("1000.00 ARS")).toBeInTheDocument();
    expect(screen.getByText("caja chica")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(5);
  });
});

describe("SolicitudesPage — alta", () => {
  beforeEach(() => {
    vi.mocked(getRequests).mockReset().mockResolvedValue([]);
    vi.mocked(createRequest).mockReset().mockResolvedValue({});
    sesion(["requests:write"]);
  });

  it("sin requests:write no se puede crear una solicitud", async () => {
    sesion([]);
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");
    expect(screen.queryByRole("button", { name: /Nueva solicitud/ })).not.toBeInTheDocument();
  });

  it("el botón alterna la visibilidad del formulario", async () => {
    const user = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");

    expect(screen.queryByRole("button", { name: "Enviar" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    expect(screen.getByRole("button", { name: "Enviar" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    expect(screen.queryByRole("button", { name: "Enviar" })).not.toBeInTheDocument();
  });

  it("Cancelar cierra el formulario sin llamar a la API", async () => {
    const user = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");

    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(screen.queryByRole("button", { name: "Enviar" })).not.toBeInTheDocument();
    expect(createRequest).not.toHaveBeenCalled();
  });

  it("crea la solicitud con el monto parseado, cierra el form y recarga", async () => {
    const user = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");

    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    await user.type(screen.getByRole("spinbutton"), "1500.75");
    await user.selectOptions(screen.getByRole("combobox"), "EUR");
    await user.type(screen.getByRole("textbox"), "compra de divisa");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(createRequest).toHaveBeenCalledWith({
      amount: 1500.75,
      currency: "EUR",
      reason: "compra de divisa",
    });
    await waitFor(() => expect(getRequests).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Enviar" })).not.toBeInTheDocument()
    );
  });

  it("el formulario queda limpio para la próxima solicitud", async () => {
    const user = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("Sin solicitudes");

    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    await user.type(screen.getByRole("spinbutton"), "1500");
    await user.type(screen.getByRole("textbox"), "algo");
    await user.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(createRequest).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    expect(screen.getByRole("spinbutton")).toHaveValue(null);
    expect(screen.getByRole("textbox")).toHaveValue("");
    expect(screen.getByRole("combobox")).toHaveValue("ARS");
  });
});
