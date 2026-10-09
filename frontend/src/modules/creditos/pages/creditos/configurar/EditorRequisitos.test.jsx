import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EditorRequisitos } from "./EditorRequisitos";
import { codigoDesde, valida } from "./esquemas";

/** El editor con su estado, como lo usa la pantalla; `ver` expone la config para las aserciones. */
function Montado({ inicial = { documentos: [], campos: [] }, editable = true, ver }) {
  const [config, setConfig] = useState(inicial);
  ver.config = config;
  return <EditorRequisitos config={config} editable={editable}
                           onChange={(patch) => setConfig((c) => ({ ...c, ...patch }))} />;
}

describe("Documentación y datos de una línea", () => {
  it("un documento propio toma su código del título", async () => {
    const u = userEvent.setup();
    const ver = {};
    render(<Montado ver={ver} />);
    await u.click(screen.getByRole("button", { name: "＋ Otro documento" }));
    await u.type(screen.getByLabelText("Documento 1"), "Orden médica");
    await u.click(screen.getByLabelText("Documento 1 obligatorio"));

    expect(ver.config.documentos).toEqual([
      { codigo: "ORDEN_MEDICA", titulo: "Orden médica", ayuda: "", obligatorio: false }]);
  });

  it("los documentos estándar se agregan con su código de siempre y una sola vez", async () => {
    const u = userEvent.setup();
    const ver = {};
    render(<Montado ver={ver} />);
    await u.selectOptions(screen.getByLabelText("Agregar documento estándar"), "DNI_FRENTE");
    expect(ver.config.documentos[0]).toMatchObject({ codigo: "DNI_FRENTE", titulo: "DNI (frente)", obligatorio: true });
    expect(screen.queryByRole("option", { name: "DNI (frente)" })).toBeNull();
  });

  it("un combo de selección múltiple con sus opciones, uno por renglón", async () => {
    const u = userEvent.setup();
    const ver = {};
    render(<Montado ver={ver} />);
    await u.click(screen.getByRole("button", { name: "＋ Agregar dato" }));
    await u.type(screen.getByLabelText("Pregunta 1"), "Tipo de tratamiento");
    await u.selectOptions(screen.getByLabelText("Tipo de selección 1"), "MULTIPLE");
    await u.type(screen.getByLabelText("Opciones 1"), "Cirugía{enter}Óptica{enter}");
    await u.click(screen.getByLabelText("Dato 1 obligatorio"));

    expect(ver.config.campos).toEqual([{ codigo: "TIPO_DE_TRATAMIENTO", etiqueta: "Tipo de tratamiento", ayuda: "",
                                         tipo: "MULTIPLE", opciones: ["Cirugía", "Óptica"], obligatorio: false }]);
  });

  it("sólo lectura: se ve, no se edita", () => {
    render(<Montado ver={{}} editable={false}
                    inicial={{ documentos: [{ codigo: "X", titulo: "Orden médica", obligatorio: true }], campos: [] }} />);
    expect(screen.getByLabelText("Documento 1")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "＋ Otro documento" })).toBeNull();
    expect(screen.queryByLabelText("Quitar documento 1")).toBeNull();
  });
});

describe("codigoDesde y validación", () => {
  it("normaliza, recorta a 20 y no repite", () => {
    expect(codigoDesde("Presupuesto del prestador médico")).toBe("PRESUPUESTO_DEL_PRES");
    expect(codigoDesde("Orden médica", ["ORDEN_MEDICA"])).toBe("ORDEN_MEDICA_2");
    expect(codigoDesde("   ")).toBe("");
  });

  it("marca un combo sin opciones suficientes y un documento sin título", () => {
    const e = valida("REQUIREMENTS", {
      documentos: [{ codigo: "", titulo: "" }],
      campos: [{ etiqueta: "Obra social", tipo: "UNICA", opciones: ["OSEP"] }],
    }, {});
    expect(e).toEqual(["Documento #1: falta el título", "Dato Obra social: necesita al menos dos opciones"]);
  });
});
