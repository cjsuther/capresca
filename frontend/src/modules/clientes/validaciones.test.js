import { describe, expect, it } from "vitest";

import { cuilValido, edadDe, validarPerfil } from "./validaciones";

// CUIL reales del padrón importado, verificados contra el algoritmo de ANSES.
const CUIL_OK = "20305047571";
const CUIL_MAL = "20305047572";   // mismo CUIL con el dígito verificador cambiado

describe("CUIL / CUIT", () => {
  it("acepta uno con el dígito verificador correcto", () => {
    expect(cuilValido(CUIL_OK)).toBe(true);
    expect(cuilValido("27-30504757-4")).toBe(cuilValido("27305047574"));   // ignora guiones
  });

  it("rechaza el dígito verificador equivocado y los largos que no son 11", () => {
    expect(cuilValido(CUIL_MAL)).toBe(false);
    expect(cuilValido("2030504757")).toBe(false);
    expect(cuilValido("")).toBe(false);
    expect(cuilValido(null)).toBe(false);
  });

  it("acepta el caso especial del prefijo 23", () => {
    // Cuando el cálculo con base 20/27 da 10, ANSES emite el CUIL con prefijo 23 y verificador 9 o 4.
    expect(cuilValido("23100000024")).toBe(true);   // base 27 → verificador 4
    expect(cuilValido("23100000059")).toBe(true);   // base 20 → verificador 9
    expect(cuilValido("23100000021")).toBe(false);  // mismo número, verificador inventado
  });
});

describe("edad", () => {
  it("calcula los años cumplidos", () => {
    const hace30 = new Date();
    hace30.setFullYear(hace30.getFullYear() - 30);
    expect(edadDe(hace30.toISOString().slice(0, 10))).toBe(30);
  });

  it("devuelve null si la fecha no sirve", () => {
    expect(edadDe("no-es-fecha")).toBeNull();
    expect(edadDe("")).toBeNull();
  });
});

const humano = (extra = {}) => ({
  first_name: "JUAN", last_name: "PEREZ", document_type: "DNI",
  document_number: "30504757", cuil: CUIL_OK, birth_date: "1984-03-04", gender: "M", ...extra,
});

describe("perfil de persona física", () => {
  it("un perfil correcto no tiene nada que corregir", () => {
    const r = validarPerfil(humano(), humano());
    expect(r.hayBloqueo).toBe(false);
    expect(r.avisos).toEqual({});
  });

  it("exige nombre y apellido", () => {
    const r = validarPerfil(humano({ first_name: " ", last_name: "" }), humano());
    expect(r.bloquean.first_name).toMatch(/obligatorio/);
    expect(r.bloquean.last_name).toMatch(/obligatorio/);
  });

  it("el documento tiene entre 6 y 8 dígitos", () => {
    expect(validarPerfil(humano({ document_number: "123" }), humano()).bloquean.document_number)
      .toMatch(/6 y 8/);
    expect(validarPerfil(humano({ document_number: "123456789" }), humano()).bloquean.document_number)
      .toMatch(/6 y 8/);
  });

  it("no deja escribir un CUIL con el verificador mal", () => {
    const r = validarPerfil(humano({ cuil: CUIL_MAL }), humano());
    expect(r.bloquean.cuil).toMatch(/no es válido/);
    expect(r.hayBloqueo).toBe(true);
  });

  it("avisa si el CUIL es válido pero no corresponde a ese documento", () => {
    // 20305047598 es un CUIL bien formado, pero del documento 30504759, no del 30504757.
    const r = validarPerfil(humano({ cuil: "20305047598" }), humano());
    expect(r.bloquean.cuil).toMatch(/no corresponde/);
  });

  it("la fecha de nacimiento no puede ser futura ni imposible", () => {
    const manana = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    expect(validarPerfil(humano({ birth_date: manana }), humano()).bloquean.birth_date)
      .toMatch(/futura/);
    expect(validarPerfil(humano({ birth_date: "1850-01-01" }), humano()).bloquean.birth_date)
      .toMatch(/antigua/);
  });

  it("el sexo tiene que estar en la lista", () => {
    expect(validarPerfil(humano({ gender: "Z" }), humano()).bloquean.gender).toBeTruthy();
    expect(validarPerfil(humano({ gender: "X" }), humano()).hayBloqueo).toBe(false);
  });

  // Lo que ya venía mal del padrón viejo (56 CUIL de 72.100) no puede trabar la corrección de
  // otro campo: se avisa, pero deja guardar.
  it("un dato que ya estaba mal y no se tocó avisa pero no bloquea", () => {
    const guardado = humano({ cuil: CUIL_MAL });
    const r = validarPerfil({ ...guardado, first_name: "JUAN CARLOS" }, guardado);
    expect(r.avisos.cuil).toMatch(/no es válido/);
    expect(r.bloquean).toEqual({});
    expect(r.hayBloqueo).toBe(false);
  });

  it("pero si lo toca y lo deja mal, bloquea", () => {
    const guardado = humano({ cuil: CUIL_MAL });
    const r = validarPerfil({ ...guardado, cuil: "20305047573" }, guardado);
    expect(r.bloquean.cuil).toBeTruthy();
  });
});

describe("perfil de persona jurídica", () => {
  const juridico = (extra = {}) => ({ legal_name: "AGENCIA SUR SRL", tax_id: CUIL_OK, ...extra });

  it("exige la razón social", () => {
    const r = validarPerfil(juridico({ legal_name: "" }), juridico(), false);
    expect(r.bloquean.legal_name).toMatch(/obligatoria/);
  });

  it("valida el CUIT y la fecha de constitución", () => {
    expect(validarPerfil(juridico({ tax_id: CUIL_MAL }), juridico(), false).bloquean.tax_id)
      .toMatch(/no es válido/);
    const manana = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    expect(validarPerfil(juridico({ incorporation_date: manana }), juridico(), false)
      .bloquean.incorporation_date).toMatch(/futura/);
  });
});
