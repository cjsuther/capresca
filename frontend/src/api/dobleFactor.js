import api from "./client";

// Doble factor (TOTP). TokenServer y su API key viven sólo en el backend (módulo security): el
// navegador nunca habla con TokenServer.

// ── Login en dos pasos (sin sesión: viaja el token temporal `mfa_token`) ──
export const loginConCodigo = (mfaToken, code) =>
  api.post("/auth/2fa/login", { mfa_token: mfaToken, code }).then((r) => r.data);

export const loginEnrolar = (mfaToken) =>
  api.post("/auth/2fa/login/enrolar", { mfa_token: mfaToken }).then((r) => r.data);

export const loginActivar = (mfaToken, tokenId, code) =>
  api.post("/auth/2fa/login/activar", { mfa_token: mfaToken, token_id: tokenId, code }).then((r) => r.data);

// ── Con sesión ──
export const getEstado2fa = () => api.get("/auth/2fa/estado").then((r) => r.data);

export const enrolar2fa = () => api.post("/auth/2fa/enrolar").then((r) => r.data);

export const activar2fa = (tokenId, code) =>
  api.post("/auth/2fa/activar", { token_id: tokenId, code }).then((r) => r.data);

export const regenerarCodigos = (code) =>
  api.post("/auth/2fa/codigos-recuperacion", { code }).then((r) => r.data);

export const desactivar2fa = (code) => api.post("/auth/2fa/desactivar", { code }).then((r) => r.data);

export const pedirStepUp = (code) => api.post("/auth/2fa/step-up", { code }).then((r) => r.data);

// ── Administración ──
export const resetear2fa = (userId) => api.delete(`/security/users/${userId}/2fa`).then((r) => r.data);

/** Mensaje para el usuario a partir de un error del backend (incluye intentos restantes y bloqueo). */
export function mensajeError2fa(err, porDefecto = "No se pudo verificar el código") {
  const d = err?.response?.data || {};
  if (!err?.response) return "No hay conexión con el servidor. Probá de nuevo.";
  let msg = typeof d.detail === "string" ? d.detail : porDefecto;
  if (d.code === "codigo_invalido" && Number.isInteger(d.remaining_attempts)) {
    msg += d.remaining_attempts === 1 ? " Te queda 1 intento." : ` Te quedan ${d.remaining_attempts} intentos.`;
  }
  return msg;
}
