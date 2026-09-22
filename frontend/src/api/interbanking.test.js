import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import * as ib from "./interbanking";

describe("API de interbanking", () => {
  let get, post;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: { origen: "get" } });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { origen: "post" } });
  });

  afterEach(() => vi.restoreAllMocks());

  describe("configuración", () => {
    it("getConfig lee la configuración guardada", async () => {
      await expect(ib.getConfig()).resolves.toEqual({ origen: "get" });
      expect(get).toHaveBeenCalledWith("/interbanking/config");
    });

    it("saveConfig postea el formulario completo", async () => {
      const form = { name: "Sandbox", client_id: "abc" };
      await expect(ib.saveConfig(form)).resolves.toEqual({ origen: "post" });
      expect(post).toHaveBeenCalledWith("/interbanking/config", form);
    });

    it("testConfig manda el scope como query param", async () => {
      await ib.testConfig({ client_id: "abc" }, "info-financiera");
      expect(post).toHaveBeenCalledWith(
        "/interbanking/config/test",
        { client_id: "abc" },
        { params: { scope: "info-financiera" } }
      );
    });

    it("testConfig sin scope manda params vacíos", async () => {
      await ib.testConfig({ client_id: "abc" });
      expect(post).toHaveBeenCalledWith("/interbanking/config/test", { client_id: "abc" }, { params: {} });
    });

    it("getTokenStatus consulta el estado de los tokens", async () => {
      await ib.getTokenStatus();
      expect(get).toHaveBeenCalledWith("/interbanking/config/token-status");
    });
  });

  describe("cuentas y saldos", () => {
    it("getCuentas sin argumentos manda params vacíos", async () => {
      await ib.getCuentas();
      expect(get).toHaveBeenCalledWith("/interbanking/cuentas", { params: {} });
    });

    it("getCuenta arma la ruta con el número de cuenta", async () => {
      await ib.getCuenta("1234567", { currency: "ARS" });
      expect(get).toHaveBeenCalledWith("/interbanking/cuentas/1234567", { params: { currency: "ARS" } });
    });

    it("getSaldos pide el endpoint de saldos", async () => {
      await expect(ib.getSaldos({ bank: "011" })).resolves.toEqual({ origen: "get" });
      expect(get).toHaveBeenCalledWith("/interbanking/cuentas/saldos", { params: { bank: "011" } });
    });
  });

  describe("transferencias", () => {
    it("listarTransferencias manda el rango de fechas", async () => {
      await ib.listarTransferencias({ date_since: "2026-01-01", date_until: "2026-01-31" });
      expect(get).toHaveBeenCalledWith("/interbanking/transferencias", {
        params: { date_since: "2026-01-01", date_until: "2026-01-31" },
      });
    });

    it("crearTransferencia postea el cuerpo tal cual", async () => {
      const body = { cbu_destino: "1".repeat(22), monto: 100 };
      await expect(ib.crearTransferencia(body)).resolves.toEqual({ origen: "post" });
      expect(post).toHaveBeenCalledWith("/interbanking/transferencias", body);
    });

    it("validarCBU envuelve el valor en cbu_or_alias", async () => {
      await ib.validarCBU("mi.alias.banco");
      expect(post).toHaveBeenCalledWith("/interbanking/transferencias/validar", {
        cbu_or_alias: "mi.alias.banco",
      });
    });

    it("getEstadoTransferencia consulta el estado por id", async () => {
      await ib.getEstadoTransferencia(42);
      expect(get).toHaveBeenCalledWith("/interbanking/transferencias/42/estado");
    });

    it("getTransferenciasLocal lee la copia local", async () => {
      await ib.getTransferenciasLocal({ page: 2 });
      expect(get).toHaveBeenCalledWith("/interbanking/transferencias/local", { params: { page: 2 } });
    });
  });

  describe("auditoría", () => {
    it("getAuditoria manda los filtros", async () => {
      await ib.getAuditoria({ operation: "VALIDAR_CBU", page: 1 });
      expect(get).toHaveBeenCalledWith("/interbanking/auditoria", {
        params: { operation: "VALIDAR_CBU", page: 1 },
      });
    });

    it("getAuditoriaEntry pide una entrada puntual", async () => {
      await ib.getAuditoriaEntry(17);
      expect(get).toHaveBeenCalledWith("/interbanking/auditoria/17");
    });

    it("exportAuditoria pide un blob y devuelve la respuesta entera (no .data)", async () => {
      get.mockResolvedValueOnce({ data: "csv", status: 200 });
      await expect(ib.exportAuditoria({ success: "true" })).resolves.toEqual({ data: "csv", status: 200 });
      expect(get).toHaveBeenCalledWith("/interbanking/auditoria/export", {
        params: { success: "true" },
        responseType: "blob",
      });
    });
  });

  it("los errores del backend se propagan al llamador", async () => {
    post.mockRejectedValueOnce({ response: { data: { detail: "Credenciales inválidas" } } });
    await expect(ib.testConfig({}, "info-financiera")).rejects.toMatchObject({
      response: { data: { detail: "Credenciales inválidas" } },
    });
  });
});
