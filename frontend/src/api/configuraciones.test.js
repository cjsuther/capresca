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
    await c.agregarNivel(1, { rol: "APROBAR" });
    await c.editarRegla(2, { activo: true });
    await c.agregarOverride(7, { username: "ana", modo: "EXCLUIR" });
    await c.borrarOverride(8);
    expect(post).toHaveBeenCalledWith("/configuraciones/impuestos", { codigo: "X" });
    expect(put).toHaveBeenCalledWith("/configuraciones/indices/3", { valor: 50 });
    expect(post).toHaveBeenCalledWith("/configuraciones/impuestos/4/baja");
    expect(post).toHaveBeenCalledWith("/configuraciones/indices/5/reactivar");
    expect(post).toHaveBeenCalledWith("/configuraciones/feriados/importar", { pais: "AR", anio: 2027 });
    expect(del).toHaveBeenCalledWith("/configuraciones/feriados/9");
    expect(post).toHaveBeenCalledWith("/configuraciones/workflow/reglas/1/niveles", { rol: "APROBAR" });
    expect(put).toHaveBeenCalledWith("/configuraciones/workflow/reglas/2", { activo: true });
    expect(post).toHaveBeenCalledWith("/configuraciones/workflow/niveles/7/usuarios", { username: "ana", modo: "EXCLUIR" });
    expect(del).toHaveBeenCalledWith("/configuraciones/workflow/usuarios/8");
  });

  it("normaliza los errores de la API", () => {
    expect(c.mensajeDeError({ response: { data: { detail: "Ya existe" } } })).toBe("Ya existe");
    expect(c.mensajeDeError({ response: { data: { detail: [{ loc: ["body", "alicuota"], msg: "debe ser ≤ 100" }] } } }))
      .toBe("alicuota: debe ser ≤ 100");
    expect(c.mensajeDeError(new Error("red"), "Sin conexión")).toBe("Sin conexión");
  });
});
