import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfigPage from "./ConfigPage";
import { useAuthStore } from "../../../context/authStore";
import {
  getConfig, saveConfig, testConfig, getTokenStatus, getCuentas,
} from "../../../api/interbanking";

vi.mock("../../../api/interbanking", () => ({
  getConfig: vi.fn(),
  saveConfig: vi.fn(),
  testConfig: vi.fn(),
  getTokenStatus: vi.fn(),
  getCuentas: vi.fn(),
}));

const CONFIG = {
  name: "Sandbox Portezuelo",
  base_url: "https://noprod-api-gw.interbanking.com.ar/pre/sandbox",
  auth_url: "https://preauth.interbanking.com.ar",
  client_id: "cli-abc",
  has_client_secret: true,
  username: "-3|usuario|sandbox",
  has_password: true,
  customer_id: "B02072A",
  service_url: "https://sandboxcapresca.com.ar",
  consolidation_account_number: "1234567890",
  consolidation_account_type: "CC",
  consolidation_bank_number: "011",
  consolidation_currency: "ARS",
  payment_account_number: "",
  payment_account_type: "CC",
  payment_bank_number: "011",
  payment_currency: "ARS",
};

const CUENTA = {
  account_number: "9876543210",
  account_type: "CA",
  bank_number: "014",
  bank_name: "Banco Provincia",
  currency: "USD",
  account_label: "Dólares",
};

const conEscritura = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["interbanking"], actions: { interbanking: ["config:read", "config:write"] } },
  });

const soloLectura = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["interbanking"], actions: { interbanking: ["config:read"] } },
  });

const secreto = () => screen.getByPlaceholderText(/Client Secret|guardado/);
const clave = () => screen.getByPlaceholderText(/^Contraseña$|guardada/);
const selects = () => screen.getAllByRole("combobox");
const botonesCargarCuentas = () => screen.getAllByRole("button", { name: /Cargar cuentas/ });

