import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { waitFor } from "@testing-library/react";
import api from "./client";
import { useAuthStore } from "../context/authStore";
import { useStepUpStore } from "../context/stepUpStore";

/** Adapter falso: responde según la cola y registra cada request (con sus headers). */
function servidor(respuestas) {
  const pedidos = [];
  const original = api.defaults.adapter;
  api.defaults.adapter = async (config) => {
    pedidos.push({ method: config.method, url: config.url, headers: { ...config.headers } });
    const r = respuestas.shift() || { status: 200, data: { ok: true } };
    const resp = { data: r.data, status: r.status, statusText: "", headers: {}, config };
    if (r.status >= 400) {
      const err = new Error(`HTTP ${r.status}`);
      err.response = resp;
      err.config = config;
      throw err;
    }
    return resp;
  };
  return { pedidos, restaurar: () => { api.defaults.adapter = original; } };
}

const PIDE_CODIGO = { status: 403, data: { code: "step_up_requerido", operacion: "Aprobar un lote de pagos", detail: "x" } };

describe("step-up en el cliente HTTP", () => {
  let srv;
  beforeEach(() => {
    useAuthStore.setState({ token: "sesion-1", user: { username: "ana" }, permissions: null });
    useStepUpStore.setState({ token: null, venceEn: 0, pedido: null });
  });
  afterEach(() => srv?.restaurar());

  it("abre el modal, y con el código repite la operación con X-2FA-Token", async () => {
    srv = servidor([PIDE_CODIGO, { status: 200, data: { aprobado: true } }]);
    const op = api.post("/tesoreria/lotes/1/aprobar");

    await waitFor(() => expect(useStepUpStore.getState().pedido).not.toBeNull());
    expect(useStepUpStore.getState().pedido.operacion).toBe("Aprobar un lote de pagos");
    useStepUpStore.getState().completar("su-1", 300);

    const r = await op;
    expect(r.data).toEqual({ aprobado: true });
    expect(srv.pedidos).toHaveLength(2);
    expect(srv.pedidos[1].headers["X-2FA-Token"]).toBe("su-1");
    expect(srv.pedidos[1].headers.Authorization).toBe("Bearer sesion-1");
  });

  it("si el usuario cancela, la operación falla con el error original y no se repite", async () => {
    srv = servidor([PIDE_CODIGO]);
    const op = api.post("/tesoreria/lotes/1/aprobar");
    await waitFor(() => expect(useStepUpStore.getState().pedido).not.toBeNull());
    useStepUpStore.getState().cancelar();
    await expect(op).rejects.toMatchObject({ response: { status: 403 } });
    expect(srv.pedidos).toHaveLength(1);
  });

  it("con un token vigente lo manda en las operaciones que modifican, no en las lecturas", async () => {
    srv = servidor([]);
    useStepUpStore.getState().guardar("su-2", 300);
    await api.post("/tesoreria/lotes/2/enviar");
    await api.get("/tesoreria/lotes");
    expect(srv.pedidos[0].headers["X-2FA-Token"]).toBe("su-2");
    expect(srv.pedidos[1].headers["X-2FA-Token"]).toBeUndefined();
  });

  it("un token vencido no se manda", async () => {
    srv = servidor([]);
    useStepUpStore.setState({ token: "viejo", venceEn: Date.now() - 1000 });
    await api.post("/x");
    expect(srv.pedidos[0].headers["X-2FA-Token"]).toBeUndefined();
  });

  it("si el reintento vuelve a pedir el código, no entra en un bucle", async () => {
    srv = servidor([PIDE_CODIGO, PIDE_CODIGO]);
    const op = api.post("/tesoreria/lotes/1/aprobar");
    await waitFor(() => expect(useStepUpStore.getState().pedido).not.toBeNull());
    useStepUpStore.getState().completar("su-x", 300);
    await expect(op).rejects.toMatchObject({ response: { status: 403 } });
    expect(srv.pedidos).toHaveLength(2);
  });

  it("dos operaciones a la vez esperan el mismo código", async () => {
    srv = servidor([PIDE_CODIGO, PIDE_CODIGO, { status: 200, data: 1 }, { status: 200, data: 2 }]);
    const a = api.post("/tesoreria/lotes/1/aprobar");
    const b = api.post("/tesoreria/lotes/2/aprobar");
    await waitFor(() => expect(srv.pedidos).toHaveLength(2));
    useStepUpStore.getState().completar("su-3", 300);
    await Promise.all([a, b]);
    expect(srv.pedidos.slice(2).every((p) => p.headers["X-2FA-Token"] === "su-3")).toBe(true);
  });

  it("un 403 común (sin permiso) no abre el modal", async () => {
    srv = servidor([{ status: 403, data: { detail: "Acceso denegado" } }]);
    await expect(api.post("/x")).rejects.toMatchObject({ response: { status: 403 } });
    expect(useStepUpStore.getState().pedido).toBeNull();
  });
});
