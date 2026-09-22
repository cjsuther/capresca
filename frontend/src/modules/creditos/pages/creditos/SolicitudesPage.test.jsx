import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SolicitudesPage from "./SolicitudesPage";
import { creditos } from "../../../../api/creditos";
import { searchClients } from "../../../../api/clientes";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { solicitudes: vi.fn(), solicitud: vi.fn(), crearSolicitud: vi.fn(), otorgar: vi.fn(), lineas: vi.fn() },
}));
vi.mock("../../../../api/clientes", () => ({ searchClients: vi.fn() }));

const CLIENTE = { id: 7, code: "PH-7", human_profile: { first_name: "Ana", last_name: "Perez", document_number: "30123456" } };
const LINEAS = [{ id: 12, nombre: "PERSONAL", tipo_calculo: 1 }, { id: 15, nombre: "CUOTA FIJA", tipo_calculo: 5 }];
const SOLICITUDES = [
  { id: 41, cliente_id: 7, cliente_nombre: "PEREZ, ANA", monto_solicitado: 300000, cantidad_cuotas: 12, estado: "I" },
  { id: 40, cliente_id: 8, cliente_nombre: "GOMEZ, LUIS", monto_solicitado: 150000, cantidad_cuotas: 6, estado: "O" },
];
const DETALLE = {
  id: 41, estado: "I", cliente_nombre: "PEREZ, ANA", linea_nombre: "PERSONAL",
  monto_solicitado: 300000, cantidad_cuotas: 12, margen_disponible: 80000,
  advertencias: [], puede_otorgarse: true,
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  sesion(["creditos:read", "creditos:write"]);
  creditos.solicitudes.mockResolvedValue(SOLICITUDES);
  creditos.lineas.mockResolvedValue(LINEAS);
  creditos.solicitud.mockResolvedValue(DETALLE);
  creditos.crearSolicitud.mockResolvedValue(DETALLE);
  creditos.otorgar.mockResolvedValue({ id: 900, cantidad_cuotas: 1, total_a_pagar: 320000,
    cuotas: [{ numero: 1, fecha_vencimiento: "2026-04-10", saldo_capital: 0, amortizacion: 300000, interes: 20000, iva_interes: 4200, total: 324200 }] });
  searchClients.mockResolvedValue({ data: [CLIENTE] });
});
afterEach(() => vi.useRealTimers());

describe("Solicitudes", () => {
  it("lista las solicitudes con su estado", async () => {
    render(<SolicitudesPage />);
    expect(await screen.findByText("PEREZ, ANA")).toBeInTheDocument();
    expect(screen.getByText("Ingresada")).toBeInTheDocument();
    expect(screen.getByText("Otorgada")).toBeInTheDocument();
  });

  it("el cliente de la nueva solicitud se elige en el padrón", async () => {
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("PEREZ, ANA");

    await u.click(screen.getByRole("button", { name: "Registrar solicitud" }));
    expect(await screen.findByText("Elegí el cliente en el padrón.")).toBeInTheDocument();
    expect(creditos.crearSolicitud).not.toHaveBeenCalled();

    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(screen.getByRole("button", { name: "Registrar solicitud" }));

    await waitFor(() => expect(creditos.crearSolicitud).toHaveBeenCalledWith(expect.objectContaining({
      cliente_id: 7, linea_id: 12, monto_solicitado: "300000", cantidad_cuotas: 12,
      fecha_primer_vencimiento: "2026-03-15",
    })));
  });

  it("con línea de cuota fija bloquea las cuotas y manda la cuota fija", async () => {
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("PEREZ, ANA");

    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.selectOptions(screen.getByLabelText("Línea"), "15");
    expect(screen.getByLabelText(/Plazo \(lo recalcula el motor\)/)).toBeDisabled();

    await u.type(screen.getByLabelText("Cuota fija"), "25000");
    await u.click(screen.getByRole("button", { name: "Registrar solicitud" }));
    await waitFor(() => expect(creditos.crearSolicitud).toHaveBeenCalledWith(
      expect.objectContaining({ linea_id: 15, cuota_fija: "25000" })));
  });

  it("abre el detalle y otorga el crédito mostrando el plan", async () => {
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await u.click(await screen.findByText("PEREZ, ANA"));

    await waitFor(() => expect(creditos.solicitud).toHaveBeenCalledWith(41));
    await u.click(await screen.findByRole("button", { name: "Otorgar crédito" }));
    await waitFor(() => expect(creditos.otorgar).toHaveBeenCalledWith(41, false));
    expect(await screen.findByText(/Crédito N° 900/)).toBeInTheDocument();
  });

  it("una solicitud que no puede otorgarse sólo ofrece forzar", async () => {
    creditos.solicitud.mockResolvedValue({ ...DETALLE, puede_otorgarse: false, advertencias: ["Supera el margen"] });
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await u.click(await screen.findByText("PEREZ, ANA"));

    expect(await screen.findByText("Supera el margen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Otorgar crédito" })).toBeDisabled();
    await u.click(screen.getByRole("button", { name: "Otorgar igual (forzar)" }));
    await waitFor(() => expect(creditos.otorgar).toHaveBeenCalledWith(41, true));
  });

  it("si el alta falla lo informa", async () => {
    creditos.crearSolicitud.mockRejectedValue(new Error("El cliente ya tiene una solicitud en curso"));
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await screen.findByText("PEREZ, ANA");

    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(screen.getByRole("button", { name: "Registrar solicitud" }));
    expect(await screen.findByText("El cliente ya tiene una solicitud en curso")).toBeInTheDocument();
  });

  it("en sólo lectura no se dan de alta ni se otorgan", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<SolicitudesPage />);
    await u.click(await screen.findByText("PEREZ, ANA"));
    expect(screen.queryByRole("button", { name: "Registrar solicitud" })).toBeNull();
    expect(await screen.findByRole("dialog")).toBeInTheDocument();     // el detalle sí se abre
    expect(screen.queryByRole("button", { name: "Otorgar crédito" })).toBeNull();
    expect(screen.queryByRole("button", { name: /forzar/ })).toBeNull();
  });
});