describe("ConfigPage — sólo lectura", () => {
  beforeEach(() => {
    soloLectura();
    getConfig.mockResolvedValue(CONFIG);
    getTokenStatus.mockResolvedValue({ tokens: [] });
  });

  it("muestra la configuración sin exponer el secreto ni la contraseña", async () => {
    render(<ConfigPage />);
    expect(await screen.findByText("Sandbox Portezuelo")).toBeInTheDocument();
    expect(screen.getByText("cli-abc")).toBeInTheDocument();
    expect(screen.getByText("B02072A")).toBeInTheDocument();
    expect(screen.getByText("•••• guardado")).toBeInTheDocument();
    expect(screen.getByText("•••• guardada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
  });

  it("avisa cuando todavía no hay configuración cargada", async () => {
    getConfig.mockRejectedValue(new Error("404"));
    render(<ConfigPage />);
    expect(await screen.findByText("Sin configuración")).toBeInTheDocument();
  });

  it("muestra guiones cuando faltan datos opcionales", async () => {
    getConfig.mockResolvedValue({ ...CONFIG, username: null, customer_id: null, has_password: false, has_client_secret: false, payment_account_number: null });
    render(<ConfigPage />);
    await screen.findByText("Sandbox Portezuelo");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });
});

describe("ConfigPage — estado de tokens", () => {
  beforeEach(() => {
    conEscritura();
    getConfig.mockResolvedValue(CONFIG);
  });

  it("muestra un panel por scope con y sin token activo", async () => {
    getTokenStatus.mockResolvedValue({
      tokens: [
        { scope: "info-financiera", has_active_token: true, minutes_remaining: 42, expires_at: "2026-02-10T12:00:00Z" },
        { scope: "transferencias-confeccion", has_active_token: false },
      ],
    });
    render(<ConfigPage />);

    expect(await screen.findByText("Información Financiera (cuentas, saldos, movimientos)")).toBeInTheDocument();
    expect(screen.getByText("Transferencias (confección y envío)")).toBeInTheDocument();
    expect(screen.getByText(/vence en 42 min/)).toBeInTheDocument();
    expect(screen.getByText("Sin token activo (se generará en la próxima llamada)")).toBeInTheDocument();
  });

  it("un scope desconocido se muestra con su código crudo", async () => {
    getTokenStatus.mockResolvedValue({ tokens: [{ scope: "otro-scope", has_active_token: false }] });
    render(<ConfigPage />);
    expect(await screen.findByText("otro-scope")).toBeInTheDocument();
  });

  it("si falla el estado de tokens no se muestra el panel", async () => {
    getTokenStatus.mockRejectedValue(new Error("500"));
    render(<ConfigPage />);
    await waitFor(() => expect(getConfig).toHaveBeenCalled());
    expect(screen.queryByText(/Token activo/)).not.toBeInTheDocument();
  });
});

describe("ConfigPage — formulario", () => {
  beforeEach(() => {
    conEscritura();
    getConfig.mockResolvedValue(CONFIG);
    getTokenStatus.mockResolvedValue({ tokens: [] });
    saveConfig.mockResolvedValue(CONFIG);
    testConfig.mockResolvedValue({ success: true, scope: "info-financiera", token_preview: "eyJh…", expires_in: 3600 });
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
  });

  it("carga los valores guardados pero deja secreto y contraseña vacíos", async () => {
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    expect(screen.getByPlaceholderText("Ej: B02072A")).toHaveValue("B02072A");
    expect(screen.getByPlaceholderText("-3|...|sandbox")).toHaveValue("-3|usuario|sandbox");
    expect(secreto()).toHaveValue("");
    expect(secreto()).toHaveAttribute("placeholder", "•••••••••••• (guardado)");
    expect(clave()).toHaveValue("");
    expect(clave()).toHaveAttribute("placeholder", "•••••••••••• (guardada)");
  });

  it("sin configuración previa arranca con los valores por defecto", async () => {
    getConfig.mockRejectedValue(new Error("404"));
    render(<ConfigPage />);
    await waitFor(() => expect(getTokenStatus).toHaveBeenCalled());

    expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("");
    expect(screen.getByPlaceholderText("https://preauth.interbanking.com.ar"))
      .toHaveValue("https://preauth.interbanking.com.ar");
    expect(secreto()).toHaveAttribute("placeholder", "Client Secret");
  });

  it("el secreto se escribe enmascarado y se puede revelar", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    expect(secreto()).toHaveAttribute("type", "password");
    await user.type(secreto(), "s3cr3t");
    const ojo = within(secreto().parentElement).getByRole("button");
    await user.click(ojo);
    expect(secreto()).toHaveAttribute("type", "text");
    await user.click(ojo);
    expect(secreto()).toHaveAttribute("type", "password");
  });

  it("la contraseña también se puede revelar", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    expect(clave()).toHaveAttribute("type", "password");
    await user.click(within(clave().parentElement).getByRole("button"));
    expect(clave()).toHaveAttribute("type", "text");
  });

  it("guarda la configuración y avisa del éxito", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.type(secreto(), "nuevo-secreto");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(saveConfig).toHaveBeenCalledTimes(1));
    expect(saveConfig.mock.calls[0][0]).toMatchObject({
      name: "Sandbox Portezuelo",
      client_id: "cli-abc",
      client_secret: "nuevo-secreto",
      customer_id: "B02072A",
    });
    expect(await screen.findByText("Configuración guardada correctamente")).toBeInTheDocument();
    await waitFor(() => expect(getConfig).toHaveBeenCalledTimes(2));   // recarga
  });

  it("muestra el detalle del backend si falla el guardado", async () => {
    saveConfig.mockRejectedValue({ response: { data: { detail: "Client ID inválido" } } });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Client ID inválido")).toBeInTheDocument();
  });

  it("mensaje genérico si el error de guardado no trae detalle", async () => {
    saveConfig.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Error al guardar")).toBeInTheDocument();
  });
});

describe("ConfigPage — prueba de conexión", () => {
  beforeEach(() => {
    conEscritura();
    getConfig.mockResolvedValue(CONFIG);
    getTokenStatus.mockResolvedValue({ tokens: [] });
    getCuentas.mockResolvedValue({ accounts: [] });
  });

  it("prueba el token de info-financiera y muestra el preview", async () => {
    testConfig.mockResolvedValue({ success: true, scope: "info-financiera", token_preview: "eyJh…", expires_in: 3600 });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Probar token info-financiera" }));

    await waitFor(() => expect(testConfig).toHaveBeenCalledTimes(1));
    expect(testConfig.mock.calls[0][1]).toBe("info-financiera");
    expect(await screen.findByText(/OK \(info-financiera\)/)).toBeInTheDocument();
    expect(screen.getByText(/eyJh…/)).toBeInTheDocument();
    expect(screen.getByText(/3600s/)).toBeInTheDocument();
  });

  it("prueba el token de transferencias con su propio scope", async () => {
    testConfig.mockResolvedValue({ success: true, scope: "transferencias-confeccion", token_preview: "abc…", expires_in: 60 });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Probar token transferencias" }));
    await waitFor(() => expect(testConfig.mock.calls[0][1]).toBe("transferencias-confeccion"));
    expect(await screen.findByText(/OK \(transferencias-confeccion\)/)).toBeInTheDocument();
  });

  it("muestra el error devuelto por la prueba", async () => {
    testConfig.mockRejectedValue({ response: { data: { detail: "invalid_client" } } });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Probar token info-financiera" }));
    expect(await screen.findByText(/Error \(info-financiera\)/)).toBeInTheDocument();
    expect(screen.getByText(/invalid_client/)).toBeInTheDocument();
  });

  it("mensaje genérico si la prueba falla sin detalle", async () => {
    testConfig.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(screen.getByRole("button", { name: "Probar token info-financiera" }));
    expect(await screen.findByText(/Error de conexión/)).toBeInTheDocument();
  });
});

