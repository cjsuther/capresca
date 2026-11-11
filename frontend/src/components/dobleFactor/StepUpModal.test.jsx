import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/dobleFactor", async (orig) => ({
  ...(await orig()),
  pedirStepUp: vi.fn(),
  enrolar2fa: vi.fn(),
  activar2fa: vi.fn(),
}));

import { pedirStepUp, enrolar2fa, activar2fa } from "../../api/dobleFactor";
import { StepUpModal } from "./StepUpModal";
import { useStepUpStore } from "../../context/stepUpStore";
import { useAuthStore } from "../../context/authStore";

function abrir(code = "step_up_requerido") {
  const promesa = useStepUpStore.getState().solicitar({ code, operacion: "Aprobar un lote de pagos" });
  promesa.catch(() => {});
  return promesa;
}

describe("StepUpModal", () => {
  beforeEach(() => {
    useStepUpStore.setState({ token: null, venceEn: 0, pedido: null });
    useAuthStore.setState({ token: "sesion", user: { username: "ana" }, mfa: { habilitado: true, activo: true } });
  });

  it("no muestra nada si nadie lo pidió", () => {
    render(<StepUpModal />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("pide el código, lo valida y entrega el token de step-up", async () => {
    pedirStepUp.mockResolvedValue({ step_up_token: "su-1", expires_in: 300 });
    render(<StepUpModal />);
    const promesa = abrir();
    expect(await screen.findByText("Aprobar un lote de pagos")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    await expect(promesa).resolves.toBe("su-1");
    expect(pedirStepUp).toHaveBeenCalledWith("123456");
    expect(useStepUpStore.getState().tokenVigente()).toBe("su-1");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("con un código incorrecto muestra los intentos que quedan y sigue abierto", async () => {
    pedirStepUp.mockRejectedValue({ response: { status: 422, data: { code: "codigo_invalido", detail: "El código no es correcto.", remaining_attempts: 2 } } });
    render(<StepUpModal />);
    abrir();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "000000");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El código no es correcto. Te quedan 2 intentos.");
    expect(useStepUpStore.getState().pedido).not.toBeNull();
  });

  it("si el servicio de 2FA no responde lo dice y no deja pasar", async () => {
    pedirStepUp.mockRejectedValue({ response: { status: 503, data: { code: "2fa_no_disponible", detail: "El servicio de doble factor no responde." } } });
    render(<StepUpModal />);
    abrir();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no responde");
    expect(useStepUpStore.getState().tokenVigente()).toBeNull();
  });

  it("no manda códigos incompletos", async () => {
    render(<StepUpModal />);
    abrir();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "12");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(pedirStepUp).not.toHaveBeenCalled();
  });

  it("acepta un código de recuperación", async () => {
    pedirStepUp.mockResolvedValue({ step_up_token: "su-r", expires_in: 300 });
    render(<StepUpModal />);
    const promesa = abrir();
    const user = userEvent.setup();
    await user.click(await screen.findByText(/usar un código de recuperación/));
    await user.type(screen.getByLabelText("Código de recuperación"), "abcde-fghij");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    await expect(promesa).resolves.toBe("su-r");
    expect(pedirStepUp).toHaveBeenCalledWith("ABCDE-FGHIJ");
  });

  it("cancelar rechaza la operación", async () => {
    render(<StepUpModal />);
    const promesa = abrir();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Cancelar" }));
    await expect(promesa).rejects.toThrow();
  });

  it("sin 2FA ofrece activarlo y después pide el próximo código", async () => {
    enrolar2fa.mockResolvedValue({ token_id: "t1", qr_png_base64: "QQ==", secret: "JBSWY3DPEHPK3PXP" });
    activar2fa.mockResolvedValue({ access_token: "sesion-2fa", recovery_codes: ["AAAAA-BBBBB"] });
    pedirStepUp.mockResolvedValue({ step_up_token: "su-2", expires_in: 300 });
    render(<StepUpModal />);
    const promesa = abrir("2fa_requerido");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Activar doble factor" }));
    expect(await screen.findByAltText("Código QR para la app autenticadora")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "111111");
    await user.click(screen.getByRole("button", { name: /Activar doble factor/ }));
    expect(await screen.findByText("AAAAA-BBBBB")).toBeInTheDocument();
    expect(useAuthStore.getState().token).toBe("sesion-2fa");
    await user.click(screen.getByRole("button", { name: "Ya los guardé" }));
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "222222");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    await expect(promesa).resolves.toBe("su-2");
  });
});
