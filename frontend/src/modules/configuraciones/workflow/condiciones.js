/** Constructor de condiciones de las decisiones: funciones puras. */
import { OPERADORES } from "./grafo";

export const TEXTO_OPERADOR = {
  "=": "es", "!=": "no es", ">": "es mayor que", ">=": "es mayor o igual que", "<": "es menor que",
  "<=": "es menor o igual que", contiene: "contiene", en: "es alguno de",
};

export const operadoresPara = (variable) => OPERADORES[variable?.tipo] || [];

/** Valor inicial razonable para una variable y operador. */
export function valorInicial(variable, op) {
  if (!variable) return "";
  if (variable.tipo === "numero") return 0;
  if (variable.tipo === "booleano") return true;
  if (variable.tipo === "opcion") return op === "en" ? [variable.opciones?.[0]].filter(Boolean) : variable.opciones?.[0] ?? "";
  return "";
}

/** Regla nueva usando la primera variable del proceso. */
export function reglaNueva(variables) {
  const [clave, v] = Object.entries(variables || {})[0] || [];
  if (!clave) return null;
  const op = operadoresPara(v)[0];
  return { variable: clave, op, valor: valorInicial(v, op) };
}

/** Cambia un campo de la regla y deja el resto coherente (op y valor válidos para la variable). */
export function cambiarRegla(regla, campo, valor, variables) {
  const r = { ...regla, [campo]: valor };
  const v = variables?.[r.variable];
  if (campo === "variable") {
    r.op = operadoresPara(v)[0];
    r.valor = valorInicial(v, r.op);
  } else if (campo === "op" && v?.tipo === "opcion") {
    const eraLista = Array.isArray(regla.valor);
    if (r.op === "en" && !eraLista) r.valor = [regla.valor].filter((x) => x !== "" && x !== undefined);
    if (r.op !== "en" && eraLista) r.valor = regla.valor[0] ?? v.opciones?.[0] ?? "";
  }
  return r;
}

/** Convierte lo que se tipeó en un input al tipo de la variable. */
export function leerValor(variable, texto) {
  if (variable?.tipo === "numero") {
    const n = Number(String(texto).replace(/\./g, "").replace(",", "."));
    return Number.isFinite(n) ? n : NaN;
  }
  if (variable?.tipo === "booleano") return texto === true || texto === "true";
  return texto;
}

const fmt = (variable, valor) => {
  if (Array.isArray(valor)) return valor.join(", ");
  if (variable?.tipo === "numero" && typeof valor === "number") return valor.toLocaleString("es-AR");
  if (variable?.tipo === "booleano") return valor ? "sí" : "no";
  return `«${valor}»`;
};

/** Texto legible: «Monto solicitado es mayor que 5.000.000 y Origen es «PORTAL»». */
export function describirCondicion(cond, variables) {
  const reglas = cond?.reglas || [];
  if (!reglas.length) return "sin condición";
  const partes = reglas.map((r) => {
    const v = variables?.[r.variable];
    return `${v?.nombre || r.variable} ${TEXTO_OPERADOR[r.op] || r.op} ${fmt(v, r.valor)}`;
  });
  return partes.join(cond.modo === "alguna" ? " o " : " y ");
}

/** Etiqueta corta para la flecha del diagrama. */
export function etiquetaConexion(c, variables) {
  if (c.salida) return c.salida;
  if (c.defecto) return "si no";
  if (c.condicion) {
    const t = describirCondicion(c.condicion, variables);
    return t.length > 40 ? `${t.slice(0, 38)}…` : t;
  }
  return c.etiqueta || "";
}
