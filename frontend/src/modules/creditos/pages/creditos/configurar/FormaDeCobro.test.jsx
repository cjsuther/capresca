import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CFG_DEFAULT, CONFIG_DEFAULT, SCHEMA, valida } from "./esquemas";
import { EditorComponente } from "./EditorComponente";

const comp = (config) => ({ codigo: "COLLECTION", nombre: "Forma de cobro", categoria: "Cobranza", activo: true, config });
const editor = (config) => render(
  <EditorComponente comp={comp(config)} cfg={CFG_DEFAULT} errores={[]} editable editableDisp indices={[]} impuestos={[]}
                    catSegmentos={[]} catCanales={[]} setCfg={() => {}} setCompCfg={() => {}} toggleComp={() => {}} />,
);

describe("Forma de cobro (componente COLLECTION)", () => {
  it("con código de descuento exige el código y cómo figura en el recibo", () => {
    expect(valida("COLLECTION", CONFIG_DEFAULT.COLLECTION, CFG_DEFAULT))
      .toEqual(["Falta el código de descuento", "Falta cómo figura en el recibo de sueldo"]);
    expect(valida("COLLECTION", { modalidad: "CODIGO_DESCUENTO", codigoDescuento: "4521", conceptoRecibo: "CAPRESCA" }, CFG_DEFAULT))
      .toEqual([]);
    expect(valida("COLLECTION", { modalidad: "VENTANILLA" }, CFG_DEFAULT)).toEqual([]);
  });

  it("muestra las modalidades con nombre y cómo se le avisa al solicitante", () => {
    editor({ modalidad: "CODIGO_DESCUENTO", codigoDescuento: "4521", conceptoRecibo: "CAPRESCA PREST PERSONAL", detalle: "" });
    expect(screen.getByRole("option", { name: "Código de descuento (recibo de sueldo)" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("«CAPRESCA PREST PERSONAL», código de descuento 4521");
    expect(SCHEMA.COLLECTION.map((f) => f.k)).toEqual(["modalidad", "codigoDescuento", "conceptoRecibo", "detalle"]);
  });
});