describe("ConfigPage — cuentas de consolidación y pagos", () => {
  beforeEach(() => {
    conEscritura();
    getConfig.mockResolvedValue(CONFIG);
    getTokenStatus.mockResolvedValue({ tokens: [] });
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
    saveConfig.mockResolvedValue(CONFIG);
  });

  it("muestra la cuenta de consolidación guardada y ninguna de pagos", async () => {
    render(<ConfigPage />);
    expect(await screen.findByText(/Seleccionada: 1234567890 · CC ·/)).toBeInTheDocument();
    expect(selects()[1]).toHaveDisplayValue("— Sin cuenta seleccionada —");
  });

  it("carga las cuentas disponibles en los dos selectores", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    await waitFor(() => expect(getCuentas).toHaveBeenCalledTimes(1));

    expect(await screen.findAllByText(/9876543210 · Banco Provincia · USD · Dólares/)).toHaveLength(2);
  });

  it("al elegir una cuenta copia tipo, banco y moneda a consolidación", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    await screen.findAllByText(/9876543210/);
    await user.selectOptions(selects()[0], "9876543210");

    expect(screen.getByText(/Seleccionada: 9876543210 · CA ·/)).toBeInTheDocument();
    expect(screen.getByText(/banco 014 · USD/)).toBeInTheDocument();
  });

  it("al elegir una cuenta de pagos salientes la copia a su sección", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[1]);
    await screen.findAllByText(/9876543210/);
    await user.selectOptions(selects()[1], "9876543210");

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(saveConfig).toHaveBeenCalled());
    expect(saveConfig.mock.calls[0][0]).toMatchObject({
      payment_account_number: "9876543210",
      payment_account_type: "CA",
      payment_bank_number: "014",
      payment_currency: "USD",
    });
  });

  it("volver a la opción vacía limpia la cuenta de pagos salientes", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[1]);
    await screen.findAllByText(/9876543210/);
    await user.selectOptions(selects()[1], "9876543210");
    expect(screen.getByText(/Seleccionada: 9876543210 · CA ·/)).toBeInTheDocument();

    await user.selectOptions(selects()[1], "");
    await waitFor(() =>
      expect(screen.queryByText(/Seleccionada: 9876543210 · CA ·/)).not.toBeInTheDocument()
    );
  });

  it("volver a la opción vacía limpia la cuenta elegida", async () => {
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    await screen.findAllByText(/9876543210/);
    await user.selectOptions(selects()[0], "");

    await waitFor(() => expect(screen.queryByText(/Seleccionada: 1234567890/)).not.toBeInTheDocument());
  });

  it("avisa si la API no devuelve ninguna cuenta", async () => {
    getCuentas.mockResolvedValue({ accounts: [] });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    expect(await screen.findByText("No se obtuvieron cuentas")).toBeInTheDocument();
  });

  it("muestra el detalle del backend si no se pueden cargar las cuentas", async () => {
    getCuentas.mockRejectedValue({ response: { data: { detail: "Scope no habilitado" } } });
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    expect(await screen.findByText("Scope no habilitado")).toBeInTheDocument();
  });

  it("mensaje genérico si la carga de cuentas falla sin detalle", async () => {
    getCuentas.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<ConfigPage />);
    await waitFor(() => expect(screen.getByPlaceholderText("Ej: Sandbox Portezuelo")).toHaveValue("Sandbox Portezuelo"));

    await user.click(botonesCargarCuentas()[0]);
    expect(await screen.findByText(/revisá credenciales info-financiera/)).toBeInTheDocument();
  });
});
