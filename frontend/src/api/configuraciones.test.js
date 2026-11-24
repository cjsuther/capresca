import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import * as c from "./configuraciones";

describe("API del módulo Configuraciones", () => {
  let get, post, put, del;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: { items: [] } });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { ok: true } });
    put = vi.spyOn(api, "put").mockResolvedValue({ data: { ok: true } });
    del = vi.spyOn(api, "delete").mockResolvedValue({ data: { ok: true } });
  });
  afterEach(() => vi.restoreAllMocks());

  it("lee los catálogos con su filtro y devuelve el cuerpo", async () => {
    await expect(c.listarImpuestos("activos")).resolves.toEqual({ items: [] });
    expect(get).toHaveBeenCalledWith("/configuraciones/impuestos", { params: { estado: "activos" } });
    await c.listarIndices();
    expect(get).toHaveBeenCalledWith("/configuraciones/indices", { params: { estado: "todos" } });
    await c.listarFeriados("AR", 2026);
    expect(get).toHaveBeenCalledWith("/configuraciones/feriados", { params: { pais: "AR", anio: 2026 } });
    await c.listarWorkflow();
    expect(get).toHaveBeenCalledWith("/configuraciones/workflow", { params: {} });
    await c.listarWorkflow("creditos");
    expect(get).toHaveBeenCalledWith("/configuraciones/workflow", { params: { modulo: "creditos" } });
  });

  it("escribe en las rutas de cada catálogo", async () => {
    await c.crearImpuesto({ codigo: "X" });
    await c.editarIndice(3, { valor: 50 });
    await c.bajaImpuesto(4);
    await c.reactivarIndice(5);
    await c.importarFeriados("AR", 2027);
    await c.borrarFeriado(9);
    expect(post).toHaveBeenCalledWith("/configuraciones/impuestos", { codigo: "X" });
    expect(put).toHaveBeenCalledWith("/configuraciones/indices/3", { valor: 50 });
    expect(post).toHaveBeenCalledWith("/configuraciones/impuestos/4/baja");
    expect(post).toHaveBeenCalledWith("/configuraciones/indices/5/reactivar");
    expect(post).toHaveBeenCalledWith("/configuraciones/feriados/importar", { pais: "AR", anio: 2027 });
    expect(del).toHaveBeenCalledWith("/configuraciones/feriados/9");
  });

  it("usa las rutas del workflow gráfico", async () => {
    const W = "/configuraciones/workflow";
    await c.listarProcesos();
    await c.verVersion(4);
    await c.crearBorrador(2);
    await c.crearBorrador(2, 1);
    await c.guardarBorrador(4, { grafo: {}, revision: 3 });
    await c.descartarBorrador(4);
    await c.publicarVersion(4, "Gerencia firma");
    await c.retirarVersion(4);
    await c.habilitarProceso(2, false);
    await c.compararVersiones(1, 4);
    expect(get).toHaveBeenCalledWith(`${W}/procesos`);
    expect(get).toHaveBeenCalledWith(`${W}/versiones/4`);
    expect(post).toHaveBeenCalledWith(`${W}/procesos/2/borrador`, {});
    expect(post).toHaveBeenCalledWith(`${W}/procesos/2/borrador`, { desde: 1 });
    expect(put).toHaveBeenCalledWith(`${W}/versiones/4`, { grafo: {}, revision: 3 });
    expect(del).toHaveBeenCalledWith(`${W}/versiones/4`);
    expect(post).toHaveBeenCalledWith(`${W}/versiones/4/publicar`, { nota: "Gerencia firma" });
    expect(post).toHaveBeenCalledWith(`${W}/versiones/4/retirar`);
    expect(post).toHaveBeenCalledWith(`${W}/procesos/2/habilitado`, { habilitado: false });
    expect(get).toHaveBeenCalledWith(`${W}/comparar`, { params: { a: 1, b: 4 } });
  });

  it("normaliza los errores de la API", () => {
    const publicar = { response: { data: { detail: { mensaje: "Tiene errores", problemas: [{ mensaje: "Falta el Fin" }, "x"] } } } };
    expect(c.mensajeDeError(publicar)).toBe("Tiene errores");
    expect(c.problemasDeError(publicar)).toEqual(["Falta el Fin", "x"]);
    expect(c.problemasDeError(new Error("red"))).toEqual([]);
    expect(c.mensajeDeError({ response: { data: { detail: "Ya existe" } } })).toBe("Ya existe");
    expect(c.mensajeDeError({ response: { data: { detail: [{ loc: ["body", "alicuota"], msg: "debe ser ≤ 100" }] } } }))
      .toBe("alicuota: debe ser ≤ 100");
    expect(c.mensajeDeError(new Error("red"), "Sin conexión")).toBe("Sin conexión");
  });
});
