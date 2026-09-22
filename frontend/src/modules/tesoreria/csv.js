/**
 * Lee un CSV de pagos: columnas beneficiario, documento, cbu, monto, concepto (en ese orden, o con
 * encabezado con esos nombres). Acepta `;` o `,` como separador y montos es-AR ("1.234,56") o "1234.56".
 */
export function montoDesdeTexto(v) {
  let s = String(v ?? "").trim().replace(/\$|\s/g, "");
  if (!s) return NaN;
  if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
  return Number(s);
}

const COLUMNAS = ["beneficiario", "documento", "cbu", "monto", "concepto"];

export function leerCsv(texto) {
  const lineas = String(texto || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lineas.length) return [];
  const sep = (lineas[0].match(/;/g) || []).length >= (lineas[0].match(/,/g) || []).length ? ";" : ",";
  const celdas = (l) => l.split(sep).map((c) => c.trim().replace(/^"(.*)"$/, "$1"));
  let orden = COLUMNAS;
  const primera = celdas(lineas[0]).map((c) => c.toLowerCase());
  if (primera.includes("cbu") && primera.includes("monto")) {
    orden = primera;
    lineas.shift();
  }
  return lineas.map((l) => {
    const c = celdas(l);
    const fila = Object.fromEntries(orden.map((k, i) => [k, c[i] ?? ""]));
    return {
      beneficiario: fila.beneficiario || "", documento: fila.documento || "", cbu: (fila.cbu || "").replace(/\D/g, ""),
      monto: fila.monto || "", concepto: fila.concepto || "",
    };
  });
}

/** Problema de una fila, o "" si está bien. */
export function problemaDeFila(f) {
  if (!f.beneficiario.trim()) return "Falta el beneficiario";
  if (String(f.cbu).replace(/\D/g, "").length !== 22) return "El CBU debe tener 22 dígitos";
  const m = montoDesdeTexto(f.monto);
  if (!(m > 0)) return "Monto inválido";
  return "";
}
