import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/dobleFactor", async (orig) => ({
  ...(await orig()),
  loginConCodigo: vi.fn(),
  loginEnrolar: vi.fn(),
  loginActivar: vi.fn(),
}));

import LoginPage from "./LoginPage";
import { useAuthStore } from "../context/authStore";
import * as authApi from "../api/auth";
import { loginConCodigo, loginEnrolar, loginActivar } from "../api/dobleFactor";

const SESION = {
  access_token: "tok-2fa",
  user: { id: 1, username: "ana", full_name: "Ana" },
  permissions: { modules: ["tesoreria"], actions: { tesoreria: ["lotes:read"] } },
  mfa: { habilitado: true, activo: true },
};

function montar() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<p>tablero</p>} />
      </Routes>
    </MemoryRouter>
  );
}

async function ingresar(user) {
  await user.type(screen.getByPlaceholderText("usuario"), "ana");
  await user.type(screen.getByPlaceholderText("••••••••"), "secreta");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("LoginPage con doble factor", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, permissions: null, mfa: null });
  });

  it("con 2FA activo la clave sola no da sesión: pide el código", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_2fa: true, mfa_token: "mfa-1", access_token: null });
    loginConCodigo.mockResolvedValue(SESION);
    const user = userEvent.setup();
    montar();
    await ingresar(user);

    const campo = await screen.findByLabelText("Código de 6 dígitos");
    expect(useAuthStore.getState().token).toBeNull();
    await user.type(campo, "123456");
    await user.click(screen.getByRole("button", { name: /Verificar/ }));

    await waitFor(() => expect(screen.getByText("tablero")).toBeInTheDocument());
    expect(loginConCodigo).toHaveBeenCalledWith("mfa-1", "123456");
    expect(useAuthStore.getState().token).toBe("tok-2fa");
    expect(useAuthStore.getState().mfa).toEqual({ habilitado: true, activo: true });
  });

  it("código incorrecto: muestra el error y deja reintentar", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_2fa: true, mfa_token: "mfa-1" });
    loginConCodigo.mockRejectedValueOnce({ response: { status: 422, data: { code: "codigo_invalido", detail: "El código no es correcto.", remaining_attempts: 1 } } });
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "000000");
    await user.click(screen.getByRole("button", { name: /Verificar/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Te queda 1 intento.");
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("bloqueado o servicio caído: no entra", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_2fa: true, mfa_token: "mfa-1" });
    loginConCodigo.mockRejectedValue({ response: { status: 429, data: { code: "2fa_bloqueado", detail: "Demasiados códigos incorrectos. Probá de nuevo en 60 segundos." } } });
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: /Verificar/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("60 segundos");
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("si el paso venció vuelve a pedir usuario y clave", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_2fa: true, mfa_token: "mfa-1" });
    loginConCodigo.mockRejectedValue({ response: { status: 400, data: { code: "mfa_token_invalido", detail: "El paso de verificación venció." } } });
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    await user.type(await screen.findByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: /Verificar/ }));
    expect(await screen.findByText("El paso de verificación venció.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("usuario")).toBeInTheDocument();
  });

  it("con código de recuperación avisa cuántos le quedan antes de entrar", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_2fa: true, mfa_token: "mfa-1" });
    loginConCodigo.mockResolvedValue({ ...SESION, remaining_recovery_codes: 3 });
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    await user.click(await screen.findByText(/usar un código de recuperación/));
    await user.type(screen.getByLabelText("Código de recuperación"), "AAAAA-BBBBB");
    await user.click(screen.getByRole("button", { name: /Verificar/ }));
    expect(await screen.findByText("3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await waitFor(() => expect(screen.getByText("tablero")).toBeInTheDocument());
  });

  it("2FA obligatorio sin activar: enrola, muestra los códigos y recién ahí entra", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_enrollment: true, mfa_token: "mfa-e" });
    loginEnrolar.mockResolvedValue({ token_id: "t1", qr_png_base64: "QQ==", secret: "JBSWY3DPEHPK3PXP" });
    loginActivar.mockResolvedValue({ ...SESION, recovery_codes: ["K78YY-DW9QL", "LWFZ6-V4CFA"] });
    const user = userEvent.setup();
    montar();
    await ingresar(user);

    expect(await screen.findByAltText("Código QR para la app autenticadora")).toBeInTheDocument();
    expect(screen.getByText("JBSW Y3DP EHPK 3PXP")).toBeInTheDocument();
    expect(loginEnrolar).toHaveBeenCalledWith("mfa-e");
    await user.type(screen.getByLabelText("Código de 6 dígitos"), "123456");
    await user.click(screen.getByRole("button", { name: /Activar doble factor/ }));

    expect(await screen.findByText("K78YY-DW9QL")).toBeInTheDocument();
    expect(loginActivar).toHaveBeenCalledWith("mfa-e", "t1", "123456");
    expect(useAuthStore.getState().token).toBeNull();          // todavía no
    await user.click(screen.getByRole("button", { name: "Ya los guardé, ingresar" }));
    await waitFor(() => expect(screen.getByText("tablero")).toBeInTheDocument());
    expect(useAuthStore.getState().token).toBe("tok-2fa");
  });

  it("enrolamiento con TokenServer caído: lo dice y ofrece reintentar", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ requires_enrollment: true, mfa_token: "mfa-e" });
    loginEnrolar.mockRejectedValue({ response: { status: 503, data: { code: "2fa_no_disponible", detail: "El servicio de doble factor no responde." } } });
    const user = userEvent.setup();
    montar();
    await ingresar(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("no responde");
    expect(screen.getByRole("button", { name: /Generar un código QR nuevo/ })).toBeInTheDocument();
    expect(useAuthStore.getState().token).toBeNull();
  });
});
