import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import {
  getConciliacion,
  getSummary,
  getAgencies,
  getRecord,
  getHistory,
  updateRecord,
  assignAgency,
  removeLink,
  downloadBoleta,
  getAdjustments,
  addAdjustment,
} from "./conciliacion";

describe("API de conciliación", () => {
  let get;
  let post;
  let put;
  let del;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: { ok: true }, headers: {} });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { id: 1 } });
    put = vi.spyOn(api, "put").mockResolvedValue({ data: { actualizado: true } });
    del = vi.spyOn(api, "delete").mockResolvedValue({ data: { eliminado: true } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("pide los registros y las transacciones de una fecha", async () => {
    await expect(getConciliacion("2026-09-20")).resolves.toEqual({ ok: true });
    expect(get).toHaveBeenCalledWith("/conciliacion", { params: { date: "2026-09-20" } });
  });

  it("pide el resumen de la fecha", async () => {
    await getSummary("2026-09-20");
    expect(get).toHaveBeenCalledWith("/conciliacion/summary", { params: { date: "2026-09-20" } });
  });

  it("pide el padrón de agencias", async () => {
    await getAgencies();
    expect(get).toHaveBeenCalledWith("/conciliacion/agencies");
  });

  it("pide un registro puntual y su historial", async () => {
    await getRecord(42);
    expect(get).toHaveBeenCalledWith("/conciliacion/records/42");

    await getHistory(42);
    expect(get).toHaveBeenCalledWith("/conciliacion/records/42/history");
  });

  it("actualiza los importes de un registro", async () => {
    await expect(
      updateRecord(7, { importe_adeudado: 100, importe_premios: 20 })
    ).resolves.toEqual({ actualizado: true });
    expect(put).toHaveBeenCalledWith("/conciliacion/records/7", {
      importe_adeudado: 100,
      importe_premios: 20,
    });
  });

  it("asigna una agencia a una transacción interbanking", async () => {
    await assignAgency("transfer", 33, 5);
    expect(put).toHaveBeenCalledWith("/conciliacion/interbanking/transfer/33/agency", {
      client_id: 5,
    });
  });

  it("elimina un vínculo", async () => {
    await expect(removeLink(99)).resolves.toEqual({ eliminado: true });
    expect(del).toHaveBeenCalledWith("/conciliacion/links/99");
  });

  it("lista y carga ajustes manuales", async () => {
    await getAdjustments(7);
    expect(get).toHaveBeenCalledWith("/conciliacion/records/7/adjustments");

    await expect(addAdjustment(7, -150.5, "error de carga")).resolves.toEqual({ id: 1 });
    expect(post).toHaveBeenCalledWith("/conciliacion/records/7/adjustments", {
      amount: -150.5,
      reason: "error de carga",
    });
  });
});

describe("descarga de boleta", () => {
  let clicked;
  let revoke;

  beforeEach(() => {
    clicked = null;
    window.URL.createObjectURL = vi.fn(() => "blob:http://localhost/boleta");
    revoke = vi.fn();
    window.URL.revokeObjectURL = revoke;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function anchorClick() {
      clicked = this;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("usa el nombre que informa el content-disposition", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: new Blob(["pdf"]),
      headers: { "content-disposition": 'attachment; filename="boleta_0001_2026-09-20.pdf"' },
    });

    await downloadBoleta(12);

    expect(api.get).toHaveBeenCalledWith("/conciliacion/records/12/boleta", {
      responseType: "blob",
    });
    expect(clicked).not.toBeNull();
    expect(clicked.download).toBe("boleta_0001_2026-09-20.pdf");
    expect(clicked.getAttribute("href")).toBe("blob:http://localhost/boleta");
    // el <a> temporal no queda colgado en el DOM y la URL se libera
    expect(clicked.isConnected).toBe(false);
    expect(revoke).toHaveBeenCalledWith("blob:http://localhost/boleta");
  });

  it("si no hay content-disposition arma un nombre por defecto", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: new Blob(["pdf"]), headers: {} });

    await downloadBoleta(77);

    expect(clicked.download).toBe("boleta_77.pdf");
  });

  it("propaga el error de la API sin disparar la descarga", async () => {
    vi.spyOn(api, "get").mockRejectedValue({ response: { data: { detail: "sin boleta" } } });

    await expect(downloadBoleta(5)).rejects.toMatchObject({
      response: { data: { detail: "sin boleta" } },
    });
    expect(clicked).toBeNull();
  });
});
