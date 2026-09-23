import { describe, expect, it } from "vitest";
import { leerCsv, montoDesdeTexto, problemaDeFila } from "./csv";

describe("CSV de pagos", () => {
  it("lee sin encabezado, con ; y montos es-AR", () => {
    expect(leerCsv("PEREZ JUAN;20301234569;2850590940090418135201;1.234,56;Honorarios")).toEqual([{
      beneficiario: "PEREZ JUAN", documento: "20301234569", cbu: "2850590940090418135201", monto: "1.234,56", concepto: "Honorarios",
    }]);
    expect(montoDesdeTexto("1.234,56")).toBe(1234.56);
    expect(montoDesdeTexto("$ 1500.5")).toBe(1500.5);
  });

  it("respeta el orden del encabezado y limpia el CBU", () => {
    const [f] = leerCsv("monto,cbu,beneficiario\n500,\"2850-5909-40090418135201\",ANA");
    expect(f).toMatchObject({ beneficiario: "ANA", cbu: "2850590940090418135201", monto: "500" });
  });

  it("marca las filas inválidas", () => {
    const ok = { beneficiario: "ANA", documento: "", cbu: "2850590940090418135201", monto: "10", concepto: "" };
    expect(problemaDeFila(ok)).toBe("");
    expect(problemaDeFila({ ...ok, cbu: "123" })).toMatch(/CBU/);
    expect(problemaDeFila({ ...ok, monto: "0" })).toMatch(/Monto/);
    expect(problemaDeFila({ ...ok, beneficiario: " " })).toMatch(/beneficiario/);
  });
});
