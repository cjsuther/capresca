import { describe, expect, it } from "vitest";
import { tesoreriaMenu } from "./index";

describe("módulo Tesorería", () => {
  it("el menú declara sus pantallas con permisos", () => {
    expect(tesoreriaMenu.map((i) => [i.path, i.permission])).toEqual([
      ["/modules/tesoreria/lotes", "lotes:read"],
      ["/modules/tesoreria/nuevo", "lotes:write"],
    ]);
  });
});
