import { describe, expect, it } from "vitest";
import { contabilidadMenu } from "./index";

describe("módulo Contabilidad", () => {
  it("declara sus pantallas con el permiso de consulta", () => {
    expect(contabilidadMenu.map((i) => [i.path, i.permission])).toEqual([
      ["/modules/contabilidad/transacciones", "asientos:read"],
      ["/modules/contabilidad/definiciones", "asientos:read"],
      ["/modules/contabilidad/libros", "asientos:read"],
      ["/modules/contabilidad/conciliacion", "asientos:read"],
      ["/modules/contabilidad/plan", "asientos:read"],
      ["/modules/contabilidad/ejercicios", "asientos:read"],
    ]);
  });
});
