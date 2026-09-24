import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import { subirDespacho } from "./despacho";

vi.mock("./client", () => ({ default: { post: vi.fn(async () => ({ data: {} })) } }));

beforeEach(() => vi.clearAllMocks());

describe("subir el backup del despacho", () => {
  it("va sin el límite de tiempo general: son ~26 MB y no entran en 15 s", async () => {
    const archivo = new File(["x"], "despacho.zip", { type: "application/zip" });
    await subirDespacho(archivo, () => {});

    const [ruta, cuerpo, opciones] = api.post.mock.calls[0];
    expect(ruta).toBe("/despacho/importaciones");
    expect(cuerpo.get("file")).toBe(archivo);
    expect(opciones.timeout).toBe(0);
  });

  it("informa el avance de la subida", async () => {
    const avances = [];
    await subirDespacho(new File(["x"], "d.zip"), (p) => avances.push(p));
    const { onUploadProgress } = api.post.mock.calls[0][2];

    onUploadProgress({ loaded: 13, total: 26 });
    expect(avances).toEqual([50]);
  });
});
