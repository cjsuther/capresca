import { describe, expect, it } from "vitest";
import { auditoriaMenu } from "./index";

describe("módulo Auditoría", () => {
  it("publica una sola pantalla, de consulta", () => {
    expect(auditoriaMenu.map((i) => [i.path, i.permission])).toEqual([
      ["/modules/auditoria/eventos", "eventos:read"],
    ]);
  });
});
