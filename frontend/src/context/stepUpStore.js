import { create } from "zustand";

/**
 * Step-up (operaciones sensibles): el gateway responde 403 `step_up_requerido` o `2fa_requerido`; el
 * interceptor de `api/client.js` llama a `solicitar()`, que abre el <StepUpModal> y espera.
 *
 * El token de step-up queda SÓLO en memoria (no en sessionStorage) y unos minutos: no se pide el código
 * en cada clic, y al recargar la página se vuelve a pedir.
 */
export const useStepUpStore = create((set, get) => ({
  token: null,
  venceEn: 0,          // epoch ms
  pedido: null,        // { code, operacion, detail, resolver, rechazar }

  tokenVigente: () => {
    const { token, venceEn } = get();
    return token && Date.now() < venceEn - 5000 ? token : null;
  },

  guardar: (token, segundos) => set({ token, venceEn: Date.now() + segundos * 1000 }),

  olvidar: () => set({ token: null, venceEn: 0 }),

  /** Abre el modal. Resuelve con el token de step-up, o rechaza si el usuario cancela. */
  solicitar: ({ code, operacion, detail }) => {
    const previo = get().pedido;
    if (previo) {
      // Ya hay un modal abierto (dos requests a la vez): esperan el mismo código.
      return new Promise((resolver, rechazar) => {
        const r0 = previo.resolver, j0 = previo.rechazar;
        previo.resolver = (t) => { r0(t); resolver(t); };
        previo.rechazar = (e) => { j0(e); rechazar(e); };
      });
    }
    return new Promise((resolver, rechazar) =>
      set({ pedido: { code, operacion, detail, resolver, rechazar } }));
  },

  completar: (token, segundos) => {
    const p = get().pedido;
    set({ token, venceEn: Date.now() + segundos * 1000, pedido: null });
    p?.resolver(token);
  },

  cancelar: (motivo = "cancelado") => {
    const p = get().pedido;
    set({ pedido: null });
    p?.rechazar(new Error(motivo));
  },
}));
