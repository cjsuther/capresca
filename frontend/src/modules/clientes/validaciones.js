/**
 * Validaciones de la ficha del cliente.
 *
 * Criterio con los datos viejos: el padrón importado trae 56 CUIL con el dígito verificador mal y
 * un puñado de documentos fuera de formato. No se puede trabar la edición de esos clientes —el
 * operador entraría a corregir el teléfono y no podría guardar—, así que un valor que **ya venía
 * mal y no se tocó** se avisa pero deja guardar; uno que el operador **escribe** mal, no.
 */

export const TIPOS_DOCUMENTO = [
  ["DNI", "DNI"],
  ["LC", "Libreta cívica"],
  ["LE", "Libreta de enrolamiento"],
  ["CI", "Cédula de identidad"],
  ["PASAPORTE", "Pasaporte"],
];

export const SEXOS = [
  ["M", "Masculino"],
  ["F", "Femenino"],
  ["X", "No binario"],
];

export const TIPOS_ID_FISCAL = [
  ["CUIT", "CUIT"],
  ["CUIL", "CUIL"],
  ["CDI", "CDI"],
];

const PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];

/** Dígito verificador de un CUIL/CUIT (módulo 11). Devuelve 10 en el caso del prefijo 23. */
function digitoVerificador(diez) {
  const suma = diez.split("").reduce((a, d, i) => a + Number(d) * PESOS[i], 0);
  const r = 11 - (suma % 11);
  return r === 11 ? 0 : r;
}

/**
 * CUIL/CUIT válido: 11 dígitos y dígito verificador correcto.
 *
 * Los que empiezan con 23 son el caso especial de ANSES: salen cuando el cálculo con la base 20
 * (varón) o 27 (mujer) da 10, y entonces el CUIL pasa a 23 con verificador 9 o 4.
 */
export function cuilValido(valor) {
  const c = String(valor || "").replace(/\D/g, "");
  if (c.length !== 11) return false;
  const dv = Number(c[10]);
  if (digitoVerificador(c.slice(0, 10)) === dv) return true;
  if (c.startsWith("23")) {
    return [["20", 9], ["27", 4]].some(
      ([base, esperado]) => digitoVerificador(base + c.slice(2, 10)) === 10 && dv === esperado);
  }
  return false;
}

const soloDigitos = (v) => String(v || "").replace(/\D/g, "");

/** Años cumplidos a hoy; null si la fecha no sirve. */
export function edadDe(fecha) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(fecha || ""))) return null;
  const n = new Date(`${fecha}T00:00:00`);
  if (isNaN(n.getTime())) return null;
  const hoy = new Date();
  let e = hoy.getFullYear() - n.getFullYear();
  const m = hoy.getMonth() - n.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < n.getDate())) e--;
  return e;
}

export const hoyISO = () => new Date().toISOString().slice(0, 10);

/** Reglas de la persona física. Devuelve { campo: mensaje } con lo que está mal. */
function reglasHumano(f) {
  const e = {};
  if (!String(f.first_name || "").trim()) e.first_name = "El nombre es obligatorio.";
  if (!String(f.last_name || "").trim()) e.last_name = "El apellido es obligatorio.";

  const doc = soloDigitos(f.document_number);
  const tipo = f.document_type || "DNI";
  if (f.document_number) {
    if (["DNI", "LC", "LE"].includes(tipo) && (doc.length < 6 || doc.length > 8)) {
      e.document_number = "El documento tiene que tener entre 6 y 8 dígitos.";
    } else if (!doc && tipo !== "PASAPORTE") {
      e.document_number = "El documento sólo lleva números.";
    }
  }

  if (f.cuil && !cuilValido(f.cuil)) {
    e.cuil = "El CUIL no es válido (11 dígitos y dígito verificador).";
  }
  // El CUIL contiene el documento: si no coinciden, uno de los dos está mal cargado.
  if (!e.cuil && f.cuil && doc && soloDigitos(f.cuil).slice(2, 10).replace(/^0+/, "") !== doc.replace(/^0+/, "")) {
    e.cuil = "El CUIL no corresponde a ese número de documento.";
  }

  if (f.birth_date) {
    const edad = edadDe(f.birth_date);
    if (edad === null) e.birth_date = "La fecha no es válida.";
    else if (edad < 0) e.birth_date = "La fecha de nacimiento no puede ser futura.";
    else if (edad > 120) e.birth_date = "La fecha de nacimiento es demasiado antigua.";
  }

  if (f.gender && !SEXOS.some(([v]) => v === f.gender)) e.gender = "Elegí una opción de la lista.";
  return e;
}

/** Reglas de la persona jurídica. */
function reglasJuridico(f) {
  const e = {};
  if (!String(f.legal_name || "").trim()) e.legal_name = "La razón social es obligatoria.";
  if (f.tax_id && !cuilValido(f.tax_id)) {
    e.tax_id = "El CUIT no es válido (11 dígitos y dígito verificador).";
  }
  if (f.incorporation_date) {
    const edad = edadDe(f.incorporation_date);
    if (edad === null) e.incorporation_date = "La fecha no es válida.";
    else if (edad < 0) e.incorporation_date = "La fecha de constitución no puede ser futura.";
  }
  return e;
}

/**
 * Valida el perfil y separa lo que **bloquea** de lo que sólo se **avisa**.
 *
 * Bloquea lo que el operador escribió mal. Si el valor es el que ya estaba guardado (viene del
 * padrón viejo) y no lo tocó, se avisa nomás: si no, no podría corregir ningún otro campo.
 */
export function validarPerfil(form, original = {}, esHumano = true) {
  const errores = esHumano ? reglasHumano(form) : reglasJuridico(form);
  const bloquean = {};
  const avisos = {};
  for (const [campo, mensaje] of Object.entries(errores)) {
    const sinTocar = String(form[campo] ?? "") === String(original[campo] ?? "");
    (sinTocar ? avisos : bloquean)[campo] = mensaje;
  }
  return { bloquean, avisos, hayBloqueo: Object.keys(bloquean).length > 0 };
}
