import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import {
  processZip,
  uploadZip,
  getBatches,
  getBatch,
  getBatchDetalle,
  getBatchValidaciones,
  getBatchArchivos,
  getArchivoUrl,
  retryConciliacion,
} from "./liquidaciones";

describe("API de liquidaciones", () => {
  let get;
  let post;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: [{ id: 1 }] });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { batch_id: 9 } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("procesa un ZIP ya depositado en el servidor por su ruta", async () => {
    await expect(processZip("/data/externalfiles/lote.zip")).resolves.toEqual({ batch_id: 9 });
    expect(post).toHaveBeenCalledWith("/liquidaciones/process", {
      zip_path: "/data/externalfiles/lote.zip",
    });
  });

  it("sube el ZIP como multipart con el archivo en el campo file", async () => {
    const file = new File(["contenido"], "lote.zip", { type: "application/zip" });

    await expect(uploadZip(file)).resolves.toEqual({ batch_id: 9 });

    const [ruta, formData, config] = post.mock.calls[0];
    expect(ruta).toBe("/liquidaciones/upload");
    expect(formData).toBeInstanceOf(FormData);
    expect(formData.get("file")).toBe(file);
    expect(config.headers["Content-Type"]).toBe("multipart/form-data");
  });

  it("lista lotes pasando los filtros como query params", async () => {
    await expect(getBatches({ status: "VALIDADO" })).resolves.toEqual([{ id: 1 }]);
    expect(get).toHaveBeenCalledWith("/liquidaciones/batches", {
      params: { status: "VALIDADO" },
    });
  });

  it("trae un lote puntual", async () => {
    await getBatch(4);
    expect(get).toHaveBeenCalledWith("/liquidaciones/batches/4");
  });

  it("el detalle filtra por agencia sólo si se la indica", async () => {
    await getBatchDetalle(4, "0001");
    expect(get).toHaveBeenCalledWith("/liquidaciones/batches/4/detalle", {
      params: { agency: "0001" },
    });

    await getBatchDetalle(4);
    expect(get).toHaveBeenLastCalledWith("/liquidaciones/batches/4/detalle", { params: {} });
  });

  it("trae validaciones y archivos del lote", async () => {
    await getBatchValidaciones(4);
    expect(get).toHaveBeenCalledWith("/liquidaciones/batches/4/validaciones");

    await getBatchArchivos(4);
    expect(get).toHaveBeenCalledWith("/liquidaciones/batches/4/archivos");
  });

  it("arma la URL pública de un archivo adjunto", () => {
    // TODO(bug): esta URL se usa en un <a href> directo, sin el JWT que agrega el cliente axios.
    expect(getArchivoUrl(4, 12)).toBe("/api/liquidaciones/batches/4/archivos/12");
  });

  it("reintenta el envío a conciliación", async () => {
    await retryConciliacion(4);
    expect(post).toHaveBeenCalledWith("/liquidaciones/batches/4/retry-conciliacion");
  });

  it("propaga el error de la API", async () => {
    post.mockRejectedValueOnce({ response: { data: { detail: "ZIP inválido" } } });
    await expect(processZip("/x.zip")).rejects.toMatchObject({
      response: { data: { detail: "ZIP inválido" } },
    });
  });
});
