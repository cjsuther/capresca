import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/dobleFactor", async (orig) => ({
  ...(await orig()),
  getEstado2fa: vi.fn(),
  enrolar2fa: vi.fn(),
  activar2fa: vi.fn(),
  regenerarCodigos: vi.fn(),
  desactivar2fa: vi.fn(),
}));

import { getEstado2fa, enrolar2fa, activar2fa, regenerarCodigos, desactivar2fa } from "../../api/dobleFactor";
import { DobleFactorModal } from "./DobleFactorModal";
import { useAuthStore } from "../../context/authStore";
import { useStepUpStore } from "../../context/stepUpStore";

const INACTIVO = { habilitado: true, activo: false, obligatorio: false, activado_en: null };
const ACTIVO = { habilitado: true, activo: true, obligatorio: false, activado_en: "2026-11-01T10:00:00Z" };

describe("DobleFactorModal (perfil)", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "sesion-1", user: { username: "ana" }, mfa: null });
    useStepUpStore.setState({ token: "su-viejo", venceEn: Date.now() + 60000, pedido: null });
  });

  it("apagado en el sistema: lo informa", async () => {
    getEstado2fa.mockResolvedValue({ habilitado: false, activo: false });
    render(<DobleFactorModal onClose={() => {}} />);
    expect(await screen.findByText("El doble factor no está habilitado en el sistema.")).toBeInTheDocument();
  });

  it("activar: QR, primer código, códigos de recuperación y sesión nueva", async () => {
    getEstado2fa.mockResolvedValueOnce(INACTIVO).mockResolvedValue(ACTIVO);
    enrolar2fa.mockResolvedValue({ token_id: "t1", qr_png_base64: "QQ==", secret: "ABCDEFGH" });
    activar2fa.mockResolvedValue({ access_token: "sesion-2", recovery_codes: ["K78YY-DW9QL"] });
    const user = userEvent.setup();
    render(<DobleFactorModal onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Activar doble factor" }));
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: /Activar doble factor/ }));
    expect(await screen.findByText("K78YY-DW9QL")).toBeInTheDocument();
    expect(activar2fa).toHaveBeenCalledWith("t1", "123456");
    expect(useAuthStore.getState().token).toBe("sesion-2");
    expect(useStepUpStore.getState().tokenVigente()).toBeNull();     // era de la sesión anterior
    expect(screen.getByRole("button", { name: "Descargar" })).toBeInTheDocument();
  });

  it("QR vencido: lo dice y deja generar otro", async () => {
    getEstado2fa.mockResolvedValue(INACTIVO);
    enrolar2fa.mockResolvedValue({ token_id: "t1", qr_png_base64: "QQ==", secret: "ABCD" });
    activar2fa.mockRejectedValue({ response: { status: 410, data: { code: "enrolamiento_vencido", detail: "El código QR venció." } } });
    const user = userEvent.setup();
    render(<DobleFactorModal onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Activar doble factor" }));
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: /Activar doble factor/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("venció");
    expect(screen.getByRole("button", { name: /Generar un código QR nuevo/ })).toBeInTheDocument();
  });

  it("desactivar pide un código y renueva la sesión", async () => {
    getEstado2fa.mockResolvedValueOnce(ACTIVO).mockResolvedValue(INACTIVO);
    desactivar2fa.mockResolvedValue({ access_token: "sesion-sin-2fa" });
    const user = userEvent.setup();
    render(<DobleFactorModal onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Desactivar" }));
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: "Desactivar" }));
    expect(await screen.findByText("No activado")).toBeInTheDocument();
    expect(desactivar2fa).toHaveBeenCalledWith("123456");
    expect(useAuthStore.getState().token).toBe("sesion-sin-2fa");
  });

  it("si el rol lo exige no ofrece desactivarlo", async () => {
    getEstado2fa.mockResolvedValue({ ...ACTIVO, obligatorio: true });
    render(<DobleFactorModal onClose={() => {}} />);
    expect(await screen.findByText("Activo")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Desactivar" })).toBeNull();
  });

  it("regenerar códigos pide un código y muestra los nuevos", async () => {
    getEstado2fa.mockResolvedValue(ACTIVO);
    regenerarCodigos.mockResolvedValue({ recovery_codes: ["NUEVO-CODIGO"] });
    const user = userEvent.setup();
    render(<DobleFactorModal onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: /Códigos de recuperación nuevos/ }));
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: "Generar códigos nuevos" }));
    expect(await screen.findByText("NUEVO-CODIGO")).toBeInTheDocument();
  });

  it("descargar arma un .txt con los códigos", async () => {
    getEstado2fa.mockResolvedValue(ACTIVO);
    regenerarCodigos.mockResolvedValue({ recovery_codes: ["AAAAA-BBBBB"] });
    const crear = vi.fn(() => "blob:x");
    URL.createObjectURL = crear;
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const user = userEvent.setup();
    render(<DobleFactorModal onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: /Códigos de recuperación nuevos/ }));
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: "Generar códigos nuevos" }));
    await user.click(await screen.findByRole("button", { name: "Descargar" }));
    expect(crear).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    const blob = crear.mock.calls[0][0];
    const texto = await new Promise((ok) => {
      const fr = new FileReader();
      fr.onload = () => ok(fr.result);
      fr.readAsText(blob);
    });
    expect(texto).toContain("AAAAA-BBBBB");
    expect(texto).toContain("Usuario: ana");
    click.mockRestore();
  });
});
